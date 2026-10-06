"""Earthquakes under the map area from the USGS ComCat catalog (PNSN). Depth is km below sea level, so y = −depth."""
from __future__ import annotations

import csv
import io
import json
import urllib.parse
from pathlib import Path

import numpy as np

from . import extent as E
from . import fetch

COMCAT = "https://earthquake.usgs.gov/fdsnws/event/1/query"
START = "1980-01-01"
MIN_EVENTS = 1000


def catalog_url(box: E.Box = E.OVERVIEW, as_of: str | None = None) -> str:
    q = {"format": "csv", "minlatitude": box.south, "maxlatitude": box.north, "minlongitude": box.west, "maxlongitude": box.east,
         "starttime": START, "minmagnitude": -2, "orderby": "time-asc"}
    if as_of:   # a frozen catalogue: events up to the end of the as-of day
        q["endtime"] = f"{as_of}T23:59:59"
    return f"{COMCAT}?{urllib.parse.urlencode(q)}"


def parse_catalog(text: str) -> list[tuple]:
    rows = []
    for r in csv.DictReader(io.StringIO(text)):
        if r["depth"] and r["mag"]:
            rows.append((float(r["longitude"]), float(r["latitude"]), float(r["depth"]), float(r["mag"]), r["time"][:10]))
    return rows


def check_quakes(meta: dict) -> list[str]:
    return [f"earthquakes: only {meta['count']} events (expected at least {MIN_EVENTS})"] if meta["count"] < MIN_EVENTS else []


def build_quakes(out_dir, cache_dir, ground, get=fetch.get, min_events: int = MIN_EVENTS, as_of: str | None = None) -> dict:
    path = Path(cache_dir) / "quakes" / (f"comcat_{as_of}.csv" if as_of else "comcat.csv")
    url = catalog_url(as_of=as_of)
    body = get(url, path, validate=lambda b: b.count(b"\n") > min_events) if get is fetch.get else get(url, path)
    b = E.OVERVIEW   # a catalog cached for an earlier, larger box keeps only the events on this map
    rows = [r for r in parse_catalog(body.decode()) if b.west <= r[0] <= b.east and b.south <= r[1] <= b.north]
    if len(rows) < min_events:   # refuse before anything is written, so a bad refresh can't replace the bundle
        raise ValueError(f"earthquakes: only {len(rows)} events (expected at least {min_events})")
    rec = np.array([(E.to_x(lon), -d, E.to_z(lat), m) for lon, lat, d, m, _ in rows], "<f4").reshape(-1, 4)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    rec.tofile(out / "quakes.bin")
    above = int(sum(1 for x, y, z, _ in rec if y > ground(float(x), float(z))))
    depth = np.array([d for _, _, d, _, _ in rows]) if rows else np.zeros(1)
    meta = {
        "count": len(rows), "drawn": len(rows) - above, "aboveGround": above,
        "from": min(t for *_, t in rows) if rows else None, "to": max(t for *_, t in rows) if rows else None,
        "magMin": min(m for _, _, _, m, _ in rows) if rows else None, "magMax": max(m for _, _, _, m, _ in rows) if rows else None,
        "depthP50": float(np.percentile(depth, 50)), "depthP90": float(np.percentile(depth, 90)),
        "source": "USGS ComCat (PNSN), depth in km below sea level",
    }
    (out / "quakes.json").write_text(json.dumps(meta, indent=1))
    return meta
