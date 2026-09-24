"""Regional (long-wavelength) model sampled on the level grids.

Down to 9.9 km below the ground: USGS Cascadia CVM v1.7 (Vp, Vs), levels L01 (0-1200 m, 200 m
spacing) and L2 (1500-9900 m, 300 m spacing), both with z = depth below the ground surface (see
configs/sources.yaml:cvm17). Deeper: CRESCENT Gen0 Vs (depth in km below sea level), with Vp from
Brocher (2005). CVM L3 (10.8-59.4 km) is not downloaded yet; CRESCENT fills that range.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import xarray as xr
from pyproj import Transformer

from rainier3d.config.domain import Domain, Level
from rainier3d.petro.relations import brocher_vp_from_vs

log = logging.getLogger(__name__)

HOME = Path.home()
CVM_FILES = [
    HOME / "GitHub/gwl-space-time-smooth/data/raw/CVM17_L01.nc",
    HOME / "GitHub/gwl-space-time-smooth/data/raw/CVM17_L2.nc",
]
CRESCENT = HOME / "GitHub/cascadia_obs_ensemble/data/tomography/CRESCENT_Gen0.nc"
CVM_MAX_DEPTH = 9900.0


def load_cvm(dom: Domain, pad: float = 2000.0) -> xr.Dataset:
    """CVM Vp, Vs (m/s) over the domain on (depth, y, x), depth below the ground surface (m)."""
    cache = dom.path("raw") / "regional" / "cvm17_domain.nc"
    if cache.exists():
        return xr.open_dataset(cache).load()
    x0, y0, x1, y1 = dom.bounds
    parts = []
    for f in CVM_FILES:
        with xr.open_dataset(f) as ds:
            sub = ds[["vp", "vs"]].sel(utme=slice(x0 - pad, x1 + pad), utmn=slice(y0 - pad, y1 + pad)).load()
        sub = sub.rename(utme="x", utmn="y", z="depth").transpose("depth", "y", "x")
        parts.append(sub)
    # L01 and L2 differ in horizontal spacing: put both on the finer L01 grid, then stack in depth
    fine = parts[0]
    deep = parts[1].interp(x=fine.x, y=fine.y, method="linear")
    cvm = xr.concat([fine, deep], dim="depth").astype("float32")
    cvm["depth"] = cvm["depth"].astype("float64")
    cvm.attrs = {"source": "cvm17", "depth": "m below ground surface"}
    cache.parent.mkdir(parents=True, exist_ok=True)
    cvm.to_netcdf(cache)
    return cvm


def load_crescent(dom: Domain) -> xr.Dataset:
    """CRESCENT Gen0 Vs and its uncertainty (m/s) on (depth_bsl m, y, x) over the domain."""
    with xr.open_dataset(CRESCENT) as ds:
        lon0, lat0, lon1, lat1 = dom.bbox_4326
        sub = ds.sel(longitude=slice(lon0 - 0.5, lon1 + 0.5), latitude=slice(lat0 - 0.5, lat1 + 0.5)).load()
    tf = Transformer.from_crs("EPSG:4326", dom.crs, always_xy=True)
    lev_x = np.arange(dom.bounds[0] - 5000, dom.bounds[2] + 5001, 2000.0)
    lev_y = np.arange(dom.bounds[1] - 5000, dom.bounds[3] + 5001, 2000.0)
    xx, yy = np.meshgrid(lev_x, lev_y)
    lon, lat = tf.transform(xx, yy, direction="INVERSE")
    lon = xr.DataArray(lon, dims=("y", "x"), coords={"y": lev_y, "x": lev_x})
    lat = xr.DataArray(lat, dims=("y", "x"), coords={"y": lev_y, "x": lev_x})
    out = sub.interp(longitude=lon, latitude=lat, method="linear").drop_vars(["longitude", "latitude"])
    out = out.assign_coords(depth=out.depth * 1000.0).rename(depth="depth_bsl")
    unit_scale = 1000.0 if float(out["Vs"].max()) < 20 else 1.0  # km/s in the file
    return (out * unit_scale).astype("float32")


def _vertical_interp(prof: np.ndarray, depths: np.ndarray, d: np.ndarray) -> np.ndarray:
    """prof (nd, ny, nx) on ``depths``; sample at d (nz, ny, nx), clamped at the ends."""
    dc = np.clip(d, depths[0], depths[-1])
    i = np.clip(np.searchsorted(depths, dc) - 1, 0, depths.size - 2)
    w = (dc - depths[i]) / (depths[i + 1] - depths[i])
    lo = np.take_along_axis(prof, i, axis=0)
    hi = np.take_along_axis(prof, i + 1, axis=0)
    return (1 - w) * lo + w * hi


def regional_on_level(lev: Level, depth: np.ndarray, cvm: xr.Dataset, cres: xr.Dataset) -> dict:
    """Regional Vp, Vs, and CRESCENT Vs uncertainty at every cell of a level (m/s)."""
    c = cvm.interp(x=lev.x, y=lev.y, method="linear")
    cd = c["depth"].values.astype(float)
    d = np.maximum(depth, 0.0)
    vp_c = _vertical_interp(c["vp"].values, cd, d)
    vs_c = _vertical_interp(c["vs"].values, cd, d)

    r = cres.interp(x=lev.x, y=lev.y, method="linear")
    zb = -lev.z[:, None, None] * np.ones((1, lev.y.size, lev.x.size))
    rd = r["depth_bsl"].values.astype(float)
    vs_r = _vertical_interp(r["Vs"].values, rd, zb)
    unc_r = _vertical_interp(r["Uncert_Vs"].values, rd, zb)
    vp_r = brocher_vp_from_vs(vs_r / 1000.0) * 1000.0

    deep = d > CVM_MAX_DEPTH
    return {
        "vp": np.where(deep, vp_r, vp_c),
        "vs": np.where(deep, vs_r, vs_c),
        "vs_unc": unc_r,
        "from_crescent": deep,
    }
