"""Surface layers of model.zarr -> a data bundle for the Rainier seismic atlas front end (Derek Yao's site).

The atlas drapes lon/lat textures on an equirectangular overview box (``manifest.json`` extent.overview),
so every layer is reprojected here from the UTM model grid onto that box with square-degree pixels:

  <out>/layers.json          list of layers: label, units, legend (ramp or classes), source, file names
  <out>/<key>.png            RGBA drape texture, TEX_WIDTH wide; alpha 0 outside the model or with no data
  <out>/<key>.u16.bin        values for the hover readout on a VAL_WIDTH-wide grid; 65535 = no data
                             (continuous: v = offset + q * scale; categorical: q is the class code)
  <out>/streams.png          NHDPlus flowlines drawn by Strahler order, for the stream toggle

Textures show the model grid (100 m cells) as stored; nothing is re-read from the original sources here.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib
import numpy as np
import xarray as xr
from affine import Affine
from PIL import Image, ImageDraw
from rasterio.warp import Resampling, reproject

from rainier3d.report.figures import UNIT_COLORS

TEX_WIDTH = 2040
VAL_WIDTH = 1020

UNIT_LABELS = {
    1: "Glacier ice",
    2: "Water",
    3: "Glacial drift",
    4: "Alluvium and colluvium",
    5: "Lahar deposits",
    6: "Mount Rainier andesite",
    7: "Younger volcanic rocks",
    8: "Miocene intrusive rocks",
    9: "Miocene volcanic rocks",
    10: "Ohanapecosh Formation",
    11: "Eocene volcanic rocks",
    12: "Puget Group and Eocene sedimentary rocks",
    13: "Mashel Formation",
    14: "Russell Ranch Formation",
}

# USGS NLCD legend (class: label, color)
NLCD = {
    11: ("Open water", "#466b9f"),
    12: ("Perennial ice and snow", "#d1def8"),
    21: ("Developed, open space", "#dec5c5"),
    22: ("Developed, low intensity", "#d99282"),
    23: ("Developed, medium intensity", "#eb0000"),
    24: ("Developed, high intensity", "#ab0000"),
    31: ("Barren land", "#b3ac9f"),
    41: ("Deciduous forest", "#68ab5f"),
    42: ("Evergreen forest", "#1c5f2c"),
    43: ("Mixed forest", "#b5c58f"),
    52: ("Shrub/scrub", "#ccb879"),
    71: ("Grassland/herbaceous", "#dfdfc2"),
    81: ("Pasture/hay", "#dcd939"),
    82: ("Cultivated crops", "#ab6c28"),
    90: ("Woody wetlands", "#b8d9eb"),
    95: ("Emergent herbaceous wetlands", "#6c9fb8"),
}

# key: (variable, label, group, units, vmin, vmax, colormap, log, note)
CONTINUOUS = {
    "ice_thickness": (
        "ice_thickness",
        "Glacier ice thickness",
        "Cryosphere",
        "m",
        0,
        250,
        "cmc.oslo_r",
        False,
        "IceBoost v2, rescaled to each glacier's volume",
    ),
    "soil_thickness": (
        "soil_thickness",
        "Soil thickness",
        "Soil",
        "m",
        0,
        2.01,
        "cmc.lajolla",
        False,
        "SOLUS100 depth to lithic contact; 2.01 m means deeper than the survey",
    ),
    "water_table_depth": (
        "water_table_depth",
        "Water-table depth, Ma et al. 2026",
        "Water",
        "m below ground",
        0.1,
        100,
        "cmc.devon",
        True,
        "Random-forest estimate from ~24 m, CC-BY-NC-ND 4.0",
    ),
    "water_table_depth_fan": (
        "water_table_depth_fan",
        "Water-table depth, Fan et al. 2017",
        "Water",
        "m below ground",
        0.1,
        100,
        "cmc.devon",
        True,
        "Global model at 30 arcsec (~1 km)",
    ),
    "canopy_height": (
        "canopy_height",
        "Canopy height",
        "Ecology",
        "m",
        0,
        60,
        "cmc.bamako_r",
        False,
        "ETH global canopy height 2020, from 10 m",
    ),
    "alteration_surface": (
        "alteration_surface",
        "Hydrothermal alteration",
        "Geology",
        "index 0 to 1",
        0,
        1,
        "cmc.bilbao",
        False,
        "model alteration field in the top rock cell",
    ),
    "vs_top": (
        "vs_top",
        "Vs, top 100 m of rock",
        "Seismic model",
        "m/s",
        300,
        3000,
        "cmc.roma",
        False,
        "fused model, mean of the top 100 m below ground",
    ),
    "ndvi": (
        "ndvi",
        "Vegetation index (NDVI)",
        "Ecology",
        "",
        -0.2,
        0.9,
        "cmc.bamako_r",
        False,
        "Sentinel-2 late-summer 2025 median",
    ),
    "ndsi": (
        "ndsi",
        "Snow and ice index (NDSI)",
        "Cryosphere",
        "",
        -0.5,
        1.0,
        "cmc.oslo",
        False,
        "Sentinel-2 late-summer 2025 median; above 0.4 marks ice and perennial snow",
    ),
}


def _cmap(name: str):
    if name.startswith("cmc."):
        import cmcrameri.cm as cmc

        return getattr(cmc, name[4:])
    return matplotlib.colormaps[name]


def overview_grid(manifest: dict, width: int) -> tuple[Affine, int, int]:
    b = manifest["extent"]["overview"]
    deg = (b["east"] - b["west"]) / width
    height = int(round((b["north"] - b["south"]) / deg))
    return Affine(deg, 0, b["west"], 0, -deg, b["north"]), width, height


def to_lonlat(a: np.ndarray, dom, manifest: dict, width: int, categorical: bool) -> np.ndarray:
    """Model surface array (rows south->north) -> overview lon/lat grid (rows north->south), NaN/0 outside."""
    r = dom.surface_res_m
    x0, _, _, y1 = dom.bounds
    src = np.ascontiguousarray(a[::-1]).astype("float32")
    dst_t, w, h = overview_grid(manifest, width)
    dst = np.full((h, w), np.nan, "float32")
    reproject(
        src,
        dst,
        src_transform=Affine(r, 0, x0, 0, -r, y1),
        src_crs=dom.crs,
        src_nodata=np.nan,
        dst_transform=dst_t,
        dst_crs="EPSG:4326",
        dst_nodata=np.nan,
        resampling=Resampling.nearest if categorical else Resampling.bilinear,
    )
    return dst


def _ramp(cmap, n: int = 9) -> list[str]:
    return [matplotlib.colors.to_hex(cmap(i / (n - 1))) for i in range(n)]


def _norm(v, vmin, vmax, log):
    if log:
        v, vmin, vmax = np.log10(np.clip(v, vmin, None)), np.log10(vmin), np.log10(vmax)
    return np.clip((v - vmin) / (vmax - vmin), 0, 1)


def _save_png(rgba: np.ndarray, path: Path) -> None:
    Image.fromarray(rgba, "RGBA").save(path, optimize=True)


def _save_texture(rgba: np.ndarray, path: Path, categorical: bool) -> str:
    """Categorical layers keep exact colours (PNG); imagery and ramps go lossy WebP with alpha."""
    if categorical:
        _save_png(rgba, path.with_suffix(".png"))
        return path.with_suffix(".png").name
    Image.fromarray(rgba, "RGBA").save(path.with_suffix(".webp"), quality=88, method=6)
    return path.with_suffix(".webp").name


def _values_u16(
    v: np.ndarray, categorical: bool, vmin: float = 0, vmax: float = 1
) -> tuple[np.ndarray, float, float]:
    if categorical:
        q = np.where(np.isfinite(v) & (v > 0), v, 65535)
        return q.astype("<u2"), 1.0, 0.0
    # the stored range covers the data, not only the legend range, so the readout is never clipped
    ok = np.isfinite(v).any()
    lo = min(vmin, float(np.nanmin(v))) if ok else vmin
    hi = max(vmax, float(np.nanmax(v))) if ok else vmax
    scale = (hi - lo) / 65000.0 or 1.0
    q = np.where(np.isfinite(v), np.rint((v - lo) / scale), 65535)
    return np.clip(q, 0, 65535).astype("<u2"), scale, lo


def surface_derived(tree: xr.DataTree) -> dict[str, np.ndarray]:
    """Model-derived surface maps: alteration and Vs in the top rock cells of L1, on the surface grid."""
    s = tree["surface"].to_dataset()
    l1 = tree["L1"].to_dataset()
    depth, rock = l1["depth"].values, l1["unit"].values > 1  # rock = not air, not ice
    top = rock & (depth >= 0) & (depth <= 100)
    n = top.sum(0)
    out = {}
    for key, var in (("vs_top", "vs"), ("alteration_surface", "alteration")):
        v = np.where(top, l1[var].values, 0.0).sum(0) / np.maximum(n, 1)
        v = np.where(n > 0, v, np.nan)
        # L1 is coarser than the surface grid: repeat cells onto it
        fy, fx = s.sizes["y"] // v.shape[0], s.sizes["x"] // v.shape[1]
        out[key] = np.repeat(np.repeat(v, fy, 0), fx, 1)
    return out


def imagery_texture(src: str, manifest: dict, width: int = 4080) -> np.ndarray:
    """Sentinel-2 true colour (seis-hydro-2-sed stretch) warped from its 20 m UTM grid to the overview box."""
    import rasterio

    from rainier3d.surface.imagery import true_colour

    rgb = true_colour(src)
    with rasterio.open(src) as ds:
        st, scrs = ds.transform, ds.crs
    t, w, h = overview_grid(manifest, width)
    out = np.zeros((h, w, 4), "uint8")
    for k in range(3):
        dst = np.zeros((h, w), "uint8")
        reproject(
            rgb[..., k],
            dst,
            src_transform=st,
            src_crs=scrs,
            src_nodata=0,
            dst_transform=t,
            dst_crs="EPSG:4326",
            dst_nodata=0,
            resampling=Resampling.bilinear,
        )
        out[..., k] = dst
    out[..., 3] = np.where(out[..., :3].max(-1) > 0, 255, 0)
    return out


def export_layers(tree: xr.DataTree, dom, manifest: dict, out: Path, flowlines=None, imagery=None) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    s = tree["surface"].to_dataset()
    derived = surface_derived(tree)
    layers = []

    def emit(key, label, group, a, categorical, legend, units="", note="", keys=(), log=False):
        tex = to_lonlat(a, dom, manifest, TEX_WIDTH, categorical)
        val = to_lonlat(a, dom, manifest, VAL_WIDTH, categorical)
        if categorical:
            lut = np.zeros((256, 4), "uint8")
            for c in legend["classes"]:
                lut[c["value"]] = [*(int(c["color"][i : i + 2], 16) for i in (1, 3, 5)), 255]
            rgba = lut[np.nan_to_num(tex, nan=0).astype(int).clip(0, 255)]
        else:
            cm = _cmap(legend["cmap"])
            t = _norm(tex, legend["min"], legend["max"], log)
            rgba = (cm(np.nan_to_num(t)) * 255).astype("uint8")
            rgba[..., 3] = np.where(np.isfinite(tex), 255, 0)
        tex_name = _save_texture(rgba, out / key, categorical)
        q, scale, offset = _values_u16(val, categorical, legend.get("min", 0), legend.get("max", 1))
        q.tofile(out / f"{key}.u16.bin")
        reg = _sources()
        layers.append(
            {
                "key": key,
                "label": label,
                "group": group,
                "kind": "categorical" if categorical else "continuous",
                "units": units,
                "note": note,
                "texture": tex_name,
                "values": {
                    "file": f"{key}.u16.bin",
                    "width": q.shape[1],
                    "height": q.shape[0],
                    "scale": scale,
                    "offset": offset,
                    "nodata": 65535,
                },
                "legend": {k: v for k, v in legend.items() if k != "cmap"},
                "sources": [{"key": k, "title": reg[k].get("title", k), "link": _link(reg[k])} for k in keys],
            }
        )

    unit = s["surface_unit"].values.astype("float32")
    unit[unit == 0] = np.nan
    present = sorted({int(u) for u in np.unique(unit[np.isfinite(unit)])})
    classes = [{"value": u, "label": UNIT_LABELS.get(u, str(u)), "color": UNIT_COLORS[u]} for u in present]
    emit(
        "geology",
        "Geology (model units)",
        "Geology",
        unit,
        True,
        {"classes": classes},
        note="WA DNR 1:100k GeMS map units through the model crosswalk; ice from IceBoost",
        keys=["dnr_gems_100k", "iceboost_v2"],
    )

    for key, (var, label, group, units, vmin, vmax, cmap, log, note) in CONTINUOUS.items():
        a = derived.get(var) if var in derived else (s[var].values if var in s else None)
        if a is None:
            continue
        a = a.astype("float32")
        if key == "ice_thickness":
            a = np.where(a > 1, a, np.nan)
        keys = list(filter(None, s[var].attrs.get("gaia:source_keys", "").split(","))) if var in s else []
        if key in ("vs_top", "alteration_surface"):
            keys = (
                ["cvm17", "crescent_gen0", "dnr_gems_100k"] if key == "vs_top" else ["finn_2001", "john_2008"]
            )
        legend = {"min": vmin, "max": vmax, "log": log, "ramp": _ramp(_cmap(cmap)), "cmap": cmap}
        emit(key, label, group, a, False, legend, units, note, keys, log)

    if "land_cover" in s:
        lc = s["land_cover"].values.astype("float32")
        lc[lc == 0] = np.nan
        present = sorted({int(u) for u in np.unique(lc[np.isfinite(lc)])} & set(NLCD))
        classes = [{"value": u, "label": NLCD[u][0], "color": NLCD[u][1]} for u in present]
        emit(
            "land_cover",
            "Land cover",
            "Ecology",
            lc,
            True,
            {"classes": classes},
            keys=list(filter(None, s["land_cover"].attrs.get("gaia:source_keys", "").split(","))),
        )

    if imagery:
        s2_name = _save_texture(imagery_texture(imagery, manifest), out / "sentinel2", False)
        reg = _sources()
        layers.insert(
            0,
            {
                "key": "sentinel2",
                "label": "Sentinel-2 true colour, Aug-Sep 2025",
                "group": "Imagery",
                "kind": "image",
                "units": "",
                "texture": s2_name,
                "values": None,
                "legend": {},
                "note": "Cloud-masked median, 20 m. Contains modified Copernicus Sentinel data 2025",
                "sources": [
                    {
                        "key": "sentinel2_l2a",
                        "title": reg["sentinel2_l2a"]["title"],
                        "link": reg["sentinel2_l2a"]["url"],
                    }
                ],
            },
        )

    streams = None
    if flowlines is not None:
        streams = _streams_png(flowlines, manifest, out / "streams.png")
    meta = {
        "layers": layers,
        "streams": streams,
        "texture_width": TEX_WIDTH,
        "grid_note": f"model surface grid, {dom.surface_res_m:.0f} m cells, {dom.crs}",
        "model": "rainier3d M1 (Denolle-Lab/mt-rainier-virtual-3d-model)",
    }
    (out / "layers.json").write_text(json.dumps(meta, indent=1))
    return meta


def _streams_png(flowlines, manifest: dict, path: Path, width: int = 4080) -> dict:
    """Draw flowlines at 2x the drape width; line width and opacity grow with Strahler order."""
    t, w, h = overview_grid(manifest, width)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    g = flowlines[flowlines.streamorde.fillna(0) >= 1].to_crs(4326).sort_values("streamorde")  # NaN: no order
    inv = ~t
    for geom, order in zip(g.geometry, g.streamorde, strict=True):
        if geom is None:
            continue
        parts = geom.geoms if geom.geom_type.startswith("Multi") else [geom]
        width_px = {1: 1, 2: 1, 3: 1, 4: 2, 5: 2, 6: 3, 7: 4}.get(int(order), 5)
        alpha = min(255, 90 + 28 * int(order))
        for p in parts:
            xy = [inv * c[:2] for c in p.coords]
            d.line(xy, fill=(120, 196, 255, alpha), width=width_px, joint="curve")
    img.save(path, optimize=True)
    return {
        "texture": path.name,
        "count": int(len(g)),
        "source": "NHDPlus v2.1 flowlines (USGS/EPA)",
        "max_order": int(g.streamorde.max()),
    }


def _sources() -> dict:
    from rainier3d.io.store import sources

    return sources()


def _link(rec: dict) -> str:
    if rec.get("doi"):
        return f"https://doi.org/{rec['doi']}"
    return rec.get("url", "")
