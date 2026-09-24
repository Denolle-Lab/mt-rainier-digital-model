"""Active seismic stations around Mount Rainier from the EarthScope FDSN station service.

Instrument kinds come from the first two letters of each channel code; station-health channels are ignored and an
unknown code fails the build. Codes within SITE_RADIUS_M of each other form one site (the Axial atlas's rule).
"""
from __future__ import annotations

import datetime as dt
import json
import math
import re
import urllib.parse
from pathlib import Path

from . import extent as E
from . import fetch

FDSN = "https://service.earthscope.org/fdsnws/station/1/query"
CENTER, RADIUS_DEG = (46.853, -121.760), 0.45
SITE_RADIUS_M = 150

KINDS = ["seismometer", "geophone", "infrasound", "accelerometer", "gnss", "tiltmeter", "strainmeter"]
_KIND = {
    "BH": ("seismometer", "broadband"), "HH": ("seismometer", "broadband"),
    "EH": ("seismometer", "short period"), "EL": ("seismometer", "short period"),
    "CH": ("geophone", None),
    "BD": ("infrasound", None), "HD": ("infrasound", None), "CD": ("infrasound", None),
    "EN": ("accelerometer", None), "HN": ("accelerometer", None),
    **{p: ("gnss", None) for p in ("GA", "GE", "GN", "GS", "GP", "GL")},
    "HA": ("tiltmeter", None), "HK": ("tiltmeter", None),
    "BS": ("strainmeter", None), "LS": ("strainmeter", None),
}
# State of health, weather at CC.PR04, and the low-rate duplicates (LN at NP stations, LH at PB.B941).
_IGNORE = set("AC CP DE DS HU LC LD LH LI LK LN LO LP LR LW ME OC QB QD QG QL QR QW RA RC RD RE RK RR RS "
              "SB SC SD SI SM SN SP SR SS ST SW VA VB VC VD VE VF VH VK VM VP VS VV".split())
OPERATORS = {
    "CC": "USGS Cascades Volcano Observatory",
    "UW": "Pacific Northwest Seismic Network",
    "NP": "USGS National Strong-Motion Project",
    "PB": "EarthScope borehole network",
}
EXCLUDED_NETWORKS = {"SY": "synthetic seismograms, not an instrument"}
EXCLUDED_STATIONS = {"C0.PALI": "duplicate of CC.PALI under a Colorado network code"}


def kind_of(code: str):
    p = code[:2]
    if p in _IGNORE:
        return None
    return _KIND[p]


def clean_name(name: str) -> str:
    name = re.sub(r",\s*(WA|Washington)\b.*$", "", name.strip())
    parts = [p.strip() for p in name.split(",")]
    parts = [p for p in parts if not re.fullmatch(r"(Mount|Mt\.?)\s+Rainier", p)]
    return ", ".join(parts) or name


def _rows(text: str):
    for line in text.splitlines():
        if line and not line.startswith("#"):
            yield [f.strip() for f in line.split("|")]


def _dist_m(a, b) -> float:
    return math.hypot((a["lon"] - b["lon"]) * E.KX, (a["lat"] - b["lat"]) * E.KZ) * 1000


def query_url(level: str, as_of: str) -> str:
    q = {"latitude": CENTER[0], "longitude": CENTER[1], "maxradius": RADIUS_DEG, "endafter": as_of, "level": level, "format": "text"}
    return f"{FDSN}?{urllib.parse.urlencode(q)}"


def _load_majors() -> dict:
    return json.loads((Path(__file__).resolve().parents[1] / "major_stations.json").read_text())


def build_stations(cache_dir, get=fetch.get, as_of: str | None = None, majors: dict | None = None) -> dict:
    as_of = as_of or dt.date.today().isoformat()
    majors = _load_majors() if majors is None else majors
    cache = Path(cache_dir) / "stations"
    chan_text = get(query_url("channel", as_of), cache / f"channels_{as_of}.txt").decode()
    sta_text = get(query_url("station", as_of), cache / f"stations_{as_of}.txt").decode()
    names = {}
    for f in _rows(sta_text):
        if not f[7] or f[7] > as_of:   # the open epoch wins over closed ones
            names[f"{f[0]}.{f[1]}"] = f[5]

    stations, excluded, returned, excluded_codes = {}, {}, set(), set()
    for f in _rows(chan_text):
        net, sta, cha = f[0], f[1], f[3]
        code = f"{net}.{sta}"
        if f[16] and f[16][:10] <= as_of:   # channel closed before the snapshot
            continue
        returned.add(code)
        if net in EXCLUDED_NETWORKS:
            excluded[f"{net}.*"] = EXCLUDED_NETWORKS[net]; excluded_codes.add(code)
            continue
        if code in EXCLUDED_STATIONS:
            excluded[code] = EXCLUDED_STATIONS[code]; excluded_codes.add(code)
            continue
        k = kind_of(cha)
        if k is None:
            continue
        s = stations.setdefault(code, {"code": code, "network": net, "operator": OPERATORS.get(net, net),
                                       "siteName": names.get(code, sta), "lat": float(f[4]), "lon": float(f[5]),
                                       "elev": round(float(f[6])), "depth": float(f[7] or 0), "since": f[15][:10], "_inst": {}})
        s["since"] = min(s["since"], f[15][:10])
        s["depth"] = max(s["depth"], float(f[7] or 0))
        inst = s["_inst"].setdefault(k, {"kind": k[0], "band": k[1], "channels": [], "rate": 0.0})
        if cha not in inst["channels"]:
            inst["channels"].append(cha)
        inst["rate"] = max(inst["rate"], float(f[14] or 0))

    for code in sorted(returned - excluded_codes - set(stations)):   # open channels, but none of them an instrument
        excluded[code] = "only state-of-health channels are open"; excluded_codes.add(code)

    for s in stations.values():
        insts = sorted(s.pop("_inst").values(), key=lambda i: (KINDS.index(i["kind"]), i["band"] or ""))
        for i in insts:
            i["channels"].sort()
        s["instruments"] = insts

    # co-located codes → one site, named after the longest-running code
    groups: list[list[dict]] = []
    for s in sorted(stations.values(), key=lambda s: (s["since"], s["code"])):
        g = next((g for g in groups if any(_dist_m(s, o) <= SITE_RADIUS_M for o in g)), None)
        (g.append(s) if g else groups.append([s]))
    b = E.OVERVIEW
    sites = []
    for g in groups:
        first = g[0]   # the longest-running code names the site and places it
        lat, lon = first["lat"], first["lon"]
        ident = next((s["code"] for s in g if s["code"] in majors), first["code"])   # people know the major code
        kinds = [k for k in KINDS if any(i["kind"] == k for s in g for i in s["instruments"])]
        codes = [s["code"] for s in g]
        major = next((majors[c] for c in codes if c in majors), None)
        sites.append({
            "id": ident, "name": clean_name(first["siteName"]), "codes": codes,
            "lat": lat, "lon": lon, "x": E.to_x(lon), "z": E.to_z(lat), "elev": first["elev"],
            "kinds": kinds, "since": first["since"], "onMap": b.west <= lon <= b.east and b.south <= lat <= b.north,
            "major": major, "stations": g,
        })
    sites.sort(key=lambda s: math.hypot(s["x"], s["z"]))
    return {
        "asOf": as_of, "kinds": KINDS, "sites": sites,
        "excluded": [{"code": c, "reason": r} for c, r in sorted(excluded.items())],
        "counts": {"returned": len(returned), "excluded": len(excluded_codes), "stations": len(stations), "sites": len(sites), "sitesOnMap": sum(s["onMap"] for s in sites),
                   "stationsOnMap": sum(len(s["stations"]) for s in sites if s["onMap"])},
        "source": "EarthScope FDSN station service; active channels as of " + as_of,
    }
