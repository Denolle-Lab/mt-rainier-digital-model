"""Soil and regolith layers of the critical zone (configs/soil.yaml).

- SOLUS100 (Nauman et al. 2024): clay, sand, silt, bulk density, rock fragments and organic carbon at seven
  depths from 0 to 1.5 m, and the depth to any restrictive layer; the USDA texture class follows from clay,
  sand and silt.
- POLARIS (Chaney et al. 2019): saturated hydraulic conductivity and van Genuchten parameters in six layers
  from 0 to 2 m.
- Depth to bedrock (Shangguan et al. 2017), metres, beyond the 2 m reach of the soil surveys.
- Vs30 (USGS global hybrid map, Heath et al. 2020).

Profiles keep their depth axis (``soil_depth`` for SOLUS points, ``polaris_layer`` for POLARIS intervals) and
go to the /soil node; 2D summaries over ``summary_cm`` go to /surface with the other surface layers.
"""

from __future__ import annotations

import logging

import numpy as np
import rasterio
import xarray as xr
import yaml
from rasterio.enums import Resampling

from rainier3d.config.domain import REPO, Domain
from rainier3d.io.store import provenance
from rainier3d.surface.layers import SOLUS, _clip_to_cache, _da, warp

log = logging.getLogger(__name__)

CFG = REPO / "configs" / "soil.yaml"

# USDA texture classes (Soil Survey Manual, 2017, Fig. 3-16): value, label, colour. 0 = no data.
TEXTURE = [
    (1, "Sand", "#f4e5a1"),
    (2, "Loamy sand", "#e9cf7c"),
    (3, "Sandy loam", "#d9b25f"),
    (4, "Loam", "#b9915a"),
    (5, "Silt loam", "#c9b98f"),
    (6, "Silt", "#ddd5b8"),
    (7, "Sandy clay loam", "#c08048"),
    (8, "Clay loam", "#9c6a4a"),
    (9, "Silty clay loam", "#a58a72"),
    (10, "Sandy clay", "#b0603c"),
    (11, "Silty clay", "#8a6f63"),
    (12, "Clay", "#6e4b3c"),
]
LOG10_CMHR_TO_MS = np.log10(0.01 / 3600.0)  # log10(cm/hr) -> log10(m/s)
LOG10_KPA_TO_M = np.log10(9.80665)  # alpha in kPa-1 -> m-1 of water head (1 m of water = 9.80665 kPa)


def config() -> dict:
    return yaml.safe_load(CFG.read_text())


def usda_texture(clay, sand, silt) -> np.ndarray:
    """USDA texture class (1-12, see TEXTURE; 0 where any fraction is missing) from percentages that are first
    rescaled to sum to 100."""
    clay, sand, silt = (np.asarray(v, dtype="float64") for v in (clay, sand, silt))
    tot = clay + sand + silt
    ok = np.isfinite(tot) & (tot > 0)
    with np.errstate(invalid="ignore", divide="ignore"):
        c, s, si = (100 * v / tot for v in (clay, sand, silt))
    rules = [
        si + 1.5 * c < 15,
        si + 2 * c < 30,
        ((c >= 7) & (c < 20) & (s > 52)) | ((c < 7) & (si < 50)),
        (c >= 7) & (c < 27) & (si >= 28) & (si < 50) & (s <= 52),
        (si >= 50) & (si < 80) & (c < 27) | (si >= 80) & (c >= 12) & (c < 27),
        (si >= 80) & (c < 12),
        (c >= 20) & (c < 35) & (si < 28) & (s > 45),
        (c >= 27) & (c < 40) & (s > 20) & (s <= 45),
        (c >= 27) & (c < 40) & (s <= 20),
        (c >= 35) & (s > 45),
        (c >= 40) & (si >= 40),
        c >= 40,
    ]
    out = np.select(rules, [v for v, _, _ in TEXTURE], default=0).astype("uint8")
    return np.where(ok, out, 0).astype("uint8")


# ---------------------------------------------------------------- SOLUS100
def _solus(dom: Domain, name: str, scalar: float) -> np.ndarray:
    a = warp(dom, SOLUS.format(name=name))
    return np.where(a < 0, np.nan, a / scalar).astype("float32")


def solus_profile(dom: Domain, cfg: dict) -> xr.Dataset:
    """SOLUS100 properties on (soil_depth, y, x); soil_depth in m below the ground."""
    sc = cfg["solus"]
    z = np.array(sc["depths_cm"], float) / 100.0
    out = {}
    for name, (var, units, scalar, long_name) in sc["properties"].items():
        a = np.stack([_solus(dom, f"{name}_{d}_cm_p.tif", scalar) for d in sc["depths_cm"]])
        da = xr.DataArray(
            a,
            dims=("soil_depth", "y", "x"),
            coords={"soil_depth": z, "y": dom.y, "x": dom.x},
            name=var,
            attrs={"units": units, "long_name": f"{long_name}, SOLUS100 prediction"},
        )
        out[var] = provenance(da, cfg["source_keys"]["solus"], var, 100)
        log.info("SOLUS %-10s %s", name, np.round(np.nanpercentile(a, [5, 50, 95]), 2))
    ds = xr.Dataset(out)
    ds["soil_depth"].attrs = {"units": "m", "long_name": "depth below the ground (SOLUS prediction depth)"}
    return ds


def depth_to_restriction(dom: Domain, cfg: dict) -> xr.DataArray:
    a = _solus(dom, cfg["solus"]["restriction"], 100.0)  # cm -> m
    return _da(
        dom,
        a,
        "depth_to_restriction",
        {"units": "m", "long_name": "depth to any restrictive layer, SOLUS100 prediction"},
        cfg["source_keys"]["solus"],
        "depth_to_restriction",
        100,
    )


def mean_over_points(da: xr.DataArray, top: float, bottom: float) -> np.ndarray:
    """Depth-weighted mean of point predictions between ``top`` and ``bottom`` (m), trapezoidal in depth, over
    the intervals with a value at both ends. SOLUS leaves depths below the lithic contact empty, so in shallow
    soils this is the mean of the soil column; with the top value alone, it is that value. NaN where the top
    depth has no value."""
    z = da["soil_depth"].values
    if top not in z or bottom not in z:
        raise ValueError(f"summary range {top}-{bottom} m must be prediction depths {z}")
    sub = da.sel(soil_depth=slice(top, bottom))
    v = sub.values
    dz = np.diff(sub.soil_depth.values)[:, None, None]
    both = np.isfinite(v[:-1]) & np.isfinite(v[1:])
    num = np.sum(np.where(both, (v[:-1] + v[1:]) / 2 * dz, 0.0), axis=0)
    den = np.sum(both * dz, axis=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        out = np.where(den > 0, num / den, v[0])
    return np.where(np.isfinite(v[0]), out, np.nan).astype("float32")


def solus_summaries(dom: Domain, prof: xr.Dataset, cfg: dict) -> dict[str, xr.DataArray]:
    top, bottom = (v / 100.0 for v in cfg["summary_cm"])
    tag = f"{cfg['summary_cm'][0]}_{cfg['summary_cm'][1]}cm"
    keys = cfg["source_keys"]["solus"] + cfg["source_keys"]["summary"]
    rng = tag.replace("_", "-")
    out = {}
    for var in prof.data_vars:
        a = mean_over_points(prof[var], top, bottom)
        ln = f"{prof[var].attrs['long_name']}, depth-weighted mean {rng}"
        out[f"{var}_{tag}"] = _da(
            dom, a, f"{var}_{tag}", {"units": prof[var].attrs["units"], "long_name": ln}, keys, var, 100
        )
    t = usda_texture(*(out[f"{v}_{tag}"].values for v in ("clay", "sand", "silt")))
    out["soil_texture_class"] = _da(
        dom,
        t,
        "soil_texture_class",
        {
            "long_name": f"USDA texture class of the {rng} mean clay, sand and silt (SOLUS100)",
            "flag_values": [v for v, _, _ in TEXTURE],
            "flag_meanings": " ".join(lab.lower().replace(" ", "_") for _, lab, _ in TEXTURE),
        },
        keys,
        "soil_texture_class",
        100,
    )
    return out


def summary(layers: dict, cfg: dict, ice: np.ndarray | None) -> dict:
    """Numbers quoted for the soil layers (paper Sect. "Soil properties, regolith and Vs30"): valid share,
    percentiles, texture-class shares, Vs30 class values and the cross-checks between sources."""

    def pct(a):
        a = np.asarray(a, float)
        ok = np.isfinite(a)
        q = np.percentile(a[ok], [5, 50, 95]).tolist()
        return {"valid_pct": round(100 * ok.mean(), 1), "p5_p50_p95": q}

    out = {k: pct(v.values) for k, v in layers.items() if k != "soil_texture_class"}
    t = layers["soil_texture_class"].values
    n = int((t > 0).sum())
    out["soil_texture_class"] = {lab: round(100 * float((t == v).sum()) / n, 1) for v, lab, _ in TEXTURE}
    v = np.round(layers["vs30"].values)
    vals, cnt = np.unique(v[np.isfinite(v)], return_counts=True)
    top = np.argsort(-cnt)[:2]
    out["vs30_most_frequent_pct"] = {int(vals[i]): round(100 * cnt[i] / v.size, 1) for i in top}
    st, dtb, rd = (layers[k].values for k in ("soil_thickness", "depth_to_bedrock", "depth_to_restriction"))
    ok = np.isfinite(st) & np.isfinite(dtb) & (st > 0)
    ok2 = np.isfinite(st) & np.isfinite(rd)
    phi = 1 - layers["bulk_density_0_100cm"].values / cfg["grain_density_gcm3"]
    ths = layers["theta_s_0_100cm"].values
    ok3 = np.isfinite(phi) & np.isfinite(ths)
    wt = layers["water_table_depth"].values if "water_table_depth" in layers else np.full(st.shape, np.nan)
    ok4 = ok & np.isfinite(wt)
    out["checks"] = {
        "bedrock_over_soil_thickness_median": round(float(np.median(dtb[ok] / st[ok])), 1),
        "bedrock_deeper_than_5m_pct": round(100 * float(np.mean(dtb[np.isfinite(dtb)] > 5)), 1),
        "restriction_above_lithic_contact_pct": round(
            100 * float(np.mean(st[ok2] - rd[ok2] > cfg["restriction_margin_m"])), 1
        ),
        "porosity_from_bulk_density_median": round(float(np.median(phi[ok3])), 2),
        "theta_s_median": round(float(np.median(ths[ok3])), 2),
        "porosity_theta_s_r": round(float(np.corrcoef(phi[ok3], ths[ok3])[0, 1]), 2),
        "glacier_cells_pct": None if ice is None else round(100 * float(np.mean(ice)), 1),
        # Ma et al. (2026) water table below the SOLUS soil and above the SoilGrids bedrock
        "water_table_between_soil_and_bedrock_pct": (
            round(100 * float(np.mean((wt[ok4] > st[ok4]) & (wt[ok4] < dtb[ok4]))), 1) if ok4.any() else None
        ),
    }
    return out


def mask_ice(obj, ice: np.ndarray):
    """No soil where the glacier stack has ice (IceBoost thickness > 0): NaN, or 0 for the texture class."""
    if obj.dtype == np.uint8:
        return obj.where(~ice, 0).astype("uint8")
    return obj.where(~ice)


# ---------------------------------------------------------------- POLARIS
def polaris_profile(dom: Domain, cfg: dict) -> xr.Dataset:
    """POLARIS layer means on (polaris_layer, y, x). Log-space variables are block-averaged in log space, so
    ksat and alpha are geometric means over the 100 m cell."""
    pc = cfg["polaris"]
    tops = np.array([t for t, _ in pc["layers_cm"]], float) / 100.0
    bots = np.array([b for _, b in pc["layers_cm"]], float) / 100.0
    out = {}
    for name, (var, units, long_name) in pc["variables"].items():
        a = np.stack([warp(dom, pc["url"].format(var=name, top=t, bottom=b)) for t, b in pc["layers_cm"]])
        a = np.where(a < -9000, np.nan, a)
        if name == "ksat":
            a = a + LOG10_CMHR_TO_MS
        elif name == "alpha":
            a = a + LOG10_KPA_TO_M
        da = xr.DataArray(
            a.astype("float32"),
            dims=("polaris_layer", "y", "x"),
            coords={"polaris_layer": np.arange(len(tops)), "y": dom.y, "x": dom.x},
            name=var,
            attrs={"units": units, "long_name": f"{long_name}, POLARIS layer mean"},
        )
        out[var] = provenance(da, cfg["source_keys"]["polaris"], var, 30)
        log.info("POLARIS %-8s %s", name, np.round(np.nanpercentile(a, [5, 50, 95]), 3))
    ds = xr.Dataset(out)
    ds = ds.assign_coords(
        layer_top=("polaris_layer", tops, {"units": "m", "long_name": "top of the layer below the ground"}),
        layer_bottom=("polaris_layer", bots, {"units": "m", "long_name": "bottom of the layer"}),
    )
    return ds


def polaris_summaries(dom: Domain, prof: xr.Dataset, cfg: dict) -> dict[str, xr.DataArray]:
    """Thickness-weighted means over summary_cm; ksat as the harmonic mean (layers in series, vertical
    flow)."""
    top, bottom = (v / 100.0 for v in cfg["summary_cm"])
    tag = f"{cfg['summary_cm'][0]}_{cfg['summary_cm'][1]}cm"
    t, b = prof.layer_top.values, prof.layer_bottom.values
    d = np.clip(np.minimum(b, bottom) - np.maximum(t, top), 0, None)[:, None, None]
    keys = cfg["source_keys"]["polaris"] + cfg["source_keys"]["summary"]
    k = 10.0 ** prof["log10_ksat"].values
    ksat = np.log10(d.sum() / np.sum(d / k, axis=0)).astype("float32")
    theta_s = (np.sum(d * prof["theta_s"].values, axis=0) / d.sum()).astype("float32")
    rng = tag.replace("_", "-")
    return {
        f"log10_ksat_{tag}": _da(
            dom,
            ksat,
            f"log10_ksat_{tag}",
            {"units": "log10(m s-1)", "long_name": f"saturated hydraulic conductivity, harmonic mean {rng}"},
            keys,
            "log10_ksat",
            30,
        ),
        f"theta_s_{tag}": _da(
            dom,
            theta_s,
            f"theta_s_{tag}",
            {"units": "m3 m-3", "long_name": f"saturated water content (porosity), mean {rng}"},
            keys,
            "theta_s",
            30,
        ),
    }


# ---------------------------------------------------------------- depth to bedrock, Vs30
def depth_to_bedrock(dom: Domain, cfg: dict) -> xr.DataArray:
    """Shangguan et al. (2017) absolute depth to bedrock (cm -> m), from a window of the global grid cached
    once."""
    c = cfg["depth_to_bedrock"]
    src = _clip_to_cache(dom, c["url"], dom.path("raw") / c["cache"])
    a = warp(dom, src, Resampling.bilinear)  # 250 m -> 100 m
    a = np.where(a < 0, np.nan, a / 100.0).astype("float32")
    return _da(
        dom,
        a,
        "depth_to_bedrock",
        {"units": "m", "long_name": "depth to bedrock (R horizon), SoilGrids250m 2017"},
        cfg["source_keys"]["depth_to_bedrock"],
        "depth_to_bedrock",
        250,
    )


def fetch_vs30(dom: Domain, cfg: dict) -> str:
    """Window of the USGS global hybrid Vs30 grid (HDF5/netCDF, 30 arcsec) read by HTTP range requests and
    cached as a GeoTIFF; the host's certificate chain needs the certifi bundle."""
    import ssl

    import certifi
    import fsspec
    from rasterio.transform import from_origin

    c = cfg["vs30"]
    cache = dom.path("raw") / c["cache"]
    if cache.exists():
        return str(cache)
    w, s, e, n = dom.bbox_4326
    pad = 0.05
    fs = fsspec.filesystem("https", ssl=ssl.create_default_context(cafile=certifi.where()))
    with fs.open(c["url"], block_size=2**20) as f, xr.open_dataset(f, engine="h5netcdf") as ds:
        sub = ds["z"].sel(lon=slice(w - pad, e + pad), lat=slice(s - pad, n + pad)).load()
    sub = sub.sortby("lat", ascending=False)
    dx = float(abs(sub.lon[1] - sub.lon[0]))
    a = sub.values.astype("float32")
    tr = from_origin(float(sub.lon[0]) - dx / 2, float(sub.lat[0]) + dx / 2, dx, dx)
    cache.parent.mkdir(parents=True, exist_ok=True)
    prof = dict(driver="GTiff", width=a.shape[1], height=a.shape[0], count=1, dtype="float32", nodata=np.nan)
    with rasterio.open(cache, "w", **prof, crs="EPSG:4326", transform=tr, compress="deflate") as out:
        out.write(a, 1)
    log.info("cached Vs30 window %dx%d -> %s", a.shape[1], a.shape[0], cache)
    return str(cache)


def vs30(dom: Domain, cfg: dict) -> xr.DataArray:
    a = warp(dom, fetch_vs30(dom, cfg), Resampling.bilinear)  # ~900 m -> 100 m
    a = np.where(a > 0, a, np.nan).astype("float32")
    return _da(
        dom,
        a,
        "vs30",
        {"units": "m s-1", "long_name": "time-averaged shear-wave speed of the top 30 m (USGS hybrid map)"},
        cfg["source_keys"]["vs30"],
        "vs30",
        900,
    )
