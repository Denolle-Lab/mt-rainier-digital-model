"""PNSN travel-time consistency (S6).

Data: PNSN (uw) origins and analyst picks from ComCat phase-data QuakeML; station coordinates
from the EarthScope FDSN station service. Travel times: fteikpy on a uniform grid, one solve per
station and phase (reciprocity), sampled at the PNSN hypocentres.

Two models are compared on the same grid:
  1D   the PNSN western-Washington layered model (vel_pnsn_wa.csv; linear gradient within layers),
       depth taken as km below sea level and the top gradient extrapolated above sea level.
  3D   the fused model (model.zarr), extended below its base with the 1D model.
Because the PNSN hypocentres were located with the 1D model plus station corrections, the 1D
residuals are biased low; residuals are compared after removing each event's mean (origin time).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import xarray as xr

from rainier3d.config.domain import Domain

log = logging.getLogger(__name__)

COMCAT = "https://earthquake.usgs.gov/fdsnws/event/1/query"
PNSN_1D = Path.home() / "GitHub/cascadia_obs_ensemble/data/vel_pnsn_wa.csv"


# ---------------------------------------------------------------- data
def fetch_events(dom: Domain, start: str, end: str, minmag: float) -> list[dict]:
    lon0, lat0, lon1, lat1 = dom.bbox_4326
    r = requests.get(
        COMCAT,
        params=dict(
            format="geojson",
            catalog="uw",
            eventtype="earthquake",
            starttime=start,
            endtime=end,
            minmagnitude=minmag,
            minlatitude=lat0,
            maxlatitude=lat1,
            minlongitude=lon0,
            maxlongitude=lon1,
        ),
        timeout=120,
    )
    r.raise_for_status()
    return r.json()["features"]


def fetch_picks(dom: Domain, events: list[dict]) -> pd.DataFrame:
    """One row per PNSN arrival: event, origin, station, phase, observed travel time."""
    from obspy import read_events

    cache = dom.path("raw") / "pnsn" / "picks.csv"
    if cache.exists():
        return pd.read_csv(cache)
    qdir = dom.path("raw") / "pnsn" / "quakeml"
    qdir.mkdir(parents=True, exist_ok=True)
    rows = []
    for ev in events:
        eid = ev["id"]
        qml = qdir / f"{eid}.xml"
        if not qml.exists():
            det = requests.get(ev["properties"]["detail"], timeout=60).json()
            pd_ = det["properties"]["products"].get("phase-data")
            if not pd_:
                continue
            url = pd_[0]["contents"]["quakeml.xml"]["url"]
            qml.write_bytes(requests.get(url, timeout=60).content)
        cat = read_events(str(qml))
        e = cat[0]
        o = e.preferred_origin() or e.origins[0]
        picks = {p.resource_id: p for p in e.picks}
        for a in o.arrivals:
            p = picks.get(a.pick_id)
            if p is None or a.phase not in ("P", "S"):
                continue
            w = p.waveform_id
            rows.append(
                dict(
                    event=eid,
                    lon=o.longitude,
                    lat=o.latitude,
                    depth_km=o.depth / 1e3,
                    mag=ev["properties"]["mag"],
                    net=w.network_code,
                    sta=w.station_code,
                    phase=a.phase,
                    tt_obs=p.time - o.time,
                    pnsn_res=a.time_residual,
                    pnsn_weight=a.time_weight,
                )
            )
    df = pd.DataFrame(rows)
    df.to_csv(cache, index=False)
    return df


def fetch_stations(dom: Domain, picks: pd.DataFrame) -> pd.DataFrame:
    from obspy.clients.fdsn import Client

    cache = dom.path("raw") / "pnsn" / "stations.csv"
    if cache.exists():
        return pd.read_csv(cache)
    lon0, lat0, lon1, lat1 = dom.bbox_4326
    inv = Client("IRIS").get_stations(
        network=",".join(sorted(picks["net"].unique())),
        level="station",
        minlatitude=lat0,
        maxlatitude=lat1,
        minlongitude=lon0,
        maxlongitude=lon1,
    )
    rows = [
        dict(net=n.code, sta=s.code, lon=s.longitude, lat=s.latitude, elev=s.elevation)
        for n in inv
        for s in n
    ]
    df = pd.DataFrame(rows).drop_duplicates(["net", "sta"])
    df.to_csv(cache, index=False)
    return df


# ---------------------------------------------------------------- models
def pnsn_1d(z_m: np.ndarray, phase: str) -> np.ndarray:
    """Velocity (m/s) of the PNSN 1D model at elevations z_m (NAVD88 m; depth = -z)."""
    t = pd.read_csv(PNSN_1D)
    t.columns = [c.strip() for c in t.columns]
    top, v, g = (
        t["depth"].values.astype(float),
        t[phase.lower() == "p" and "vp" or "vs"].values,
        t[phase.lower() == "p" and "vp_grad" or "vs_grad"].values,
    )
    dkm = -np.asarray(z_m) / 1e3
    i = np.clip(np.searchsorted(top, dkm, side="right") - 1, 0, top.size - 1)
    return (v[i] + g[i] * (dkm - top[i])) * 1e3


def grid_axes(dom: Domain, dx: float, z_top: float, z_bot: float):
    x0, y0, x1, y1 = dom.bounds
    return (np.arange(x0, x1 + 1, dx), np.arange(y0, y1 + 1, dx), np.arange(z_top, z_bot - 1, -dx))


def model_on_grid(tree: xr.DataTree, var: str, xs, ys, zs, phase: str) -> np.ndarray:
    """(nz, nx, ny) velocity from the fused model; air filled from the cell below; below base: 1D."""
    out = np.full((zs.size, xs.size, ys.size), np.nan)
    for lev in ("L1", "L2", "L3"):
        ds = tree[lev].to_dataset()
        zmin, zmax = float(ds.z.min()) - ds.attrs["dz"] / 2, float(ds.z.max()) + ds.attrs["dz"] / 2
        sel = (zs <= zmax) & (zs >= zmin) & np.isnan(out[:, 0, 0])
        if not sel.any():
            continue
        v = ds[var].sel(z=zs[sel], x=xs, y=ys, method="nearest").transpose("z", "x", "y").values
        out[sel] = v
    # air: fill downward-first so stations at the surface sit in rock velocity
    for k in range(zs.size - 2, -1, -1):
        out[k] = np.where(np.isnan(out[k]), out[k + 1], out[k])
    below = np.isnan(out)
    zz = np.broadcast_to(zs[:, None, None], out.shape)
    out[below] = pnsn_1d(zz[below], phase)
    return out


def _pykonal_one(args):
    """One PointSourceSolver solve (refined spherical grid around the source); T at the receivers."""
    import pykonal
    from scipy.interpolate import RegularGridInterpolator

    vel_xyd, x0, dx, src_xyd, rec_xyd = args
    s = pykonal.solver.PointSourceSolver(coord_sys="cartesian")
    s.velocity.min_coords = x0
    s.velocity.node_intervals = dx, dx, dx
    s.velocity.npts = vel_xyd.shape
    s.velocity.values = vel_xyd
    s.src_loc = np.asarray(src_xyd, dtype=float)
    s.solve()
    axes = [x0[i] + dx * np.arange(vel_xyd.shape[i]) for i in range(3)]
    return RegularGridInterpolator(axes, s.traveltime.values, bounds_error=False, fill_value=np.nan)(rec_xyd)


def travel_times(
    vel: np.ndarray, xs, ys, zs, dx, sources_xyz, receivers_xyz, solver: str = "pykonal"
) -> np.ndarray:
    """T[source, receiver] (s). Grid in fteikpy order (depth-down, x, y); sources are stations (reciprocity).

    pykonal PointSourceSolver is the default: against analytic times on this grid size (0.5 km) it is 2-3x
    more accurate than fteikpy (event-demeaned RMS 4.6 vs 10.5 ms homogeneous, 5.5 vs 14.8 ms for a gradient)
    at ~1.2x the cost; see docs/eikonal_benchmark.md.
    """
    if solver == "fteikpy":
        from fteikpy import Eikonal3D

        origin = (-zs[0], xs[0], ys[0])
        eik = Eikonal3D(vel, gridsize=(dx, dx, dx), origin=origin)
        src = [(-z, x, y) for x, y, z in sources_xyz]
        rec = np.array([(-z, x, y) for x, y, z in receivers_xyz])
        tts = eik.solve(src, nsweep=2)
        return np.array([tt(rec) for tt in tts])
    if solver != "pykonal":
        raise ValueError(f"unknown solver {solver!r}")
    import os
    from concurrent.futures import ProcessPoolExecutor

    vel_xyd = np.ascontiguousarray(np.transpose(vel, (1, 2, 0)), dtype=float)  # (x, y, depth)
    x0 = (xs[0], ys[0], -zs[0])
    rec = np.array([(x, y, -z) for x, y, z in receivers_xyz])
    jobs = [(vel_xyd, x0, dx, (x, y, -z), rec) for x, y, z in sources_xyz]
    with ProcessPoolExecutor(max_workers=min(8, os.cpu_count() or 1)) as ex:
        return np.array(list(ex.map(_pykonal_one, jobs)))


def summarize(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Per-phase RMS of event-demeaned residuals, and per-station terms."""
    rows = []
    for ph, g in df.groupby("phase"):
        r = {"phase": ph, "n_picks": len(g), "n_events": g.event.nunique(), "n_stations": g.sta.nunique()}
        for m in ("1d", "3d"):
            res = g["tt_obs"] - g[f"tt_{m}"]
            dm = res - res.groupby(g["event"]).transform("mean")
            r[f"rms_{m}"] = float(np.sqrt(np.mean(res**2)))
            r[f"rms_{m}_demeaned"] = float(np.sqrt(np.mean(dm**2)))
        r["rms_pnsn_reported"] = float(np.sqrt(np.nanmean(g["pnsn_res"] ** 2)))
        rows.append(r)
    per = df.assign(res_1d=df.tt_obs - df.tt_1d, delay_3d_1d=df.tt_3d - df.tt_1d)
    st = (
        per.groupby(["phase", "net", "sta"])
        .agg(
            n=("event", "size"),
            res_1d=("res_1d", "mean"),
            delay_3d_1d=("delay_3d_1d", "mean"),
            pnsn_res=("pnsn_res", "mean"),
        )
        .reset_index()
    )
    return pd.DataFrame(rows), st


def station_correlation(st: pd.DataFrame, min_n: int = 5) -> dict:
    out = {}
    for ph, g in st[st.n >= min_n].groupby("phase"):
        out[ph] = {
            "n_stations": len(g),
            "corr(res_1d, delay_3d_1d)": float(np.corrcoef(g.res_1d, g.delay_3d_1d)[0, 1])
            if len(g) > 2
            else float("nan"),
        }
    return out


def write_report(path: Path, summ: pd.DataFrame, corr: dict) -> None:
    path.write_text(
        summ.to_string(index=False, float_format=lambda v: f"{v:.3f}")
        + "\n\n"
        + json.dumps(corr, indent=1)
        + "\n"
    )
