"""PNSN events, analyst picks and stations for a catalogue relocation (S25).

Events: ComCat (network uw) in the domain box. Picks: the phase-data QuakeML of each event (P and S arrivals
of the preferred origin), cached in data/raw/pnsn/quakeml/ (shared with S6/S13). Stations: EarthScope FDSN,
inside the domain (the travel-time grids cover the domain only).
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from rainier3d.config.domain import Domain
from rainier3d.validate import pnsn

log = logging.getLogger(__name__)


def _get(url: str, tries: int = 4) -> requests.Response:
    """GET with retries and backoff (ComCat occasionally drops a request or a DNS lookup)."""
    import time

    for k in range(tries):
        try:
            r = requests.get(url, timeout=60)
            r.raise_for_status()
            return r
        except requests.RequestException:
            if k == tries - 1:
                raise
            time.sleep(2 * (k + 1))
    raise AssertionError


def _quakeml(ev: dict, qdir: Path) -> Path | None:
    q = qdir / f"{ev['id']}.xml"
    if q.exists():
        return q
    det = _get(ev["properties"]["detail"]).json()
    pdata = det["properties"]["products"].get("phase-data")
    if not pdata:
        return None
    q.write_bytes(_get(pdata[0]["contents"]["quakeml.xml"]["url"]).content)
    return q


def _picks(ev: dict, q: Path) -> list[dict]:
    from obspy import read_events

    e = read_events(str(q))[0]
    o = e.preferred_origin() or e.origins[0]
    picks = {p.resource_id: p for p in e.picks}
    rows = []
    for a in o.arrivals:
        p = picks.get(a.pick_id)
        if p is None or a.phase not in ("P", "S"):
            continue
        w = p.waveform_id
        rows.append(
            {
                "event": ev["id"],
                "origin_time": o.time.datetime.isoformat(),
                "lon": o.longitude,
                "lat": o.latitude,
                "depth_km": o.depth / 1e3 if o.depth is not None else np.nan,
                "mag": ev["properties"]["mag"],
                "net": w.network_code,
                "sta": w.station_code,
                "phase": a.phase,
                "pick_time": p.time.datetime.isoformat(),
                "tt_obs": float(p.time - o.time),
                "pnsn_res": a.time_residual,
            }
        )
    return rows


def fetch(dom: Domain, start: str, end: str, minmag: float, cache: Path, workers: int = 4) -> pd.DataFrame:
    """One row per P/S pick of every event with phase data; cached as <cache>/picks.csv."""
    out = cache / "picks.csv"
    if out.exists():
        return pd.read_csv(out)
    cache.mkdir(parents=True, exist_ok=True)
    qdir = dom.path("raw") / "pnsn" / "quakeml"
    qdir.mkdir(parents=True, exist_ok=True)
    events = pnsn.fetch_events(dom, start, end, minmag)
    log.info("%d events from ComCat, %s to %s, M >= %s", len(events), start, end, minmag)
    with ThreadPoolExecutor(max_workers=workers) as ex:  # a few requests at a time, as ComCat asks
        files = list(ex.map(lambda e: _quakeml(e, qdir), events))
    rows = []
    for ev, q in zip(events, files, strict=True):
        if q is not None:
            rows += _picks(ev, q)
    df = pd.DataFrame(rows)
    df.to_csv(out, index=False)
    log.info("%d picks for %d events (%d without phase data)", len(df), df.event.nunique(), files.count(None))
    return df


def stations(dom: Domain, picks: pd.DataFrame, cache: Path) -> pd.DataFrame:
    """Picked stations inside the domain, with UTM x, y (m) and elevation (m); one row per station code."""
    from obspy.clients.fdsn import Client
    from pyproj import Transformer

    out = cache / "stations.csv"
    if out.exists():
        return pd.read_csv(out)
    lon0, lat0, lon1, lat1 = dom.bbox_4326
    inv = Client("IRIS").get_stations(
        network=",".join(sorted(picks["net"].unique())),
        level="station",
        minlatitude=lat0,
        maxlatitude=lat1,
        minlongitude=lon0,
        maxlongitude=lon1,
    )
    rows = [{"net": n.code, "sta": s.code, "lon": s.longitude, "lat": s.latitude, "elev": s.elevation}
            for n in inv for s in n]  # fmt: skip
    st = pd.DataFrame(rows).drop_duplicates(["net", "sta"])
    used = picks[["net", "sta"]].drop_duplicates()
    st = st.merge(used, on=["net", "sta"])
    st["x"], st["y"] = Transformer.from_crs(4326, dom.crs, always_xy=True).transform(
        st.lon.values, st.lat.values
    )
    x0, y0, x1, y1 = dom.bounds
    st = st[(st.x > x0) & (st.x < x1) & (st.y > y0) & (st.y < y1)]
    dup = st.sta.duplicated(keep=False)
    if dup.any():  # NonLinLoc keys stations by code: keep the network with the most picks
        n = picks.groupby(["net", "sta"]).size().rename("n").reset_index()
        st = (
            st.merge(n, on=["net", "sta"])
            .sort_values("n", ascending=False)
            .drop_duplicates("sta")
            .drop(columns="n")
        )
    st.to_csv(out, index=False)
    return st.reset_index(drop=True)
