"""Fused model -> uniform grids for ray tracing and location codes.

The model is stored on three stacked levels with different spacing (L1/L2/L3). Ray tracers want
one regular grid, so :func:`uniform` resamples all three onto a single (z, y, x) grid by linear
interpolation within each level. Cells above the DEM ("air") are filled with the value of the
first rock cell below them, so that receivers at the surface sit in rock; an ``air`` mask keeps
track of them.

Writers:
  write_netcdf  CF netCDF4 in UTM 10N (x, y in m; z = elevation in m, positive up)
  write_nll     NonLinLoc 3D model grids (SLOW_LEN, km, depth positive down, TRANSFORM NONE)
  write_emc     EMC-style netCDF (longitude, latitude, depth in km below sea level, km/s, g/cm^3)
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import xarray as xr

VARS = ("vp", "vs", "rho", "qp", "qs")
UNITS = {"vp": "m/s", "vs": "m/s", "rho": "kg/m3", "qp": "1", "qs": "1"}
LONG = {
    "vp": "P-wave speed",
    "vs": "S-wave speed",
    "rho": "density",
    "qp": "P quality factor",
    "qs": "S quality factor",
}


def uniform(
    tree: xr.DataTree,
    dx: float = 500.0,
    dz: float = 100.0,
    z_top: float | None = None,
    z_bot: float = -20000.0,
    variables=VARS,
) -> xr.Dataset:
    s = tree["surface"].to_dataset()
    x0, x1 = float(s.x.min()) - 50, float(s.x.max()) + 50
    y0, y1 = float(s.y.min()) - 50, float(s.y.max()) + 50
    if z_top is None:
        z_top = float(np.ceil(float(s["elevation"].max()) / dz) * dz)
    xs = np.arange(x0 + dx / 2, x1, dx)
    ys = np.arange(y0 + dx / 2, y1, dx)
    zs = np.arange(z_top - dz / 2, z_bot, -dz)
    out = {v: np.full((zs.size, ys.size, xs.size), np.nan, np.float32) for v in variables}
    for lev in ("L1", "L2", "L3"):
        ds = tree[lev].to_dataset()
        half = ds.attrs["dz"] / 2
        zmax, zmin = float(ds.z.max()) + half, float(ds.z.min()) - half
        sel = (zs <= zmax) & (zs >= zmin) & np.isnan(out[variables[0]][:, 0, 0])
        if not sel.any():
            continue
        # clamp to the level's cell centres so the edges of each level are filled, not NaN
        zq = np.clip(zs[sel], float(ds.z.min()), float(ds.z.max()))
        xq = np.clip(xs, float(ds.x.min()), float(ds.x.max()))
        yq = np.clip(ys, float(ds.y.min()), float(ds.y.max()))
        sub = ds[list(variables)].interp(z=zq, y=yq, x=xq, method="linear")
        for v in variables:
            out[v][sel] = sub[v].transpose("z", "y", "x").values
    # air (and interpolation holes just under the surface): fill downward from the first rock cell
    air = np.isnan(out[variables[0]])
    for v in variables:
        a = out[v]
        for k in range(a.shape[0] - 2, -1, -1):
            a[k] = np.where(np.isnan(a[k]), a[k + 1], a[k])
    elev = s["elevation"].interp(x=xs, y=ys, method="linear").values
    air = air & (zs[:, None, None] > elev[None])
    ds = xr.Dataset(
        {v: (("z", "y", "x"), out[v], {"units": UNITS[v], "long_name": LONG[v]}) for v in variables},
        coords={
            "z": ("z", zs, {"units": "m", "long_name": "elevation (NAVD88), positive up"}),
            "y": ("y", ys, {"units": "m", "long_name": "UTM 10N northing"}),
            "x": ("x", xs, {"units": "m", "long_name": "UTM 10N easting"}),
        },
    )
    ds["air"] = (
        ("z", "y", "x"),
        air.astype(np.int8),
        {"long_name": "1 above the ground surface (values copied from the first rock cell below)"},
    )
    ds["surface_elevation"] = (("y", "x"), elev.astype(np.float32), {"units": "m"})
    ds.attrs = {
        "title": "rainier3d fused model, uniform grid",
        "crs": "EPSG:32610 (UTM 10N, WGS84)",
        "vertical_datum": "NAVD88 (EPSG:5703)",
        "dx_m": dx,
        "dz_m": dz,
        "method": "linear resampling of model.zarr levels L1-L3; air filled from below",
        "source": "https://github.com/Denolle-Lab/mt-rainier-digital-model",
    }
    return ds


def write_netcdf(ds: xr.Dataset, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    enc = {v: {"zlib": True, "complevel": 4} for v in ds.data_vars}
    ds.to_netcdf(path, encoding=enc)
    return path


def write_nll(ds: xr.Dataset, stem: Path, phases=("P", "S")) -> list[Path]:
    """NonLinLoc model grids: stem.P.mod.hdr/.buf etc. SLOW_LEN = slowness (s/km) x cell size (km).

    Grid axes are x (east), y (north), z (depth, km, positive down, below sea level) in UTM 10N km;
    the .buf is float32 with z varying fastest, then y, then x (NonLinLoc order).
    """
    stem.parent.mkdir(parents=True, exist_ok=True)
    dxk = float(ds.attrs["dx_m"]) / 1000.0
    dzk = float(ds.attrs["dz_m"]) / 1000.0
    if not np.isclose(dxk, dzk):
        raise ValueError("NonLinLoc SLOW_LEN grids need dx == dz; export with dz equal to dx")
    written = []
    for ph in phases:
        v = ds["vp" if ph == "P" else "vs"].values / 1000.0  # km/s, (z, y, x) with z top-down
        slow_len = (dxk / v).astype(np.float32)
        arr = np.transpose(slow_len, (2, 1, 0))  # (x, y, z): z fastest in C order
        buf = stem.with_name(f"{stem.name}.{ph}.mod.buf")
        hdr = stem.with_name(f"{stem.name}.{ph}.mod.hdr")
        np.ascontiguousarray(arr).tofile(buf)
        nx, ny, nz = arr.shape
        x0, y0 = float(ds.x[0]) / 1000.0, float(ds.y[0]) / 1000.0
        z0 = -float(ds.z[0]) / 1000.0
        hdr.write_text(
            f"{nx} {ny} {nz}  {x0:.4f} {y0:.4f} {z0:.4f}  {dxk:.4f} {dxk:.4f} {dzk:.4f} SLOW_LEN FLOAT\n"
            "TRANSFORM  NONE\n"
        )
        written += [hdr, buf]
    return written


def write_emc(
    tree: xr.DataTree, dom, path: Path, dlon: float = 0.005, dlat: float = 0.005, depths_km=None
) -> Path:
    """EMC-style netCDF on a lon/lat grid; depth in km below sea level (negative above)."""
    from pyproj import Transformer

    if depths_km is None:
        depths_km = np.r_[np.arange(-4.4, 1.0, 0.1), np.arange(1.0, 6.0, 0.25), np.arange(6.0, 20.01, 1.0)]
    w, s, e, n = dom.bbox_4326
    lon = np.arange(np.ceil(w / dlon) * dlon, e, dlon)
    lat = np.arange(np.ceil(s / dlat) * dlat, n, dlat)
    grid = uniform(tree, dx=250.0, dz=50.0)
    tf = Transformer.from_crs("EPSG:4326", dom.crs, always_xy=True)
    LON, LAT = np.meshgrid(lon, lat)
    X, Y = tf.transform(LON, LAT)
    xi = xr.DataArray(X, dims=("latitude", "longitude"))
    yi = xr.DataArray(Y, dims=("latitude", "longitude"))
    zi = xr.DataArray(-np.asarray(depths_km) * 1000.0, dims=("depth",))
    sub = grid[["vp", "vs", "rho", "air"]].interp(x=xi, y=yi, z=zi, method="linear")
    out = xr.Dataset(
        coords={
            "depth": (
                "depth",
                depths_km,
                {"units": "km", "positive": "down", "long_name": "depth below sea level"},
            ),
            "latitude": ("latitude", lat, {"units": "degrees_north"}),
            "longitude": ("longitude", lon, {"units": "degrees_east"}),
        }
    )
    for v, scale, u in (("vp", 1e-3, "km.s-1"), ("vs", 1e-3, "km.s-1"), ("rho", 1e-3, "g.cm-3")):
        a = sub[v].where(sub["air"] < 0.5).transpose("depth", "latitude", "longitude") * scale
        out[v] = a.astype(np.float32)
        out[v].attrs = {"units": u, "long_name": LONG[v], "_FillValue": np.float32(np.nan)}
    out.attrs = {
        "title": "rainier3d fused velocity model (EMC-style)",
        "geospatial_lat_min": float(lat.min()),
        "geospatial_lat_max": float(lat.max()),
        "geospatial_lon_min": float(lon.min()),
        "geospatial_lon_max": float(lon.max()),
        "geospatial_vertical_positive": "down",
        "geospatial_vertical_units": "km",
        "source": "https://github.com/Denolle-Lab/mt-rainier-digital-model",
        "note": "above-ground cells are NaN; depth is relative to sea level (NAVD88)",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_netcdf(path, format="NETCDF3_CLASSIC")
    return path
