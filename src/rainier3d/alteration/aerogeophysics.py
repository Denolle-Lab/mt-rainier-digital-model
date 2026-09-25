"""USGS 1996 helicopter EM and magnetic survey of Mount Rainier (Rystrom, Finn & Deszcz-Pan 2000, OFR 00-027),
the data behind Finn, Sisson & Deszcz-Pan (2001, Nature 409).

Grids (Geosoft GXF, NAD27 / UTM 10N):
  33k, 4737, 4341  apparent resistivity, log10 ohm-m (coplanar 33 kHz and 4737 Hz, coaxial 4341 Hz), 50 m
  837              apparent resistivity, ohm-m (coplanar 837 Hz), 50 m
  rp               total-field anomaly reduced to the pole, nT, 62 m
Flight lines: flightem.xyz (radar altitude, apparent depth per frequency), flight_line_mag.gxf (DEM, flight
elevation, total field).

Georeferencing is checked, not assumed: GDAL places the rp grid (#SENSE -2) with its origin at the top edge,
although #YORIGIN is its lower edge; read_grid() uses the header and check_registration() verifies every grid
against topography (magnetics) and the glacier mask (EM, ice is resistive).
"""

from __future__ import annotations

import gzip
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

URL = "https://pubs.usgs.gov/of/2000/ofr-00-0027/data"
FILES = {
    "33k": "grid_files/geosoft/em/33k.gxf",
    "4737": "grid_files/geosoft/em/4737.gxf",
    "4341": "grid_files/geosoft/em/4341.gxf",
    "837": "grid_files/geosoft/em/837.gxf",
    "rp": "grid_files/geosoft/mag/rp.gxf",
    "flightem.xyz.gz": "flight_line/em/flightem.xyz.gz",
    "flight_line_mag.gxf.gz": "flight_line/mag/flight_line_mag.gxf.gz",
}
EM_FREQS = {"33k": 33000.0, "4737": 4737.0, "4341": 4341.0, "837": 837.0}
NAD27_UTM10 = "EPSG:26710"


def fetch(raw: Path) -> Path:
    import requests

    raw.mkdir(parents=True, exist_ok=True)
    for rel in FILES.values():
        p = raw / Path(rel).name
        if not p.exists():
            r = requests.get(f"{URL}/{rel}", timeout=120)
            r.raise_for_status()
            p.write_bytes(r.content)
    return raw


def _gxf_header(path: Path) -> dict:
    head, key = {}, None
    with open(path, errors="ignore") as f:
        for line in f:
            s = line.strip()
            if s.startswith("#GRID"):
                break
            if s.startswith("#"):
                key = s[1:].split()[0]
            elif key and s and key not in head:
                head[key] = s
    return head


def read_grid(raw: Path, name: str) -> xr.DataArray:
    """One survey grid on NAD27 / UTM 10N cell-centre coordinates (y ascending). EM grids as log10 ohm-m."""
    import rasterio

    path = raw / Path(FILES[name]).name
    h = _gxf_header(path)
    with rasterio.open(path) as d:
        a = d.read(1).astype(float)
    nx, ny = int(h["POINTS"]), int(h["ROWS"])
    dx, dy = float(h["PTSEPARATION"]), float(h["RWSEPARATION"])
    x0, y0 = float(h["XORIGIN"]), float(h["YORIGIN"])
    x = x0 + dx * np.arange(nx)
    y = y0 + dy * np.arange(ny)  # the origin is the first point of the lowest row for both sense codes here
    # rasterio returns rows north -> south for both files (checked against the header origin and topography)
    a = a[::-1]
    dummy = float(h.get("DUMMY", "nan").split()[0]) if "DUMMY" in h else np.nan
    a[(a <= -1e5) | (a == dummy)] = np.nan
    if name == "837":
        a = np.where(a > 0, np.log10(np.where(a > 0, a, 1.0)), np.nan)
    elif name != "rp" and np.nanmin(a) < -1.0:  # the transform's zero code is a dummy for the log grids
        a[a < -1.0] = np.nan
    units = "nT" if name == "rp" else "log10 ohm-m"
    return xr.DataArray(a, coords={"y": y, "x": x}, dims=("y", "x"), name=name, attrs={"units": units})


def to_model_grid(da: xr.DataArray, x: np.ndarray, y: np.ndarray, crs: str) -> xr.DataArray:
    """Resample a NAD27 grid onto model-CRS cell centres x, y (bilinear on the NAD27 coordinates)."""
    from pyproj import Transformer

    tf = Transformer.from_crs(crs, NAD27_UTM10, always_xy=True)
    xx, yy = np.meshgrid(x, y)
    xs, ys = tf.transform(xx, yy)
    out = da.interp(x=xr.DataArray(xs, dims=("y", "x")), y=xr.DataArray(ys, dims=("y", "x")))
    return xr.DataArray(out.values, coords={"y": y, "x": x}, dims=("y", "x"), name=da.name, attrs=da.attrs)


def flight_mag(raw: Path) -> pd.DataFrame:
    """Flight-line magnetics: x, y (NAD27 UTM), dem, flelv (m), total field (nT)."""
    rows = []
    with gzip.open(raw / "flight_line_mag.gxf.gz", "rt", errors="ignore") as f:
        for line in f:
            t = line.split()
            if len(t) == 9 and not line.lstrip().startswith("Line"):
                try:
                    rows.append([float(v) for v in t[:6]])
                except ValueError:
                    pass
    df = pd.DataFrame(rows, columns=["x", "y", "dem", "flelv", "id", "mag"])
    return df[(df.flelv > 0) & (df.dem > 0)].reset_index(drop=True)


def flight_em(raw: Path) -> pd.DataFrame:
    """Flight-line EM: radar altitude (m) and, per frequency block, apparent depth (m) and log10 resistivity.

    The 16 data columns come as four blocks of (in-phase, quadrature, apparent depth, log10 resistivity); the
    blocks are identified by their resistivity saturation levels (log10 3.20, 4.50, 3.90, 3.80), which order
    them as 837 Hz, 33 kHz, 4737 Hz and 4341 Hz (highest frequencies resolve the highest resistivities).
    """
    rows = []
    with gzip.open(raw / "flightem.xyz.gz", "rt", errors="ignore") as f:
        for line in f:
            t = line.split()
            if len(t) == 22:
                try:
                    rows.append([float(v.strip('"')) for v in t])
                except ValueError:
                    pass
    a = np.array(rows)
    df = pd.DataFrame({"radar": a[:, 1], "lon": a[:, 4], "lat": a[:, 5]})
    for b, f in enumerate(("837", "33k", "4737", "4341")):
        df[f"dep_{f}"] = a[:, 6 + 4 * b + 2]
        df[f"res_{f}"] = a[:, 6 + 4 * b + 3]
    return df[(df.radar > 0) & (df.radar < 1000)].reset_index(drop=True)


def check_registration(grids: dict, elevation: xr.DataArray, ice: xr.DataArray) -> dict:
    """Correlations that a mis-registered grid would fail: RTP against the high-passed topography (a
    magnetised edifice produces anomalies over ridges), and EM resistivity against ice thickness (ice is
    resistive)."""
    from scipy.ndimage import gaussian_filter

    def hp(a, s):
        a = np.nan_to_num(a, nan=np.nanmean(a))
        return a - gaussian_filter(a, s)

    out = {}
    e = elevation.values
    for k, g in grids.items():
        v = g.values
        ok = np.isfinite(v) & np.isfinite(e)
        if k == "rp":
            out[k] = float(np.corrcoef(hp(v, 10)[ok], hp(e, 10)[ok])[0, 1])
        else:
            i = ice.values
            ok &= np.isfinite(i)
            out[k] = float(np.corrcoef(v[ok], (i[ok] > 10).astype(float))[0, 1])
    return out
