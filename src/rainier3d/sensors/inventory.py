"""Sensor inventory for the domain: one list of *sites*, each carrying its *sensors*.

A site is a place (lon, lat, elevation); a sensor is one instrument at that site (e.g. the
broadband seismometer and the accelerometer of UW.RCM are two sensors of one site). Every sensor
has a family (configs/sensor_families.yaml), a status (operating / retired) and dates.

Sources
  FDSN (EarthScope station service, channel level): seismic, strong motion, nodes, infrasound,
      strain/tilt, MT. Channels grouped per (network, station, location, band+instrument).
  2025 Rainier nodes: FDSN network Z5 (2025), fetched whole, also beyond the domain box.
  GNSS: EarthScope/UNAVCO GNSS site metadata web service.
  Meteorology & streamflow: gaia-hazlab/catalog GeoJSON (Synoptic), cached by mt-rainier-smart-sensing.
  DAS: the Paradise-Nisqually Entrance channel table (per-channel coordinates and lithology).
"""

from __future__ import annotations

import io
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import yaml

from rainier3d.config.domain import REPO, Domain
from rainier3d.config.platform import as_of, as_of_datetime, local_input

FAMILIES = REPO / "configs" / "sensor_families.yaml"
FDSN = "https://service.earthscope.org/fdsnws/station/1/query"
GNSS = "https://web-services.unavco.org/gps/metadata/sites/v1"
# The data freeze of configs/platform.yaml: a sensor is operating if its last epoch ends after it.
NOW = as_of_datetime()


def families() -> dict:
    return yaml.safe_load(FAMILIES.read_text())


def _status(end) -> str:
    if end is None or pd.isna(end):
        return "operating"
    t = pd.Timestamp(end)
    return "operating" if (t.tz_localize(None) if t.tzinfo else t) > NOW else "retired"


def _date(t) -> str | None:
    return None if t is None or pd.isna(t) else pd.Timestamp(t).strftime("%Y-%m-%d")


def is_node_2025(site_id: str, cfg: dict) -> bool:
    """A site of the 2025 Rainier node array (FDSN network in configs/sensor_families.yaml nodes_2025)."""
    return site_id.startswith(cfg["nodes_2025"]["network"] + ".")


def _in(dom: Domain, lon, lat):
    w, s, e, n = dom.bbox_4326
    return (lon >= w) & (lon <= e) & (lat >= s) & (lat <= n)


# ---------------------------------------------------------------- FDSN
def _fdsn_text(cache: Path, **params) -> Path:
    if not cache.exists():
        r = requests.get(FDSN, params=dict(params, level="channel", format="text"), timeout=180)
        r.raise_for_status()
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(r.text)
    return cache


def fdsn_channels(dom: Domain, cfg: dict) -> pd.DataFrame:
    w, s, e, n = dom.bbox_4326
    box = _fdsn_text(
        # the file name carries every variable of the query, so a changed query cannot reuse an old cache
        dom.path("raw") / "sensors" / f"fdsn_channels_{dom.name}_{as_of()}.txt",
        minlatitude=s,
        maxlatitude=n,
        minlongitude=w,
        maxlongitude=e,
        endtime=f"{as_of()}T23:59:59",
    )
    nd = cfg["nodes_2025"]
    nodes = _fdsn_text(
        dom.path("raw") / "sensors" / f"fdsn_channels_{nd['network']}_{nd['start']}_{nd['end']}.txt",
        network=nd["network"],
        starttime=nd["start"],
        endtime=nd["end"],
    )
    df = pd.concat([pd.read_csv(f, sep="|", dtype=str) for f in (box, nodes)]).drop_duplicates()
    df.columns = [c.strip().lstrip("#").strip() for c in df.columns]
    for c in ("Latitude", "Longitude", "Elevation", "SampleRate"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["Location"] = df["Location"].fillna("")
    df["StartTime"] = pd.to_datetime(df["StartTime"], errors="coerce")
    df["EndTime"] = pd.to_datetime(df["EndTime"], errors="coerce")
    return df


def classify(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    rules = [(re.compile(rx), fam, lab) for rx, fam, lab in cfg["fdsn_rules"]]
    fam, lab = [], []
    for ch in df["Channel"]:
        hit = next(((f, lab_) for rx, f, lab_ in rules if rx.match(ch)), (None, None))
        fam.append(hit[0])
        lab.append(hit[1])
    out = df.assign(family=fam, kind=lab)
    return out[out.family.notna() & ~out.Network.isin(cfg["exclude_networks"])]


def fdsn_sites(dom: Domain, cfg: dict) -> list[dict]:
    df = classify(fdsn_channels(dom, cfg), cfg)
    sites = []
    for (net, sta), g in df.groupby(["Network", "Station"]):
        sensors = []
        for (loc, bi), h in g.groupby([g.Location, g.Channel.str[:2]]):
            end = None if h.EndTime.isna().any() else h.EndTime.max()
            sensors.append(
                dict(
                    family=h.family.iloc[0],
                    kind=h.kind.iloc[0],
                    channels=f"{loc + '.' if loc else ''}{bi}{''.join(sorted(set(h.Channel.str[2])))}",
                    sps=float(h.SampleRate.max()),
                    start=_date(h.StartTime.min()),
                    end=_date(end),
                    status=_status(end),
                    description=str(h.SensorDescription.dropna().iloc[0])[:60]
                    if h.SensorDescription.notna().any()
                    else "",
                )
            )
        r = g.iloc[0]
        sites.append(
            dict(
                id=f"{net}.{sta}",
                name=f"{net}.{sta}",
                source="FDSN (EarthScope)",
                lon=float(r.Longitude),
                lat=float(r.Latitude),
                elev=float(r.Elevation),
                url=f"https://ds.iris.edu/mda/{net}/{sta}",
                sensors=sensors,
            )
        )
    return sites


# ---------------------------------------------------------------- GNSS
def gnss_sites(dom: Domain) -> list[dict]:
    cache = dom.path("raw") / "sensors" / "gnss_sites.csv"
    if not cache.exists():
        w, s, e, n = dom.bbox_4326
        r = requests.get(
            GNSS, params=dict(minlatitude=s, maxlatitude=n, minlongitude=w, maxlongitude=e), timeout=120
        )
        r.raise_for_status()
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(r.text)
    d = pd.read_csv(
        io.StringIO("\n".join(ln for ln in cache.read_text().splitlines() if not ln.startswith("#"))),
        header=None,
    )
    head = [h.split("[")[0] for h in cache.read_text().splitlines()[0].lstrip("#fields=").split(",")]
    d.columns = head[: d.shape[1]]
    out = []
    for sid, g in d.groupby("ID"):
        start = pd.to_datetime(g.session_start_time, errors="coerce").min()
        stop = pd.to_datetime(g.session_stop_time, errors="coerce")
        end = None if stop.isna().any() else stop.max()
        # the service reports the latest data epoch as the stop time: recent = still recording
        if end is not None and (NOW - (end.tz_localize(None) if end.tzinfo else end)).days < 30:
            end = None
        r = g.iloc[-1]
        out.append(
            dict(
                id=f"gnss-{sid}",
                name=f"{sid} {r.station_name}",
                source="EarthScope GNSS (UNAVCO)",
                lon=float(r.longitude),
                lat=float(r.latitude),
                elev=None,  # service heights unreliable
                url=f"https://www.unavco.org/data/gps-gnss/data-access-methods/dai2/app/dai2.html#4Char={sid}",
                sensors=[
                    dict(
                        family="gnss",
                        kind="GNSS receiver",
                        channels=str(r.receiver_type),
                        start=_date(start),
                        end=_date(end),
                        status=_status(end),
                        description=str(r.antenna_type),
                    )
                ],
            )
        )
    return out


# ---------------------------------------------------------------- Synoptic met / hydro
def synoptic_sites(dom: Domain) -> list[dict]:
    out = []
    for fname, fam, kind in (
        ("precip-stations.geojson", "meteorology", "weather / precipitation"),
        ("snotel_stations.geojson", "meteorology", "SNOTEL snow"),
        ("streamflow-stations.geojson", "hydrology", "stream gauge"),
    ):
        stations = local_input("smart_sensing_stations", dom.path("raw"))
        for f in json.loads((stations / fname).read_text())["features"]:
            p = f["properties"]
            lon, lat = (float(v) for v in f["geometry"]["coordinates"][:2])
            if not _in(dom, lon, lat):
                continue
            end = p.get("end_datetime")
            elev = p.get("elevation")
            out.append(
                dict(
                    id=f"syn-{p['stid']}",
                    name=f"{p['stid']} {p.get('name', '')}".strip(),
                    source="Synoptic via gaia-hazlab/catalog",
                    lon=lon,
                    lat=lat,
                    elev=float(elev) * 0.3048 if elev is not None else None,  # Synoptic reports feet
                    url=f"https://explore.synopticdata.com/{p['stid']}/metadata",
                    sensors=[
                        dict(
                            family=fam,
                            kind=kind,
                            channels=", ".join(p.get("sensor_variables") or [])[:80],
                            start=_date(p.get("start_datetime")),
                            end=_date(end),
                            status=_status(end),
                        )
                    ],
                )
            )
    return out


# ---------------------------------------------------------------- DAS
def das_channels(path: Path) -> pd.DataFrame:
    d = pd.read_csv(path)
    d = d.rename(
        columns={
            "Latitude [°]": "lat",
            "Longitude [°]": "lon",
            "Elevation [m]": "elev",
            "Optical Distance [m]": "optical_m",
            "Distance along road [m]": "road_m",
        }
    )
    return d.dropna(subset=["lat", "lon"])


def merge_colocated(sites: list[dict], tol_m: float = 60.0) -> list[dict]:
    """Merge sites closer than tol_m (e.g. a SNOTEL mast next to a seismometer); nodes stay single."""
    lat0 = np.mean([s["lat"] for s in sites])
    xy = np.array([(s["lon"] * 111320 * np.cos(np.deg2rad(lat0)), s["lat"] * 110540) for s in sites])
    used, out = np.zeros(len(sites), bool), []
    for i, s in enumerate(sites):
        if used[i]:
            continue
        used[i] = True
        if s["sensors"][0]["family"] == "nodes":
            out.append(s)
            continue
        near = np.where(~used & (np.hypot(*(xy - xy[i]).T) < tol_m))[0]
        near = [j for j in near if sites[j]["sensors"][0]["family"] != "nodes"]
        if near:
            s = dict(s, sensors=list(s["sensors"]), name=s["name"])
            for j in near:
                used[j] = True
                s["sensors"] += sites[j]["sensors"]
                s["name"] += " + " + sites[j]["name"]
        out.append(s)
    return out


def inventory(dom: Domain) -> list[dict]:
    cfg = families()
    sites = fdsn_sites(dom, cfg) + gnss_sites(dom) + synoptic_sites(dom)
    # nodes are all kept (the 2025 deployment extends beyond the model domain); others are clipped
    sites = [s for s in sites if is_node_2025(s["id"], cfg) or _in(dom, s["lon"], s["lat"])]
    for s in sites:
        s["in_model_domain"] = bool(_in(dom, s["lon"], s["lat"]))
    for s in sites:
        s["status"] = "operating" if any(x["status"] == "operating" for x in s["sensors"]) else "retired"
    return merge_colocated(sites)
