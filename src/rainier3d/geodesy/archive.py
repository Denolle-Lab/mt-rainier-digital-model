"""Deterministic fetching of GNSS products from their original archives.

Every download goes through :func:`fetch`: the file is cached under data/raw/gnss/<archive>/, and a line is
added to data/raw/gnss/manifest.csv (archive, url, path relative to the manifest, retrieved UTC, bytes,
sha256). A rebuild
reads the cache, so results depend only on the cached bytes; `verify_manifest` checks them. Parsers turn
each archive's format into one table (see ``COLUMNS``) so the rest of the pipeline never sees archive
specifics."""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import logging
import os
import re
from pathlib import Path

import numpy as np
import pandas as pd
import requests

log = logging.getLogger(__name__)

# common daily table: one row per site and day; e, n, u in metres relative to the first epoch of the series
COLUMNS = [
    "site",
    "date",
    "decyear",
    "e",
    "n",
    "u",
    "se",
    "sn",
    "su",
    "lon",
    "lat",
    "height",
    "archive",
    "frame",
]
USER_AGENT = "rainier3d GNSS pipeline (github.com/Denolle-Lab/mt-rainier-digital-model)"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _manifest_path(path: Path, manifest: Path) -> str:
    return Path(os.path.relpath(path.resolve(), manifest.parent.resolve())).as_posix()


def _record(manifest: Path, archive: str, url: str, path: Path, retrieved: dt.datetime) -> None:
    new = not manifest.exists()
    manifest.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["archive", "url", "path", "retrieved_utc", "bytes", "sha256"])
        w.writerow(
            [
                archive,
                url,
                _manifest_path(path, manifest),
                retrieved.isoformat(timespec="seconds"),
                path.stat().st_size,
                sha256(path),
            ]
        )


def _recorded(path: Path, manifest: Path) -> bool:
    if not manifest.exists():
        return False
    with open(manifest) as f:
        return any((manifest.parent / r["path"]).resolve() == path.resolve() for r in csv.DictReader(f))


def fetch(
    url: str, path: Path, archive: str, manifest: Path, timeout: int = 120, refresh: bool = False
) -> Path:
    """Download ``url`` to ``path`` once and record it in the manifest; later calls read the cache. A cached
    file missing from the manifest (e.g. a deleted manifest) is recorded again, dated by its mtime."""
    if path.exists() and not refresh:
        if not _recorded(path, manifest):
            mtime = dt.datetime.fromtimestamp(path.stat().st_mtime, dt.UTC)
            _record(manifest, archive, url, path, mtime)
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_name(path.name + ".part")
    with requests.get(url, timeout=timeout, headers={"User-Agent": USER_AGENT}, stream=True) as r:
        r.raise_for_status()
        with open(part, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
    part.replace(path)  # a failed download never leaves a partial file at the cached path
    _record(manifest, archive, url, path, dt.datetime.now(dt.UTC))
    log.info("fetched %s (%d bytes)", url, path.stat().st_size)
    return path


def verify_manifest(manifest: Path) -> list[str]:
    """Files whose bytes no longer match the manifest (latest entry per file). Relative paths are read from
    the manifest's folder; absolute paths (older manifests) are used as they are."""
    latest = {}
    with open(manifest) as f:
        for row in csv.DictReader(f):
            latest[(manifest.parent / row["path"]).resolve()] = row
    return [str(p) for p, row in latest.items() if not p.exists() or sha256(p) != row["sha256"]]


# ---------------------------------------------------------------- UNR (Nevada Geodetic Laboratory)
UNR_TENV3 = "https://geodesy.unr.edu/gps_timeseries/IGS20/tenv3/IGS20/{site}.tenv3"
UNR_TENV3_NA = "https://geodesy.unr.edu/gps_timeseries/IGS20/tenv3/NA/{site}.NA.tenv3"  # North-America-fixed
UNR_HOLDINGS = "https://geodesy.unr.edu/NGLStationPages/DataHoldings.txt"


def parse_unr_tenv3(path: Path, frame: str = "IGS20") -> pd.DataFrame:
    """NGL tenv3 (IGS20): east/north/up as integer + fractional metres from a reference position."""
    d = pd.read_csv(path, sep=r"\s+", header=0)
    d.columns = [c.strip("_").strip() for c in d.columns]
    e = d["e0(m)"] + d["east(m)"]
    n = d["n0(m)"] + d["north(m)"]
    u = d["u0(m)"] + d["up(m)"]
    out = pd.DataFrame(
        {
            "site": d["site"].astype(str),
            "date": pd.to_datetime(d["YYMMMDD"], format="%y%b%d"),
            "decyear": d["yyyy.yyyy"].astype(float),
            "e": e - e.iloc[0],
            "n": n - n.iloc[0],
            "u": u - u.iloc[0],
            "se": d["sig_e(m)"],
            "sn": d["sig_n(m)"],
            "su": d["sig_u(m)"],
            "lon": d["longitude(deg)"],
            "lat": d["latitude(deg)"],
            "height": d["height(m)"],
            "archive": "unr",
            "frame": frame,
        }
    )
    return out[COLUMNS]


def decyear(dates: pd.Series) -> np.ndarray:
    d = pd.to_datetime(dates)
    y = d.dt.year
    start = pd.to_datetime(y.astype(str) + "-01-01")
    end = pd.to_datetime((y + 1).astype(str) + "-01-01")
    return (y + (d - start) / (end - start)).to_numpy(float)


UNR_STEPS = "https://geodesy.unr.edu/NGLStationPages/steps.txt"


def parse_unr_holdings(path: Path, bbox) -> pd.DataFrame:
    """NGL station list, restricted to a lon/lat box. Longitudes are given 0-360 for some sites."""
    d = pd.read_csv(path, sep=r"\s+", usecols=range(11), header=0)
    d.columns = ["site", "lat", "lon", "height", "X", "Y", "Z", "begin", "end", "modified", "nsol"]
    d["lon"] = ((d["lon"] + 180) % 360) - 180
    w, s, e, n = bbox
    return d[(d.lon >= w) & (d.lon <= e) & (d.lat >= s) & (d.lat <= n)].reset_index(drop=True)


def parse_unr_steps(path: Path) -> pd.DataFrame:
    """NGL steps file: code 1 = equipment or processing change, code 2 = earthquake (distance, magnitude)."""
    rows = []
    for line in path.read_text(errors="replace").splitlines():
        p = line.split()
        if len(p) >= 3 and p[2] in ("1", "2"):
            rows.append(
                {
                    "site": p[0],
                    "date": pd.to_datetime(p[1], format="%y%b%d", errors="coerce"),
                    "code": int(p[2]),
                    "what": " ".join(p[3:]),
                }
            )
    d = pd.DataFrame(rows).dropna(subset=["date"])
    d["decyear"] = decyear(d["date"])
    return d


# ---------------------------------------------------------------- PANGA (Central Washington University)
# Daily GIPSY solutions, North-America-fixed ("raw" = outlier-screened, not detrended). One zip holds every
# site as <proc>/<SITE>.{lat,lon,rad}: DQRFIT output with a '#' header (model, step epochs) and columns
# decimal year, position (mm), sigma (mm); lat = north, lon = east, rad = up. Acknowledge: "GPS time series
# provided by the Pacific Northwest Geodetic Array, Central Washington University".
PANGA_ZIP = "https://www.geodesy.org/panga/officialresults/archives/panga_{proc}.zip"
PANGA_HVEL = "https://www.geodesy.org/data/map/velocity_field/panga_nam20_hvel.xml"
PANGA_VVEL = "https://www.geodesy.org/data/map/velocity_field/panga_nam20_vvel.xml"


def panga_date(t: np.ndarray) -> pd.DatetimeIndex:
    """PANGA decimal year -> date: Jan 1 + round(frac * days_in_year) - 1 (checked against GAGE dates)."""
    t = np.asarray(t, float)
    y = np.floor(t).astype(int)
    ndays = np.where((y % 4 == 0) & ((y % 100 != 0) | (y % 400 == 0)), 366, 365)
    doy = np.rint((t - y) * ndays).astype(int) - 1
    return pd.to_datetime(y.astype(str), format="%Y") + pd.to_timedelta(doy, unit="D")


def parse_panga_component(text: str) -> tuple[pd.DataFrame, list[float]]:
    """One PANGA component file -> (decimal year, value mm, sigma mm) and the step epochs of its header."""
    steps = [float(x) for x in re.findall(r"heav\(t-\s*([0-9.]+)\s*\)", text)]
    rows = [ln.split() for ln in text.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
    d = pd.DataFrame(rows, columns=["t", "v", "s"]).astype(float)
    return d, steps


def parse_panga_site(zf, site: str, proc: str = "raw") -> tuple[pd.DataFrame, list[float]]:
    """A site's three components from the PANGA zip -> common table (metres) and the union of step epochs."""
    comps, steps = {}, set()
    for c, k in (("lat", "n"), ("lon", "e"), ("rad", "u")):
        d, st = parse_panga_component(zf.read(f"{proc}/{site}.{c}").decode(errors="replace"))
        comps[k] = d.set_index("t")
        steps |= set(st)
    t = sorted(set(comps["e"].index) & set(comps["n"].index) & set(comps["u"].index))
    out = pd.DataFrame({"decyear": t})
    for k in ("e", "n", "u"):
        out[k] = comps[k].loc[t, "v"].to_numpy() / 1000.0
        out["s" + k] = comps[k].loc[t, "s"].to_numpy() / 1000.0
    for k in ("e", "n", "u"):
        out[k] -= out[k].iloc[0]
    out["site"] = site.upper()
    out["date"] = panga_date(out["decyear"].to_numpy())
    out["archive"], out["frame"] = "panga", "NA-fixed (PANGA raw)"
    out["lon"] = out["lat"] = out["height"] = np.nan
    return out[COLUMNS], sorted(steps)


def parse_panga_velocities(hvel: Path, vvel: Path | None = None) -> pd.DataFrame:
    """PANGA velocity field (NA20-fixed): site, lat, lon, ve, vn (mm/yr) and sigmas; vu when vvel is given."""
    import xml.etree.ElementTree as ET

    def read(p):
        return pd.DataFrame([m.attrib for m in ET.parse(p).getroot().iter("marker")])

    h = read(hvel)
    out = pd.DataFrame(
        {
            "site": h["name"].str.upper(),
            "lat": h["lat"].astype(float),
            "lon": h["lng"].astype(float),
            "ve": h["x"].astype(float),
            "vn": h["y"].astype(float),
            "se": h["x_sig"].astype(float),
            "sn": h["y_sig"].astype(float),
        }
    )
    if vvel is not None:
        v = read(vvel)
        out = out.merge(
            pd.DataFrame(
                {"site": v["name"].str.upper(), "vu": v["y"].astype(float), "su": v["y_sig"].astype(float)}
            ),
            on="site",
            how="left",
        )
    return out
