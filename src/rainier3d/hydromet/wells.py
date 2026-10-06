"""Wells and boreholes in the model box (configs/wells.yaml): Washington Department of Ecology well reports,
USGS groundwater levels, and the Washington Geological Survey subsurface database.

Each fetcher queries its service once, with the as_of date as the upper bound, sorts the records and caches
them under data/raw/wells/; reruns read the cache. well_table() turns the three caches into one table of depth
to water (and, from the boreholes, depth to bedrock) in metres below the ground, and compare() samples the
gridded layers of /surface at each well."""

from __future__ import annotations

import logging
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import xarray as xr
import yaml

from rainier3d.config.domain import REPO, Domain

log = logging.getLogger(__name__)

CFG = REPO / "configs" / "wells.yaml"
FT = 0.3048
UA = {
    "User-Agent": "rainier3d/1.0 (+https://github.com/Denolle-Lab/mt-rainier-digital-model)"
}  # Ecology: 403


def config() -> dict:
    return yaml.safe_load(CFG.read_text())


def _raw(dom: Domain) -> Path:
    p = dom.path("raw") / "wells"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _in_box(dom: Domain, lon, lat) -> np.ndarray:
    w, s, e, n = dom.bbox_4326
    return (lon >= w) & (lon <= e) & (lat >= s) & (lat <= n)


# ---------------------------------------------------------------- Ecology well reports
def fetch_ecology(dom: Domain, cfg: dict) -> Path:
    cache = _raw(dom) / "ecology_well_reports.csv"
    if cache.exists():
        return cache
    c = cfg["ecology"]
    w, s, e, n = dom.bbox_4326
    where = f"WorkCompletionDate IS NULL OR WorkCompletionDate <= DATE '{cfg['as_of']}'"
    # The object ids are listed first and fetched in fixed chunks, so no page boundary can move between
    # requests; locations come from the geometry, because the lat/lon fields are empty for most reports.
    q = {
        "where": where,
        "geometry": f"{w},{s},{e},{n}",
        "geometryType": "esriGeometryEnvelope",
        "inSR": 4326,
        "spatialRel": "esriSpatialRelIntersects",
        "returnIdsOnly": "true",
        "f": "json",
    }
    r = requests.get(c["url"], params=q, headers=UA, timeout=180)
    r.raise_for_status()
    ids = sorted(r.json()["objectIds"])
    rows = []
    for i in range(0, len(ids), c["page"]):
        p = {
            "objectIds": ",".join(map(str, ids[i : i + c["page"]])),
            "outFields": ",".join(c["fields"]),
            "returnGeometry": "true",
            "outSR": 4326,
            "f": "json",
        }
        r = requests.post(c["url"], data=p, headers=UA, timeout=180)
        r.raise_for_status()
        for f in r.json()["features"]:
            g = f.get("geometry") or {}
            rows.append({**f["attributes"], "lon": g.get("x"), "lat": g.get("y")})
    df = pd.DataFrame(rows, columns=[*c["fields"], "lon", "lat"]).sort_values("OBJECTID")
    if len(df) != len(ids):
        raise RuntimeError(f"Ecology returned {len(df)} records for {len(ids)} ids")
    df["WorkCompletionDate"] = pd.to_datetime(df["WorkCompletionDate"], unit="ms").dt.strftime("%Y-%m-%d")
    df.to_csv(cache, index=False)
    log.info("cached %d Ecology well reports -> %s", len(df), cache)
    return cache


# ---------------------------------------------------------------- USGS groundwater levels
def _ogc_pages(url: str, params: dict) -> list[dict]:
    feats, nxt = [], (url, params)
    while nxt:
        r = requests.get(nxt[0], params=nxt[1], headers=UA, timeout=300)
        r.raise_for_status()
        d = r.json()
        feats += d.get("features", [])
        link = next((lk["href"] for lk in d.get("links", []) if lk.get("rel") == "next"), None)
        nxt = (link, None) if link and d.get("features") else None
    return feats


def fetch_nwis(dom: Domain, cfg: dict) -> tuple[Path, Path]:
    raw = _raw(dom)
    sites_csv, levels_csv = raw / "nwis_gw_sites.csv", raw / "nwis_gw_levels.csv"
    if sites_csv.exists() and levels_csv.exists():
        return sites_csv, levels_csv
    c = cfg["nwis"]
    bbox = ",".join(str(v) for v in dom.bbox_4326)
    lv = _ogc_pages(
        f"{c['api']}/field-measurements/items",
        {
            "f": "json",
            "bbox": bbox,
            "parameter_code": c["parameter_code"],
            "datetime": f"../{cfg['as_of']}T23:59:59Z",
            "limit": c["page"],
        },
    )
    keep = ["monitoring_location_id", "time", "value", "unit_of_measure", "qualifier", "approval_status"]
    levels = pd.DataFrame([{k: f["properties"].get(k) for k in keep} for f in lv])
    levels["qualifier"] = levels["qualifier"].map(lambda q: ";".join(q) if isinstance(q, list) else (q or ""))
    levels = levels.sort_values(["monitoring_location_id", "time", "value"]).reset_index(drop=True)
    st = _ogc_pages(
        f"{c['api']}/monitoring-locations/items",
        {"f": "json", "bbox": bbox, "site_type_code": "GW", "limit": c["page"]},
    )
    sites = pd.DataFrame(
        [
            {
                "monitoring_location_id": f["properties"]["id"],
                "lon": f["geometry"]["coordinates"][0],
                "lat": f["geometry"]["coordinates"][1],
                "well_depth_ft": f["properties"].get("well_constructed_depth"),
                "aquifer_code": f["properties"].get("aquifer_code"),
            }
            for f in st
            if f.get("geometry")
        ]
    ).sort_values("monitoring_location_id")
    sites.to_csv(sites_csv, index=False)
    levels.to_csv(levels_csv, index=False)
    log.info("cached %d NWIS groundwater sites, %d water levels", len(sites), len(levels))
    return sites_csv, levels_csv


# ---------------------------------------------------------------- WGS subsurface database
def fetch_wgs(dom: Domain, cfg: dict) -> Path:
    cache = _raw(dom) / "ger_portal_subsurface_database.zip"
    if not cache.exists():
        with requests.get(cfg["wgs"]["url"], headers=UA, stream=True, timeout=600) as r:
            r.raise_for_status()
            cache.write_bytes(r.content)
        log.info("cached the WGS subsurface database -> %s", cache)
    return cache


def wgs_tables(dom: Domain, zpath: Path, cfg: dict) -> dict[str, pd.DataFrame]:
    """Boreholes in the box with their depth to water and depth to bedrock (layers listed in the config)."""
    import pyogrio

    with zipfile.ZipFile(zpath) as z:
        gdb = sorted({n.split("/")[0] for n in z.namelist() if ".gdb" in n.split("/")[0]})[0]
    src = f"/vsizip/{zpath}/{gdb}"
    points = cfg["wgs"]["point_layers"]  # geotechnical boreholes and water wells (the latter carry an ECYID)
    bh = pd.concat(
        [pyogrio.read_dataframe(src, layer=k, read_geometry=False) for k in points], ignore_index=True
    )
    bh = bh[_in_box(dom, bh.LONGITUDE.astype(float), bh.LATITUDE.astype(float))]
    ids = set(bh.BOREHOLE_ID)
    out = {"borehole_information": bh.sort_values("BOREHOLE_ID")}
    for name in cfg["wgs"]["layers"]:
        t = pyogrio.read_dataframe(src, layer=name, read_geometry=False)
        out[name] = t[t.BOREHOLE_ID.isin(ids)].sort_values(list(t.columns[:2]))
    return out


# ---------------------------------------------------------------- one table
def well_table(dom: Domain, cfg: dict, eco: Path, nwis: tuple[Path, Path], wgs: dict) -> pd.DataFrame:
    """One row per well or borehole: source, id, lon, lat, depth to water (m), well depth (m), number of
    water-level measurements, depth to bedrock (m, boreholes only)."""
    qmax = cfg["qc"]["max_depth_to_water_m"]
    e = pd.read_csv(eco, dtype={"StaticWaterLvl": str, "CompletedDepth": str})
    e = e[_in_box(dom, e.lon, e.lat)]
    dtw = pd.to_numeric(e.StaticWaterLvl, errors="coerce") * FT
    depth = pd.to_numeric(e.CompletedDepth, errors="coerce") * FT
    eco_t = pd.DataFrame(
        {
            "source": "ecology",
            "site_id": e.ID.astype(str),
            "lon": e.lon,
            "lat": e.lat,
            "depth_to_water_m": dtw,
            "well_depth_m": depth,
            "n_levels": dtw.notna().astype(int),
            "depth_to_bedrock_m": np.nan,
            "date": e.WorkCompletionDate,
        }
    )
    sites, levels = (pd.read_csv(p) for p in nwis)
    lv = levels[levels.unit_of_measure == "ft"].copy()
    lv["v"] = pd.to_numeric(lv.value, errors="coerce") * FT
    g = lv.groupby("monitoring_location_id")
    agg = pd.DataFrame(
        {"depth_to_water_m": g.v.median(), "n_levels": g.v.count(), "date": g.time.max().str[:10]}
    )
    nw = sites.merge(agg, left_on="monitoring_location_id", right_index=True, how="inner")
    nw = nw[_in_box(dom, nw.lon, nw.lat)]
    nwis_t = pd.DataFrame(
        {
            "source": "nwis",
            "site_id": nw.monitoring_location_id,
            "lon": nw.lon,
            "lat": nw.lat,
            "depth_to_water_m": nw.depth_to_water_m,
            "well_depth_m": nw.well_depth_ft * FT,
            "n_levels": nw.n_levels,
            "depth_to_bedrock_m": np.nan,
            "date": nw.date,
        }
    )
    bh = wgs["borehole_information"]
    hyd = wgs["hydrologic"].assign(v=lambda t: pd.to_numeric(t.DEPTH_TO_WATER_FT, errors="coerce") * FT)
    bed = wgs["bedrock"].assign(b=lambda t: pd.to_numeric(t.DEPTH_TO_BEDROCK_FT, errors="coerce") * FT)
    w = bh.set_index("BOREHOLE_ID")
    ecy = w.ECYID.astype("string").str.strip().str.removesuffix(".0")  # stored as float text
    wgs_t = pd.DataFrame(
        {
            "source": "wgs",
            "ecology_id": ecy.values,
            "site_id": w.index.astype(str),
            "lon": w.LONGITUDE.astype(float).values,
            "lat": w.LATITUDE.astype(float).values,
            "depth_to_water_m": hyd.groupby("BOREHOLE_ID").v.median().reindex(w.index).values,
            "well_depth_m": pd.to_numeric(w.BOREHOLE_DEPTH_FT, errors="coerce").values * FT,
            "n_levels": hyd.groupby("BOREHOLE_ID").v.count().reindex(w.index).fillna(0).astype(int).values,
            "depth_to_bedrock_m": bed.groupby("BOREHOLE_ID").b.min().reindex(w.index).values,
            "date": pd.to_datetime(w.BOREHOLE_DATE, errors="coerce").dt.strftime("%Y-%m-%d").values,
        }
    )
    t = pd.concat([eco_t, nwis_t, wgs_t], ignore_index=True)
    # a WGS water well is an Ecology report too: its water level is counted once, under Ecology
    t["duplicate_of_ecology"] = (t.source == "wgs") & t.ecology_id.isin(set(eco_t.site_id))
    bad = (t.depth_to_water_m < 0) | (t.depth_to_water_m > qmax) | (t.depth_to_water_m > t.well_depth_m)
    t["qc_water"] = np.where(t.depth_to_water_m.isna(), "none", np.where(bad, "rejected", "ok"))
    t.loc[t.duplicate_of_ecology & (t.qc_water == "ok"), "qc_water"] = "duplicate"
    from pyproj import Transformer

    tf = Transformer.from_crs("EPSG:4326", dom.crs, always_xy=True)
    t["x"], t["y"] = tf.transform(t.lon.values, t.lat.values)
    return t.sort_values(["source", "site_id"]).reset_index(drop=True)


def compare(t: pd.DataFrame, surface, cfg: dict) -> dict:
    """Sample /surface at each well (nearest cell) and summarise observed minus gridded depths."""
    s = surface
    px, py = xr.DataArray(t.x.values, dims="w"), xr.DataArray(t.y.values, dims="w")

    def at(var):  # the cell nearest each well
        return s[var].sel(x=px, y=py, method="nearest").values if var in s else np.full(len(t), np.nan)

    elev = at("elevation")
    split = cfg["comparison"]["elevation_split_m"]
    out = {"as_of": cfg["as_of"], "elevation_split_m": split, "counts": {}, "water_table": {}, "bedrock": {}}
    for src, g in t.groupby("source"):
        out["counts"][src] = {
            "wells": int(len(g)),
            "with_water_level": int((g.qc_water == "ok").sum()),
            "rejected_water_level": int((g.qc_water == "rejected").sum()),
            "upland_with_water_level": int(((g.qc_water == "ok") & (elev[g.index] >= split)).sum()),
            "with_bedrock_pick": int(g.depth_to_bedrock_m.notna().sum()),
        }
    ok = (t.qc_water == "ok").values
    obs = t.depth_to_water_m.values
    for var in ("water_table_depth", "water_table_depth_fan"):
        grid = at(var)
        for band, m in (("all", ok), ("lowland", ok & (elev < split)), ("upland", ok & (elev >= split))):
            m = m & np.isfinite(grid)
            if m.sum() < 5:
                continue
            r = grid[m] - obs[m]
            out["water_table"][f"{var}|{band}"] = {
                "n": int(m.sum()),
                "obs_median_m": round(float(np.median(obs[m])), 1),
                "grid_median_m": round(float(np.median(grid[m])), 1),
                "median_grid_minus_obs_m": round(float(np.median(r)), 1),
                "median_abs_diff_m": round(float(np.median(np.abs(r))), 1),
                "spearman_r": round(float(pd.Series(grid[m]).corr(pd.Series(obs[m]), method="spearman")), 2),
            }
    bd = t.depth_to_bedrock_m.values
    mb = np.isfinite(bd)
    for var in ("soil_thickness", "depth_to_bedrock"):
        grid = at(var)
        m = mb & np.isfinite(grid)
        if m.sum():
            out["bedrock"][var] = {
                "n": int(m.sum()),
                "obs_median_m": round(float(np.median(bd[m])), 1),
                "grid_median_m": round(float(np.median(grid[m])), 1),
                "median_grid_minus_obs_m": round(float(np.median(grid[m] - bd[m])), 1),
            }
    return out
