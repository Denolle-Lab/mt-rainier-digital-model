"""Terrain-correlated apparent magnetisation from the 2022 Packwood aeromagnetic survey (Blakely, Bennett,
Staisch & Wells 2024, USGS data release, doi:10.5066/P9UJHQU1), merged with the 1996 helicopter survey of the
edifice (Rystrom, Finn & Deszcz-Pan 2000; S22, rainier3d.alteration.finn2001).

The 2022 survey (fixed wing, 400 m east-west lines, drape planned 200 m above terrain) surrounds the edifice
but does not cover it; the 1996 survey covers the edifice and overlaps it in a ring up to ~3 km wide. In
rugged terrain the 2022 sensor flew ~700 m above the ground (400-1100 m), the 1996 sensor ~80 m.

Per survey, on the model surface grid:
  rtp   the published total-field anomaly (2022: grid MAGRES, IGRF-12 removed) reduced to the pole with the
        field direction of configs/magnetics.yaml and induced magnetisation along it; gaps are filled with the
        harmonic interpolant and the grid is reflect-padded before the FFT. 1996: the published rp grid.
  G     the anomaly at the sensor (2022: the drape surface of the flight lines) of the terrain between 0 m and
        ``top`` (the ground, or the bedrock with glacier ice excluded) magnetised 1 A/m vertically: harmonica
        prisms, truncated ``reach`` beyond each tile of sensors.
  M     the local slope of rtp on G in a Gaussian window (2022: configs/magnetics.yaml; 1996: 500 m, S22): the
        magnetisation of uniformly magnetised terrain that explains the local covariance. A constant in each
        window absorbs sources broader than the window.
The two M fields are blended across the overlap: the weight of 1996 falls linearly with distance from 1 at the
edge of the 2022 gap to 0 at the edge of the 1996 survey.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.sparse as sp
import scipy.sparse.linalg as spla
import xarray as xr
from scipy.interpolate import griddata
from scipy.ndimage import binary_fill_holes, distance_transform_edt, gaussian_filter

from rainier3d.alteration.aerogeophysics import _gxf_header

log = logging.getLogger(__name__)
ITEM_URL = "https://www.sciencebase.gov/catalog/item/{item}?format=json"
GRID = "Packwood_grid_MAIN.gxf"
LINES = "Packwood_data_MAIN.csv"


def fetch(raw: Path, item: str, files: list[str]) -> Path:
    """Download ``files`` of ScienceBase item ``item`` into ``raw`` (cached); the file URLs come from the
    item's JSON record."""
    import requests

    raw.mkdir(parents=True, exist_ok=True)
    missing = [f for f in files if not (raw / f).exists()]
    if missing:
        rec = requests.get(ITEM_URL.format(item=item), timeout=60).json()
        urls = {f["name"]: f["url"] for f in rec.get("files", [])}
        for name in missing:
            log.info("fetching %s", name)
            with requests.get(urls[name], stream=True, timeout=600) as r:
                r.raise_for_status()
                tmp = raw / f"{name}.part"
                with open(tmp, "wb") as fh:
                    for chunk in r.iter_content(1 << 20):
                        fh.write(chunk)
                tmp.rename(raw / name)
    return raw


def read_grid(path: Path) -> xr.DataArray:
    """A Packwood GXF grid on WGS84 / UTM 10N cell centres, y ascending, the -1e32 nulls as NaN."""
    import rasterio

    h = _gxf_header(path)
    nx, ny, dx = int(h["POINTS"]), int(h["ROWS"]), float(h["PTSEPARATION"])
    x0, y0 = float(h["XORIGIN"]), float(h["YORIGIN"])
    with rasterio.open(path) as d:
        a = d.read(1).astype(float)
        top = d.transform.f
    # GDAL returns rows north -> south with its top edge half a cell above the header's last row
    if abs(top - (y0 + (ny - 1) * dx + dx / 2)) > 1e-6:
        raise ValueError(f"{path.name}: GDAL top edge {top} does not match the GXF header")
    a = a[::-1]
    a[a <= -1e30] = np.nan
    x, y = x0 + dx * np.arange(nx), y0 + dx * np.arange(ny)
    return xr.DataArray(a, coords={"y": y, "x": x}, dims=("y", "x"), name="tmi", attrs={"units": "nT"})


def sensor_elevation(csv: Path, x: np.ndarray, y: np.ndarray, step: int) -> np.ndarray:
    """Drape surface of the flight lines (channel DRAPE, m above sea level), linear onto cell centres x, y.
    The published anomaly is reduced to this surface (data dictionary: IGRFDIFF and ALTCOR)."""
    fl = pd.read_csv(csv, usecols=["x", "y", "DRAPE"]).iloc[::step]
    X, Y = np.meshgrid(x, y)
    return griddata((fl.x.values, fl.y.values), fl.DRAPE.values, (X, Y), method="linear")


def harmonic_fill(a: np.ndarray) -> np.ndarray:
    """NaN cells filled with the harmonic interpolant of their finite neighbours (zero flux at the grid
    edge)."""
    bad = ~np.isfinite(a)
    if not bad.any():
        return a.copy()
    idx = -np.ones(a.shape, int)
    idx[bad] = np.arange(bad.sum())
    ny, nx = a.shape
    rows, cols, vals = [], [], []
    rhs = np.zeros(bad.sum())
    for k, (i, j) in enumerate(zip(*np.nonzero(bad), strict=True)):
        nb = [
            (i + di, j + dj)
            for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1))
            if 0 <= i + di < ny and 0 <= j + dj < nx
        ]
        rows.append(k), cols.append(k), vals.append(float(len(nb)))
        for ii, jj in nb:
            if bad[ii, jj]:
                rows.append(k), cols.append(idx[ii, jj]), vals.append(-1.0)
            else:
                rhs[k] += a[ii, jj]
    out = a.copy()
    out[bad] = spla.spsolve(sp.csr_matrix((vals, (rows, cols)), shape=(bad.sum(), bad.sum())), rhs)
    return out


def reduce_to_pole(da: xr.DataArray, inc: float, dec: float, pad_fraction: float) -> xr.DataArray:
    """harmonica.reduction_to_pole of a gappy grid: harmonic fill, reflect pad, transform, crop, re-mask.
    harmonica sets the zero wavenumber to 0, so the level of the result is arbitrary (zero mean over the
    padded grid); the regression of local_slope does not depend on it."""
    import harmonica as hm

    a = harmonic_fill(da.values)
    py, px = int(a.shape[0] * pad_fraction), int(a.shape[1] * pad_fraction)
    ap = np.pad(a - a.mean(), ((py, py), (px, px)), mode="reflect")
    dx = float(da.x[1] - da.x[0])
    g = xr.DataArray(
        ap,
        coords={
            "northing": float(da.y[0]) + dx * np.arange(-py, a.shape[0] + py),
            "easting": float(da.x[0]) + dx * np.arange(-px, a.shape[1] + px),
        },
        dims=("northing", "easting"),
    )
    r = hm.reduction_to_pole(g, inc, dec).values[py : py + a.shape[0], px : px + a.shape[1]]
    return da.copy(data=np.where(np.isfinite(da.values), r, np.nan)).rename("rtp")


def onto(da: xr.DataArray, x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Bilinear onto cell centres x, y in the same CRS; NaN where the nearest source cell is NaN."""
    v = da.copy(data=harmonic_fill(da.values)).interp(x=x, y=y).values
    ok = da.copy(data=np.isfinite(da.values).astype(float)).interp(x=x, y=y, method="nearest").values
    return np.where(ok > 0.5, v, np.nan)


def highpass_corr(a: np.ndarray, b: np.ndarray, sigma_cells: float = 10) -> float:
    """Correlation of the high-passed fields over the cells where both are finite (as aerogeophysics)."""

    def hp(v):
        v = np.nan_to_num(v, nan=np.nanmean(v))
        return v - gaussian_filter(v, sigma_cells)

    ok = np.isfinite(a) & np.isfinite(b)
    return float(np.corrcoef(hp(a)[ok], hp(b)[ok])[0, 1])


def terrain_effect(
    top: np.ndarray,
    x: np.ndarray,
    y: np.ndarray,
    h: np.ndarray,
    need: np.ndarray,
    reach_m: float,
    tile: int = 50,
) -> np.ndarray:
    """b_u (nT) at (x, y, h) of prisms from 0 m to ``top`` magnetised 1 A/m vertically, on the cells of
    ``need``; the prisms more than ``reach_m`` beyond a tile of ``tile`` x ``tile`` cells are left out, and
    the grid is edge-padded by ``reach_m``."""
    import harmonica as hm

    dx = float(x[1] - x[0])
    R = int(round(reach_m / dx))
    t = np.pad(np.maximum(np.nan_to_num(top, nan=np.nanmin(top)), 1.0), R, mode="edge")
    xp, yp = x[0] + dx * np.arange(-R, len(x) + R), y[0] + dx * np.arange(-R, len(y) + R)
    G = np.full(h.shape, np.nan)
    ny, nx = h.shape
    for i0 in range(0, ny, tile):
        for j0 in range(0, nx, tile):
            sl = (slice(i0, min(i0 + tile, ny)), slice(j0, min(j0 + tile, nx)))
            if not need[sl].any():
                continue
            X, Y = np.meshgrid(x[sl[1]], y[sl[0]])
            ti, tj = slice(i0, min(i0 + tile, ny) + 2 * R), slice(j0, min(j0 + tile, nx) + 2 * R)
            PX, PY = np.meshgrid(xp[tj], yp[ti])
            tt = t[ti, tj].ravel()
            pr = np.column_stack([PX.ravel() - dx / 2, PX.ravel() + dx / 2, PY.ravel() - dx / 2,
                                  PY.ravel() + dx / 2, np.zeros(tt.size), tt])  # fmt: skip
            n = len(pr)
            G[sl] = hm.prism_magnetic(
                (X.ravel(), Y.ravel(), h[sl].ravel()), pr, (np.zeros(n), np.zeros(n), np.ones(n)), "b_u"
            ).reshape(X.shape)
    return np.where(need, G, np.nan)


def local_slope(d: np.ndarray, G: np.ndarray, dx: float, sigma_m: float) -> np.ndarray:
    """Slope of d on G in a Gaussian window of ``sigma_m`` (the regression of
    finn2001.apparent_magnetization), NaN where less than half of the window has data or the cell has none."""
    ok = np.isfinite(d) & np.isfinite(G)
    w = ok.astype(float)
    dd, gg = np.where(ok, d, 0.0), np.where(ok, G, 0.0)
    s = sigma_m / dx

    def wmean(v):
        return gaussian_filter(v * w, s) / np.maximum(gaussian_filter(w, s), 1e-9)

    mg, md = wmean(gg), wmean(dd)
    M = (wmean(gg * dd) - mg * md) / np.maximum(wmean(gg * gg) - mg**2, 1e-9)
    return np.where((gaussian_filter(w, s) > 0.5) & ok, M, np.nan)


def blend_weight(inner: np.ndarray, outer: np.ndarray) -> np.ndarray:
    """Weight of ``inner`` (1996) where both fields have data: linear in distance from 1 at the cells where
    only ``inner`` has data (the 2022 gap) to 0 at the edge of the ``inner`` footprint; 1 where only
    ``inner``, 0 elsewhere. Gaps of a few cells inside the footprint do not count as its edge."""
    fi, fo = np.isfinite(inner), np.isfinite(outer)
    foot = binary_fill_holes(fi)
    a = distance_transform_edt(~(foot & ~fo))  # to the cells where only inner has data
    b = distance_transform_edt(foot)  # to the outside of the inner footprint
    w = b / np.maximum(a + b, 1e-9)
    return np.where(fi & fo, w, np.where(fi, 1.0, 0.0))


def blend(inner: np.ndarray, outer: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """The two fields merged with blend_weight -> (merged, weight of inner)."""
    w = blend_weight(inner, outer)
    fi, fo = np.isfinite(inner), np.isfinite(outer)
    merged = np.where(fi & fo, w * inner + (1 - w) * outer, np.where(fi, inner, outer))
    return merged, w
