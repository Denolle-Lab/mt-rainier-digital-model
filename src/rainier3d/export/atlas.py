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
        "Hydrothermal alteration, surface rock",
        "Geology",
        "index 0 to 1",
        0,
        1,
        "cmc.bilbao_r",
        False,
        "From the 1996 helicopter EM survey (Finn et al. 2001): low apparent resistivity of the edifice "
        "lavas, "
        "top ~20-150 m below the glacier bed; transparent below 0.1 and outside the survey",
    ),
    "apparent_magnetization": (
        "apparent_magnetization",
        "Apparent magnetisation (terrain-correlated)",
        "Geology",
        "A/m",
        -1,
        5,
        "cmc.vik",
        False,
        "Reduced-to-pole anomaly of the 1996 survey regressed on the terrain effect, 500 m window; "
        "low values mark demagnetised (altered) or reversed rock",
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
        if key == "alteration_surface" and "alt_a_surface" in s:  # S22 map at the surface resolution
            cov = (
                s["alt_coverage"].values > 0
                if "alt_coverage" in s
                else np.isfinite(s["alt_a_surface"].values)
            )
            a = s["alt_a_surface"].values  # drape only altered ground (>= 0.1) so the imagery shows elsewhere
            out[key] = np.where(cov & (a >= 0.1), a, np.nan)
            continue
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
                ["cvm17", "crescent_gen0", "dnr_gems_100k"]
                if key == "vs_top"
                else ["finn_2001", "rystrom_2000"]
                if "alt_a_surface" in s
                else ["finn_2001", "john_2008"]
            )
        if key == "apparent_magnetization":
            keys = ["finn_2001", "rystrom_2000"]
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
        "model": "rainier3d M1 (Denolle-Lab/mt-rainier-digital-model)",
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


# ---- subsurface volume for the viewer's section and depth slice ----
# name: (label, units, vmin, vmax, colormap); "unit" is categorical (byte = unit code)
VOLUME_VARS = {
    "vs": ("Vs", "m/s", 300, 4200, "cmc.roma"),
    "vp": ("Vp", "m/s", 1500, 7200, "cmc.roma"),
    "vpvs": ("Vp/Vs", "", 1.5, 2.3, "cmc.vik"),
    "rho": ("Density", "kg/m³", 1800, 3100, "cmc.lapaz_r"),
    "alteration": ("Hydrothermal alteration", "0-1", 0, 1, "cmc.bilbao_r"),
    "unit": ("Model units", "", 0, 0, None),
}


def scene_frame(atlas: Path) -> dict:
    """The viewer's local frame (equirectangular km around LON0, LAT0; x east, z south), from its bundle."""
    t = json.loads((atlas / "terrain" / "terrain.json").read_text())
    b = json.loads((atlas / "manifest.json").read_text())["extent"]["overview"]
    kx = t["cols"] * t["dx"] / (b["east"] - b["west"])
    kz = t["rows"] * t["dz"] / (b["north"] - b["south"])
    return {"lon0": b["west"] - t["x0"] / kx, "lat0": b["north"] + t["z0"] / kz, "kx": kx, "kz": kz}


def _quad_fit(fr: dict, dom, target) -> list[float]:
    """Coefficients of target(x, z) ~ c0 + c1 x + c2 z + c3 x^2 + c4 x z + c5 z^2 (x, z in scene km).
    UTM is not linear in the scene frame (grid convergence ~0.9 deg); the quadratic is good to < 1 m here."""
    from pyproj import Transformer

    lon0, lat0, lon1, lat1 = dom.bbox_4326
    lon, lat = np.meshgrid(
        np.linspace(lon0 - 0.05, lon1 + 0.05, 80), np.linspace(lat0 - 0.05, lat1 + 0.05, 80)
    )
    x, z = (lon - fr["lon0"]) * fr["kx"], -(lat - fr["lat0"]) * fr["kz"]
    e, n = Transformer.from_crs(4326, dom.crs, always_xy=True).transform(lon, lat)
    A = np.c_[np.ones(x.size), x.ravel(), z.ravel(), x.ravel() ** 2, (x * z).ravel(), z.ravel() ** 2]
    c, *_ = np.linalg.lstsq(A, target(e, n).ravel(), rcond=None)
    err = np.abs(A @ c - target(e, n).ravel()).max()
    return [float(v) for v in c], float(err)


def export_volume(tree: xr.DataTree, dom, atlas: Path, dx: float = 500.0, dz: float = 250.0) -> dict:
    """model.zarr -> <atlas>/model/volume/: one uint8 cube per property on a uniform UTM grid (x fastest,
    then y south->north, then z top->down); 255 = air. volume.json maps scene (x, z) km to texture (u, v)
    by quadratic fits and elevation to r linearly."""
    from rainier3d.export.grids import uniform

    out = atlas / "model" / "volume"
    out.mkdir(parents=True, exist_ok=True)
    g = uniform(tree, dx=dx, dz=dz, z_bot=-20000.0, variables=("vp", "vs", "rho", "alteration"))
    air = g["air"].values.astype(bool)
    g["vpvs"] = g["vp"] / g["vs"]
    # units: nearest cell of the level that holds each depth (categorical, never interpolated)
    unit = np.zeros(air.shape, np.uint8)
    for lev in ("L1", "L2", "L3"):
        ds = tree[lev].to_dataset()
        half = ds.attrs["dz"] / 2
        sel = (g.z.values <= float(ds.z.max()) + half) & (g.z.values >= float(ds.z.min()) - half)
        if sel.any():
            u = ds["unit"].sel(z=g.z.values[sel], y=g.y.values, x=g.x.values, method="nearest")
            unit[sel] = u.transpose("z", "y", "x").values.astype(np.uint8)
    nz, ny, nx = air.shape
    fr = scene_frame(atlas)
    xe, ye = float(g.x[0]) - dx / 2, float(g.y[0]) - dx / 2
    cu, eu = _quad_fit(fr, dom, lambda e, n: (e - xe) / (nx * dx))
    cv, ev = _quad_fit(fr, dom, lambda e, n: (n - ye) / (ny * dx))
    meta = {
        "grid": {
            "nx": nx,
            "ny": ny,
            "nz": nz,
            "dx_m": dx,
            "dz_m": dz,
            "x_edge": xe,
            "y_edge": ye,
            "z_top_m": float(g.z[0]) + dz / 2,
            "crs": dom.crs,
        },
        "uv_poly": {
            "u": cu,
            "v": cv,
            "terms": "1, x, z, x^2, x z, z^2 (scene km)",
            "max_error_cells": max(eu * nx, ev * ny),
        },
        "vars": {},
        "source": "rainier3d model.zarr via export.grids.uniform (linear within levels; units nearest)",
    }
    for key, (label, units, vmin, vmax, cmap) in VOLUME_VARS.items():
        if key == "unit":
            q = np.where(air, 255, unit).astype(np.uint8)
            lut = [[0, 0, 0]] * 256
            for u_, col in UNIT_COLORS.items():
                lut[u_] = [int(col[i : i + 2], 16) for i in (1, 3, 5)]
            classes = [
                {"value": int(u_), "label": UNIT_LABELS.get(u_, str(u_)), "color": UNIT_COLORS[u_]}
                for u_ in sorted(set(np.unique(q)) - {0, 255})
                if u_ in UNIT_COLORS
            ]
            legend = {"classes": classes}
        else:
            v = g[key].values
            # air keeps the rock value below it (as in grids.uniform): the viewer hides everything above the
            # ground, and linear filtering must not blend a no-data code into the top rock cells
            q = np.where(~np.isfinite(v), 255, np.clip(np.rint(254 * (v - vmin) / (vmax - vmin)), 0, 254))
            q = q.astype(np.uint8)
            cm = _cmap(cmap)
            lut = [[int(c * 255) for c in cm(min(i, 254) / 254)[:3]] for i in range(256)]
            legend = {"min": vmin, "max": vmax, "log": False, "ramp": _ramp(cm)}
        q.tofile(out / f"{key}.u8")
        meta["vars"][key] = {
            "label": label,
            "units": units,
            "file": f"volume/{key}.u8",
            "kind": "categorical" if key == "unit" else "continuous",
            "lut": lut,
            "legend": legend,
            "vmin": vmin,
            "vmax": vmax,
        }
    (out.parent / "volume.json").write_text(json.dumps(meta))
    return meta


# ---- strain in the volume (S24): extra subsurface properties and orientation bars on the depth slice ----
# key: label, units, min, max, colour map, scale to the display unit, bar set drawn on the depth slice, note
STRAIN_VOLUME_VARS = {
    "load_volumetric": (
        "Edifice-load volumetric strain",
        "microstrain",
        -600,
        0,
        "cmc.lajolla",
        1e6,
        "load",
        "Static strain of the edifice weight (compression negative). Bars: SHmax of the load.",
    ),
    "load_max_shear_h": (
        "Edifice-load horizontal shear strain",
        "microstrain",
        0,
        20,
        "cmc.batlow",
        1e6,
        "load",
        "Static strain of the edifice weight. Bars: SHmax of the load.",
    ),
    "tect_areal_rate": (
        "GNSS areal strain rate",
        "nanostrain/yr",
        -30,
        30,
        "cmc.vik",
        1e9,
        "tectonic",
        "GNSS surface field carried down unchanged (assumption). Bars: axis of maximum shortening.",
    ),
    "tect_max_shear_rate": (
        "GNSS maximum shear strain rate",
        "nanostrain/yr",
        0,
        25,
        "cmc.lajolla",
        1e9,
        "tectonic",
        "GNSS surface field carried down unchanged (assumption). Bars: axis of maximum shortening.",
    ),
    "wrsz_shear_rate": (
        "Right-lateral shear rate on WRSZ-parallel planes",
        "nanostrain/yr",
        -20,
        20,
        "cmc.vik",
        1e9,
        "tectonic",
        "Resolved on vertical planes parallel to the WRSZ epicentres. Bars: axis of maximum shortening.",
    ),
}


def export_strain(strain: xr.Dataset, dom, atlas: Path, spacing_cells=(10, 4), load_radius_m=20000.0) -> dict:
    """Append the S24 strain fields to <atlas>/model/volume.json (same grid as export_volume) and write
    <atlas>/model/strain_bars.json: orientation bars (scene km) every 1 km of elevation, tectonic and load."""
    from pyproj import Transformer

    out = atlas / "model"
    meta = json.loads((out / "volume.json").read_text())
    g = meta["grid"]
    if strain.sizes["x"] != g["nx"] or strain.sizes["y"] != g["ny"] or strain.sizes["z"] != g["nz"]:
        raise ValueError(
            "strain_3d.zarr is not on the viewer volume grid; rerun S24 with the same dx, dz, z_bot"
        )
    for key, (label, units, vmin, vmax, cmap, scale, bars, note) in STRAIN_VOLUME_VARS.items():
        v = strain[key].transpose("z", "y", "x").values * scale
        q = np.where(~np.isfinite(v), 255, np.clip(np.rint(254 * (v - vmin) / (vmax - vmin)), 0, 254)).astype(
            np.uint8
        )
        q.tofile(out / "volume" / f"{key}.u8")
        cm = _cmap(cmap)
        meta["vars"][key] = {
            "label": label,
            "units": units,
            "file": f"volume/{key}.u8",
            "kind": "continuous",
            "lut": [[int(c * 255) for c in cm(min(i, 254) / 254)[:3]] for i in range(256)],
            "legend": {"min": vmin, "max": vmax, "log": False, "ramp": _ramp(cm)},
            "vmin": vmin,
            "vmax": vmax,
            "bars": bars,
            "note": note,
        }
    fr = scene_frame(atlas)
    inv = Transformer.from_crs(dom.crs, 4326, always_xy=True)
    sx, sy = dom.summit_xy
    step_m = g["dx_m"]

    def scene(x, y):
        lon, lat = inv.transform(x, y)
        return (np.asarray(lon) - fr["lon0"]) * fr["kx"], (fr["lat0"] - np.asarray(lat)) * fr["kz"]

    top, bottom = float(strain.z.max()) / 1000, float(strain.z.min()) / 1000  # the grid as exported
    levels = np.arange(np.floor(top), np.ceil(bottom) - 0.5, -1.0)
    sets = {"tectonic": [], "load": []}
    for zk in levels:
        lev = strain.sel(z=zk * 1000, method="nearest")
        for kind, az_key, step in (
            ("tectonic", "tect_az_shortening", spacing_cells[0]),
            ("load", "load_shmax_az", spacing_cells[1]),
        ):
            sub = lev.isel(x=slice(step // 2, None, step), y=slice(step // 2, None, step))
            X, Y = np.meshgrid(sub.x.values, sub.y.values)
            az = np.radians(sub[az_key].values)
            keep = np.isfinite(az)
            if kind == "load":
                keep &= np.hypot(X - sx, Y - sy) <= load_radius_m
            half = 0.4 * step * step_m
            x0, y0 = X[keep] - half * np.sin(az[keep]), Y[keep] - half * np.cos(az[keep])
            x1, y1 = X[keep] + half * np.sin(az[keep]), Y[keep] + half * np.cos(az[keep])
            a, b = scene(x0, y0)
            c, d = scene(x1, y1)
            sets[kind].append(np.round(np.column_stack([a, b, c, d]).ravel(), 3).tolist())
    bars = {
        "levels_km": levels.tolist(),
        **sets,
        "note": "segments x0, z0, x1, z1 in scene km, one list per level; tectonic: GNSS shortening axis; "
        "load: SHmax of the edifice load (none in the cone interior)",
    }
    (out / "strain_bars.json").write_text(json.dumps(bars, separators=(",", ":")))
    meta["bars"] = "strain_bars.json"
    (out / "volume.json").write_text(json.dumps(meta))
    return {
        "vars": list(STRAIN_VOLUME_VARS),
        "levels": len(levels),
        "segments": {k: sum(len(v) // 4 for v in s) for k, s in sets.items()},
    }


# ---- sensors: every site of the S8 inventory, for the viewer's sensor layer ----
# Temporary networks follow the FDSN convention (codes starting with a digit or X, Y, Z are temporary);
# TA is a permanent code for a moving deployment. Non-FDSN sources are classed by what they are.
TEMP_CODES = {"TA"}
TEMP_SOURCES = ("2025 Rainier node deployment",)


def is_temporary(site_id: str, source: str) -> bool:
    if source.startswith(TEMP_SOURCES):
        return True
    if source.startswith("FDSN"):
        net = site_id.split(".")[0]
        return net[:1].isdigit() or net[:1] in "XYZ" or net in TEMP_CODES
    return False


def viewer_kind(kind: str, family: str) -> str:
    """Our instrument kind or family -> the viewer's kinds (web/viewer/site/src/data/kinds.js)."""
    k = kind.lower()
    for key, words in (
        ("geophone", ("geophone", "node")),
        ("accelerometer", ("accelerometer",)),
        ("infrasound", ("infrasound",)),
        ("gnss", ("gnss",)),
        ("tiltmeter", ("tilt",)),
        ("strainmeter", ("strainmeter",)),
        ("seismometer", ("seismometer",)),
    ):
        if any(w in k for w in words):
            return key
    return {
        "meteorology": "hydromet",
        "hydrology": "hydromet",
        "nodes": "geophone",
        "strong": "accelerometer",
        "seismic": "seismometer",
        "gnss": "gnss",
        "infrasound": "infrasound",
    }.get(family, "other")


def export_sensors(atlas: Path, web_data: Path) -> dict:
    """S8's web/atlas/data/{sites,das}.geojson -> <atlas>/model/sensors.json in the viewer's scene frame.
    Deployers' names are left out of the public file."""
    fr = scene_frame(atlas)
    to_x = lambda lon: (lon - fr["lon0"]) * fr["kx"]  # noqa: E731
    to_z = lambda lat: -(lat - fr["lat0"]) * fr["kz"]  # noqa: E731
    sites = []
    for f in json.loads((web_data / "sites.geojson").read_text())["features"]:
        p, (lon, lat) = f["properties"], f["geometry"]["coordinates"][:2]
        sensors = json.loads(p.get("sensors") or "[]")
        kinds = sorted(
            {viewer_kind(s.get("kind", ""), s.get("family", p["family"])) for s in sensors}
            or {viewer_kind("", p["family"])}
        )
        starts = [s["start"] for s in sensors if s.get("start")]
        ends = [s["end"] for s in sensors if s.get("end")]
        sites.append(
            {
                "id": p["id"],
                "name": p["name"],
                "lon": round(lon, 6),
                "lat": round(lat, 6),
                "x": round(to_x(lon), 4),
                "z": round(to_z(lat), 4),
                "elev": p.get("elev"),
                "kinds": kinds,
                "source": p["source"],
                "temporary": is_temporary(p["id"], p["source"]),
                "status": p["status"],
                "start": min(starts) if starts else None,
                "end": None if p["status"] == "operating" else (max(ends) if ends else None),
                "instruments": sorted({s.get("kind", "") for s in sensors} - {""}),
                "notes": p.get("notes") or "",
                "url": p.get("url") or "",
            }
        )
    das, ch = [], 0
    for f in json.loads((web_data / "das.geojson").read_text())["features"]:
        ch = max(ch, int(f["properties"].get("ch1", -1)) + 1)
        g = f["geometry"]
        lines = g["coordinates"] if g["type"] == "MultiLineString" else [g["coordinates"]]
        for ln in lines:
            das.append([[round(to_x(c[0]), 4), round(to_z(c[1]), 4)] for c in ln])
    counts = {}
    for s in sites:
        for k in s["kinds"]:
            key = f"{k}|{'temporary' if s['temporary'] else 'permanent'}|{s['status']}"
            counts[key] = counts.get(key, 0) + 1
    # reviewed notes per station code (configs/sensor_notes.yaml), attached to the site that holds the station
    import yaml

    from rainier3d.config.domain import REPO

    notes_cfg = yaml.safe_load((REPO / "configs" / "sensor_notes.yaml").read_text()) or {}
    for s in sites:
        codes = [c.strip() for c in s["name"].split("+")] + [s["id"]]
        extra = [notes_cfg[c]["note"] for c in dict.fromkeys(codes) if c in notes_cfg]
        if extra:
            s["notes"] = " ".join([*extra, s["notes"]]).strip()
    meta = {
        "sites": sites,
        "notes": {k: v["note"] for k, v in notes_cfg.items()},
        "das": {
            "name": "Paradise–Nisqually Entrance DAS fiber",
            "segments": das,
            "temporary": True,
            "status": "operating",
            "channels": ch,
        },
        "counts": counts,
        "source": "rainier3d S8 sensor inventory (EarthScope FDSN, UW 2025 nodes, "
        "EarthScope GNSS, Synoptic), exported by S11",
    }
    (atlas / "model" / "sensors.json").write_text(json.dumps(meta, separators=(",", ":")))
    return meta


# ---- canopy-storage layers (S19) appended to the viewer bundle without re-exporting the model layers ----
CANOPY_STYLE = {
    "canopy_height_lidar": ("Canopy height, lidar 10 m", 0, 60, "cmc.bamako_r"),
    "vegetation_cover_lidar": ("Vegetation cover, lidar 10 m", 0, 1, "cmc.bamako_r"),
    "lai_sentinel2": ("Leaf area index, Sentinel-2 2023", 0, 6, "cmc.bamako_r"),
    "gedi_pai": ("Plant area index, GEDI L2B", 0, 6, "cmc.bamako_r"),
    "gedi_canopy_height": ("Canopy height, GEDI L3", 0, 60, "cmc.bamako_r"),
    "gedi_biomass": ("Aboveground biomass, GEDI L4B", 0, 600, "cmc.lajolla"),
    "gedi_biomass_se": ("Biomass standard error, GEDI L4B", 0, 100, "cmc.lajolla"),
}


def rgb_texture(src: str, manifest: dict, width: int = 4080) -> np.ndarray:
    """A 3-band image (any CRS) warped to the overview box; alpha 0 where all bands are 0 or 255 (masked).
    Nearest-neighbour, so a rendered map keeps its exact legend colours and its mask."""
    import rasterio

    t, w, h = overview_grid(manifest, width)
    out = np.zeros((h, w, 4), "uint8")
    with rasterio.open(src) as ds:
        for k in range(3):
            dst = np.zeros((h, w), "uint8")
            reproject(
                rasterio.band(ds, k + 1),
                dst,
                dst_transform=t,
                dst_crs="EPSG:4326",
                resampling=Resampling.nearest,
            )
            out[..., k] = dst
    rgb = out[..., :3].astype(int)
    out[..., 3] = np.where((rgb.sum(-1) == 0) | (rgb.min(-1) == 255), 0, 255)
    return out


def append_canopy_layers(atlas: Path, dom, ds: xr.Dataset, cfg: dict, keys=None) -> list[str]:
    """Add S19 layers and the soil image to <atlas>/model/layers.json, replacing same-key entries.
    ``keys`` limits the update to those layers (default: all)."""
    from rainier3d.surface.canopy import source_path

    out = atlas / "model"
    manifest = json.loads((atlas / "manifest.json").read_text())
    meta = json.loads((out / "layers.json").read_text())
    reg, specs = _sources(), {s["name"]: s for s in cfg["layers"]}
    new = []
    for key, (label, vmin, vmax, cmap) in CANOPY_STYLE.items():
        if key not in ds or (keys is not None and key not in keys):
            continue
        a = ds[key].values.astype("float32")
        tex, val = (
            to_lonlat(a, dom, manifest, TEX_WIDTH, False),
            to_lonlat(a, dom, manifest, VAL_WIDTH, False),
        )
        cm = _cmap(cmap)
        rgba = (cm(np.nan_to_num(_norm(tex, vmin, vmax, False))) * 255).astype("uint8")
        rgba[..., 3] = np.where(np.isfinite(tex), 255, 0)
        tname = _save_texture(rgba, out / key, False)
        q, scale, offset = _values_u16(val, False, vmin, vmax)
        q.tofile(out / f"{key}.u16.bin")
        sk = specs[key]["source"]
        new.append(
            {
                "key": key,
                "label": label,
                "group": "Canopy (canopy-storage project)",
                "kind": "continuous",
                "units": ds[key].attrs.get("units", ""),
                "note": specs[key]["long_name"],
                "texture": tname,
                "values": {
                    "file": f"{key}.u16.bin",
                    "width": q.shape[1],
                    "height": q.shape[0],
                    "scale": scale,
                    "offset": offset,
                    "nodata": 65535,
                },
                "legend": {"min": vmin, "max": vmax, "log": False, "ramp": _ramp(cm)},
                "sources": [{"key": sk, "title": reg[sk]["title"], "link": _link(reg[sk])}],
            }
        )
    for im in cfg.get("images", []):
        if keys is not None and im["name"] not in keys:
            continue
        src = source_path(im, Path(cfg["root"]).expanduser())
        if not src.exists():
            continue
        src = str(src)
        tname = _save_texture(rgb_texture(src, manifest), out / im["name"], False)
        new.append(
            {
                "key": im["name"],
                "label": im["label"],
                "group": "Soil",
                "kind": "image",
                "units": "",
                "note": im["note"],
                "texture": tname,
                "values": None,
                "legend": {},
                "sources": [{"key": im["source"], "title": reg[im["source"]]["title"], "link": ""}],
            }
        )
    keys = {n["key"] for n in new}
    meta["layers"] = [x for x in meta["layers"] if x["key"] not in keys] + new
    (out / "layers.json").write_text(json.dumps(meta, indent=1))
    return sorted(keys)
