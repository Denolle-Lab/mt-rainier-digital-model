"""Terrain geometry that controls surface instability (S30), after the specification of S. Han (2026).

Four layers on a 30 m grid in the domain CRS, from the USGS 3DEP surface elevation z and the IceBoost v2
ice thickness H (bedrock elevation b = z - H):

  surface_slope   arctan |grad z|, central differences between adjacent cells (a 2-cell, 60 m baseline);
                  over glaciers this is the slope of the ice surface
  bedrock_slope   the same operator on b; identical to surface_slope where there is no ice
  local_relief    max z - min z within a disk of radius R_relief centred on the cell
  valley_depth    black top-hat of z: grey-scale closing (dilation, then erosion, with a disk of radius
                  R_valley) minus z

Every filter reflects the grid at its edges (scipy.ndimage mode "reflect": d c b a | a b c d | d c b a).
The disk filters are exact: a flat disk is the union of its rows, so a running maximum (or minimum) of the
right width along x, shifted along y and reduced over the 2R+1 rows, gives the disk maximum in O(R N).
Parameters are in configs/terrain.yaml.
"""

from __future__ import annotations

import numpy as np
import xarray as xr
import yaml
from affine import Affine
from scipy import ndimage

from rainier3d.config.domain import REPO, Domain
from rainier3d.io.store import provenance

CONFIG = REPO / "configs" / "terrain.yaml"
LAYERS = ("surface_slope", "bedrock_slope", "local_relief", "valley_depth")


def load_config(path=CONFIG) -> dict:
    return yaml.safe_load(open(path).read())


# ---- grid ----
def grid(dom: Domain, res_m: float) -> tuple[np.ndarray, np.ndarray, Affine]:
    """Cell centres (x, y south to north) and the north-up transform of a ``res_m`` grid anchored at the
    domain's west and south edges. Whole cells only: a partial cell at the east or north edge is dropped."""
    x0, y0, x1, y1 = dom.bounds
    nx, ny = int(np.floor((x1 - x0) / res_m + 1e-9)), int(np.floor((y1 - y0) / res_m + 1e-9))
    x = x0 + res_m * (np.arange(nx) + 0.5)
    y = y0 + res_m * (np.arange(ny) + 0.5)
    return x, y, Affine(res_m, 0, x0, 0, -res_m, y0 + ny * res_m)


def dem_on(dom: Domain, src: xr.DataArray, res_m: float) -> xr.DataArray:
    """3DEP elevation (any CRS) block-averaged onto the ``res_m`` grid; rows south to north."""
    from rasterio.enums import Resampling

    x, y, t = grid(dom, res_m)
    out = src.rio.reproject(dom.crs, shape=(y.size, x.size), transform=t, resampling=Resampling.average)
    a = out.values.astype("float32")[::-1]
    a[a < -1000] = np.nan
    if np.isnan(a).any():
        raise ValueError(f"DEM has {int(np.isnan(a).sum())} empty cells on the {res_m:g} m grid")
    return xr.DataArray(a, dims=("y", "x"), coords={"y": y, "x": x})


def ice_on(ice: xr.DataArray, x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Ice thickness (model surface grid) interpolated bilinearly onto (x, y). Cells between the outermost
    source cell centres and the grid edge are extrapolated linearly; negative values are set to 0."""
    ice = ice.sortby("y").fillna(0.0)
    a = ice.interp(x=x, y=y, method="linear", kwargs={"fill_value": "extrapolate"}).values
    return np.clip(a, 0.0, None).astype("float32")


# ---- operators ----
def slope_deg(z: np.ndarray, dx: float) -> np.ndarray:
    """arctan |grad z| in degrees; central differences (z[i+1] - z[i-1]) / 2dx, reflected edges."""
    k = np.array([-1.0, 0.0, 1.0]) / (2.0 * dx)
    gx = ndimage.correlate1d(z.astype("float64"), k, axis=1, mode="reflect")
    gy = ndimage.correlate1d(z.astype("float64"), k, axis=0, mode="reflect")
    return np.degrees(np.arctan(np.hypot(gx, gy))).astype("float32")


def disk_halfwidths(radius_cells: float) -> np.ndarray:
    """Half-width (cells) of each row of a disk: row dy holds the cells with dx^2 + dy^2 <= r^2."""
    r = int(np.floor(radius_cells + 1e-9))
    dy = np.arange(-r, r + 1)
    return np.floor(np.sqrt(np.maximum(radius_cells**2 - dy**2, 0.0)) + 1e-9).astype(int)


def disk_filter(z: np.ndarray, radius_cells: float, op: str) -> np.ndarray:
    """Exact maximum (op='max') or minimum (op='min') of z over a flat disk, reflected edges."""
    f1 = ndimage.maximum_filter1d if op == "max" else ndimage.minimum_filter1d
    red = np.maximum if op == "max" else np.minimum
    hw = disk_halfwidths(radius_cells)
    r = hw.size // 2
    zp = np.pad(z.astype("float64"), ((r, r), (0, 0)), mode="symmetric")  # = ndimage "reflect"
    rows = {w: f1(zp, size=2 * w + 1, axis=1, mode="reflect") for w in np.unique(hw)}
    ny = z.shape[0]
    out = None
    for i, w in enumerate(hw):  # row i of the disk is offset dy = i - r
        s = rows[w][i : i + ny]
        out = s.copy() if out is None else red(out, s)
    return out


def local_relief(z: np.ndarray, radius_m: float, dx: float) -> np.ndarray:
    r = radius_m / dx
    return (disk_filter(z, r, "max") - disk_filter(z, r, "min")).astype("float32")


def valley_depth(z: np.ndarray, radius_m: float, dx: float) -> np.ndarray:
    """Black top-hat: closing (dilation then erosion with the disk) minus z; >= 0."""
    r = radius_m / dx
    closing = disk_filter(disk_filter(z, r, "max"), r, "min")
    return (closing - z).astype("float32")


# ---- the dataset ----
ATTRS = {
    "elevation": ("m", "surface elevation (NAVD88), USGS 3DEP; top of the ice on glaciers"),
    "ice_thickness": ("m", "glacier ice thickness, IceBoost v2, bilinear from the 100 m model grid"),
    "bedrock_elevation": ("m", "bedrock elevation, surface elevation minus ice thickness"),
    "surface_slope": ("degree", "surface slope, arctan |grad z|, central differences (60 m baseline)"),
    "bedrock_slope": ("degree", "bedrock slope, arctan |grad b|, central differences (60 m baseline)"),
    "local_relief": ("m", "local relief, max - min surface elevation within a disk of radius {r_relief} m"),
    "valley_depth": (
        "m",
        "valley depth, grey-scale closing of surface elevation with a disk of radius {r_valley} m, minus"
        " the elevation (black top-hat)",
    ),
}
KEYS = {
    "elevation": ["usgs_3dep"],
    "ice_thickness": ["iceboost_v2", "rgi60"],
    "bedrock_elevation": ["usgs_3dep", "iceboost_v2"],
    "surface_slope": ["usgs_3dep", "han_terrain_2026"],
    "bedrock_slope": ["usgs_3dep", "iceboost_v2", "han_terrain_2026"],
    "local_relief": ["usgs_3dep", "han_terrain_2026"],
    "valley_depth": ["usgs_3dep", "han_terrain_2026"],
}


def build(dom: Domain, z: xr.DataArray, ice_model: xr.DataArray, cfg: dict) -> xr.Dataset:
    """All layers on the grid of ``z`` (from :func:`dem_on`)."""
    dx = float(cfg["grid"]["res_m"])
    rr, rv = float(cfg["local_relief"]["radius_m"]), float(cfg["valley_depth"]["radius_m"])
    x, y = z.x.values, z.y.values
    zz = z.values.astype("float32")
    h = ice_on(ice_model, x, y)
    b = zz - h
    arrays = {
        "elevation": zz,
        "ice_thickness": h,
        "bedrock_elevation": b,
        "surface_slope": slope_deg(zz, dx),
        "bedrock_slope": slope_deg(b, dx),
        "local_relief": local_relief(zz, rr, dx),
        "valley_depth": valley_depth(zz, rv, dx),
    }
    ds = xr.Dataset(coords={"y": y, "x": x})
    for k, a in arrays.items():
        units, long = ATTRS[k]
        da = xr.DataArray(a, dims=("y", "x"), coords=ds.coords, name=k)
        da.attrs = {"units": units, "long_name": long.format(r_relief=f"{rr:g}", r_valley=f"{rv:g}")}
        res = float(ice_model.attrs.get("gaia:resolution_m", 100.0)) if k == "ice_thickness" else dx
        ds[k] = provenance(da, KEYS[k], k, res)
    ds.attrs = {
        "crs": dom.crs,
        "vertical_datum": dom.vertical_datum,
        "domain": dom.name,
        "res_m": dx,
        "edge_handling": "reflect (scipy.ndimage mode 'reflect', half-sample symmetric)",
        "local_relief_radius_m": rr,
        "valley_depth_radius_m": rv,
        "specification": "han_terrain_2026 (configs/terrain.yaml)",
    }
    return ds


# ---- comparison with the mass-movement catalogue (S24) ----
def cell_index(ds: xr.Dataset, xs, ys) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Row, column of the cells holding points (xs, ys), and a mask of points on the grid."""
    dx = float(ds.x[1] - ds.x[0])
    x0, y0 = float(ds.x[0]) - dx / 2, float(ds.y[0]) - dx / 2
    j = np.floor((np.asarray(xs) - x0) / dx).astype(int)
    i = np.floor((np.asarray(ys) - y0) / dx).astype(int)
    ok = (i >= 0) & (i < ds.sizes["y"]) & (j >= 0) & (j < ds.sizes["x"])
    return i, j, ok


def polygon_mask(ds: xr.Dataset, geoms) -> np.ndarray:
    """Cells whose centre falls in any of ``geoms`` (rows south to north)."""
    from rasterio.features import geometry_mask

    dx = float(ds.x[1] - ds.x[0])
    t = Affine(dx, 0, float(ds.x[0]) - dx / 2, 0, -dx, float(ds.y[-1]) + dx / 2)
    m = geometry_mask(list(geoms), out_shape=(ds.sizes["y"], ds.sizes["x"]), transform=t, invert=True)
    return m[::-1]


def _stats(group: str, kind: str, n_features: int, vals: dict, thresholds: dict, ice: np.ndarray) -> dict:
    row = {"group": group, "kind": kind, "n_features": n_features, "n_cells": int(ice.size)}
    row["frac_on_ice"] = round(float(np.mean(ice > 10.0)), 3) if ice.size else np.nan
    for k, v in vals.items():
        v = v[np.isfinite(v)]
        p10, p50, p90 = np.percentile(v, [10, 50, 90]) if v.size else (np.nan,) * 3
        row |= {f"{k}_p10": round(p10, 1), f"{k}_median": round(p50, 1), f"{k}_p90": round(p90, 1)}
        row[f"{k}_frac_above_{thresholds[k]:g}"] = (
            round(float(np.mean(v > thresholds[k])), 3) if v.size else np.nan
        )
    return row


def compare(ds: xr.Dataset, events, flows, thresholds: dict, event_classes, flow_classes):
    """Distribution of the four layers at the events (by class, and all), in the flow polygons (by class)
    and over the whole grid. Returns the table and the number of events off the grid."""
    import pandas as pd

    arr = {k: ds[k].values for k in LAYERS}
    ice = ds["ice_thickness"].values
    rows = [
        _stats("whole domain", "domain", 0, {k: a.ravel() for k, a in arr.items()}, thresholds, ice.ravel())
    ]
    i, j, ok = cell_index(ds, events.geometry.x.values, events.geometry.y.values)
    ev = events[ok].assign(_i=i[ok], _j=j[ok])
    groups = [("all events", ev)] + [(label, ev[ev.cls == key]) for key, label, _ in event_classes]
    groups.append(("seismically recorded events", ev[ev.located == "seismic"]))
    for label, g in groups:
        if len(g):
            ii, jj = g._i.values, g._j.values
            rows.append(
                _stats(
                    label, "event", len(g), {k: a[ii, jj] for k, a in arr.items()}, thresholds, ice[ii, jj]
                )
            )
    for key, label, _ in flow_classes:
        g = flows[flows.cls == key]
        if len(g):
            m = polygon_mask(ds, g.geometry)
            rows.append(_stats(label, "flow", len(g), {k: a[m] for k, a in arr.items()}, thresholds, ice[m]))
    return pd.DataFrame(rows), int((~ok).sum())
