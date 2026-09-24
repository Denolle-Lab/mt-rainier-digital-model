"""model.zarr -> compact browser files for the atlas section tool and the underground 3D view.

Each (level, variable) becomes a gzip-compressed uint8 cube in C order (z top-down, y south->north,
x west->east): q = round(254 * (v - vmin) / (vmax - vmin)), 255 = no data (air). meta.json carries the
grid of each level, the quantization range, a 256-entry colormap per variable, and the surface grid.
Surface layers (elevation, ice thickness) are int16/uint8 on the 100 m surface grid; textures for the
3D view are rendered here on the same UTM grid so browser UVs are exact.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import matplotlib
import numpy as np
import xarray as xr
from PIL import Image

from rainier3d.petro.table import unit_names

# name: (source variable or callable, vmin, vmax, units, label, colormap)
VARS = {
    "vs": ("vs", 200, 4200, "m/s", "Vs", "turbo_r"),
    "vp": ("vp", 1000, 7200, "m/s", "Vp", "turbo_r"),
    "rho": ("rho", 900, 3100, "kg/m³", "Density", "cividis"),
    "vpvs": (lambda d: d["vp"] / d["vs"], 1.5, 3.0, "", "Vp/Vs", "RdYlBu_r"),
    "qs": ("qs", 0, 250, "", "Qs", "magma"),
    "unit": ("unit", 0, 254, "", "Units", "tab20"),
    "alteration": ("alteration", 0, 1, "", "Alteration", "inferno"),
    "vs_geology": ("vs_geology", 200, 4200, "m/s", "Vs (geology only)", "turbo_r"),
    "vs_regional": ("vs_regional", 200, 4200, "m/s", "Vs (regional CVM/CRESCENT)", "turbo_r"),
    "vp_geology": ("vp_geology", 1000, 7200, "m/s", "Vp (geology only)", "turbo_r"),
    "vp_regional": ("vp_regional", 1000, 7200, "m/s", "Vp (regional CVM/CRESCENT)", "turbo_r"),
}


def _lut(name: str) -> list:
    cmap = matplotlib.colormaps[name]
    return [[int(c * 255) for c in cmap(i / 255.0)[:3]] for i in range(256)]


def _unit_lut() -> list:
    # the same colors as the section figures and model_geology overlay: tab20 at unit / 21
    cmap = matplotlib.colormaps["tab20"]
    return [[int(c * 255) for c in cmap(min(i, 21) / 21.0)[:3]] for i in range(256)]


def _quantize(a: np.ndarray, vmin: float, vmax: float, categorical: bool) -> np.ndarray:
    q = np.where(np.isfinite(a), a if categorical else np.rint(254 * (a - vmin) / (vmax - vmin)), 255)
    return np.clip(q, 0, 255).astype(np.uint8)


def _write_gz(path: Path, arr: np.ndarray) -> int:
    raw = np.ascontiguousarray(arr).tobytes()
    path.write_bytes(gzip.compress(raw, compresslevel=6))
    return path.stat().st_size


def export_model(tree: xr.DataTree, dom, out: Path, levels=("L1", "L2", "L3")) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    meta = {"crs": dom.crs, "utm_zone": 10, "levels": {}, "vars": {}, "units": {}, "bytes": 0}
    for lev in levels:
        ds = tree[lev].to_dataset()
        air = ds["unit"].values == 0
        meta["levels"][lev] = {
            "x0": float(ds.x[0]),
            "y0": float(ds.y[0]),
            "dx": float(ds.attrs["dx"]),
            "dz": float(ds.attrs["dz"]),
            "nx": int(ds.x.size),
            "ny": int(ds.y.size),
            "nz": int(ds.z.size),
            "z_top": float(ds.z[0]) + ds.attrs["dz"] / 2,
            "z_bot": float(ds.z[-1]) - ds.attrs["dz"] / 2,
        }
        for name, (src, vmin, vmax, units, label, cmap) in VARS.items():
            a = src(ds).values if callable(src) else ds[src].values.astype(float)
            cat = name == "unit"
            a = np.where(air, np.nan, a)
            meta["bytes"] += _write_gz(out / f"{lev}_{name}.u8.gz", _quantize(a, vmin, vmax, cat))
            meta["vars"][name] = {
                "vmin": vmin,
                "vmax": vmax,
                "units": units,
                "label": label,
                "categorical": cat,
                "lut": _unit_lut() if cat else _lut(cmap),
            }
    meta["units"] = {int(k): v for k, v in unit_names().items()}
    meta["surface"] = export_surface(tree["surface"].to_dataset(), dom, out)
    (out / "meta.json").write_text(json.dumps(meta, separators=(",", ":")))
    return meta


def export_surface(s: xr.Dataset, dom, out: Path) -> dict:
    s = s.sortby("y")  # south -> north
    elev = np.rint(s["elevation"].values).astype(np.int16)
    ice = s["ice_thickness"].values
    _write_gz(out / "surface_elev.i16.gz", elev)
    _write_gz(out / "surface_ice.u8.gz", np.clip(np.rint(ice), 0, 254).astype(np.uint8))
    textures = {"units": _units_texture(s), "ice": _ice_texture(s)}
    for k, img in textures.items():
        Image.fromarray(img[::-1]).save(out / f"tex_{k}.png")  # image rows north -> south
    i432 = dom.path("processed") / "overlays" / "i432.tif"
    if i432.exists():
        _i432_texture(i432, s, dom, out / "tex_i432.webp")
        textures["i432"] = True
    from pyproj import Transformer

    x0, y0, x1, y1 = dom.bounds
    tf = Transformer.from_crs(dom.crs, "EPSG:4326", always_xy=True)
    corners = [list(tf.transform(x, y)) for x, y in ((x0, y1), (x1, y1), (x1, y0), (x0, y0))]  # NW NE SE SW
    return {
        "corners_lonlat": corners,
        "bounds": [x0, y0, x1, y1],
        "x0": float(s.x[0]),
        "y0": float(s.y[0]),
        "dx": float(dom.surface_res_m),
        "nx": int(s.x.size),
        "ny": int(s.y.size),
        "textures": sorted(textures),
    }


def _hillshade(z: np.ndarray, res: float) -> np.ndarray:
    gy, gx = np.gradient(z, res)
    az, alt = np.deg2rad(315), np.deg2rad(45)
    slope = np.arctan(np.hypot(gx, gy))
    aspect = np.arctan2(-gx, gy)
    return np.clip(np.sin(alt) * np.cos(slope) + np.cos(alt) * np.sin(slope) * np.cos(az - aspect), 0, 1)


def _units_texture(s: xr.Dataset) -> np.ndarray:
    lut = np.array(_unit_lut(), dtype=float)
    rgb = lut[np.clip(s["surface_unit"].values, 0, 255)]
    hs = _hillshade(s["elevation"].values, float(abs(s.x[1] - s.x[0])))[..., None]
    return np.clip(rgb * (0.45 + 0.75 * hs), 0, 255).astype(np.uint8)


def _ice_texture(s: xr.Dataset) -> np.ndarray:
    hs = _hillshade(s["elevation"].values, float(abs(s.x[1] - s.x[0])))
    base = np.stack([hs * 170 + 40] * 3, -1)
    h = s["ice_thickness"].values
    cmap = matplotlib.colormaps["Blues"]
    ice = np.array(cmap(np.clip(h / 250.0, 0, 1) * 0.8 + 0.2))[..., :3] * 255
    return np.where((h > 1)[..., None], ice, base).astype(np.uint8)


def _i432_texture(tif: Path, s: xr.Dataset, dom, path: Path, res: float = 25.0):
    """I-432 reprojected to the UTM surface grid at 25 m (transparent outside the map)."""
    import rioxarray  # noqa: F401
    from affine import Affine
    from rasterio.enums import Resampling

    x0, y0, x1, y1 = dom.bounds
    shape = (int((y1 - y0) / res), int((x1 - x0) / res))
    img = xr.open_dataarray(tif, engine="rasterio").rio.reproject(
        dom.crs,
        shape=shape,
        transform=Affine(res, 0, x0, 0, -res, y1),
        resampling=Resampling.bilinear,
        nodata=0,
    )
    Image.fromarray(np.moveaxis(img.values.astype(np.uint8), 0, -1)).save(path, quality=82, method=6)
