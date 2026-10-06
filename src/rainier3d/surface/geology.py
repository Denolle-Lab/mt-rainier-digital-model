"""Surface geology: fetch DNR GeMS 1:100k map units, crosswalk to model units, rasterize.

Pattern follows gwl-space-time-smooth/src/data/rasterize_geology.py: raw vectors cached as
GeoPackage, categorical raster as uint8 with no interpolation, and a reviewable crosswalk JSON.
"""

from __future__ import annotations

import json
import logging
import re

import geopandas as gpd
import numpy as np
import requests
import xarray as xr
from rasterio.features import rasterize

from rainier3d.config.domain import REPO, Domain
from rainier3d.io.store import provenance
from rainier3d.petro.table import units_config

log = logging.getLogger(__name__)

GEMS = "https://gis.dnr.wa.gov/site1/rest/services/Public_Geology/100K_Surface_Geology_WA_GeMS/FeatureServer"
MAP_UNITS, DMU = 11, 13
CROSSWALK = REPO / "configs" / "crosswalk_geology.json"


def _query(layer: int, params: dict, page: int = 1000) -> list[dict]:
    feats, off = [], 0
    while True:
        p = {"f": "geojson", "resultOffset": off, "resultRecordCount": page, **params}
        r = requests.get(f"{GEMS}/{layer}/query", params=p, timeout=180)
        r.raise_for_status()
        got = r.json().get("features", [])
        if not got:  # the server may cap a page below ``page``: stop only on an empty page
            return feats
        feats += got
        off += len(got)


def fetch_map_units(dom: Domain) -> gpd.GeoDataFrame:
    cache = dom.path("raw") / "geology" / "dnr_gems_100k_map_units.gpkg"
    if cache.exists():
        return gpd.read_file(cache)
    lon0, lat0, lon1, lat1 = dom.bbox_4326
    feats = _query(
        MAP_UNITS,
        {
            "where": "1=1",
            "geometry": f"{lon0},{lat0},{lon1},{lat1}",
            "geometryType": "esriGeometryEnvelope",
            "inSR": 4326,
            "outSR": 4326,
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "MAP_UNIT_100K,MAP_UNIT_100K_LABEL,MAP_UNIT_100K_ID_CONFIDENCE",
        },
    )
    gdf = gpd.GeoDataFrame.from_features(feats, crs="EPSG:4326").to_crs(dom.crs)
    cache.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(cache)
    log.info("cached %d map-unit polygons -> %s", len(gdf), cache)
    return gdf


def fetch_dmu(dom: Domain) -> list[dict]:
    """Description of Map Units (compiled quadrangle), cached once so reruns read the same text."""
    cache = dom.path("raw") / "geology" / "dnr_gems_100k_dmu.json"
    if cache.exists():
        return json.loads(cache.read_text())
    rows = _query(
        DMU,
        {
            "where": "DMU_100K_QUAD_NAME='Compiled'",
            "outFields": "DMU_100K_MAP_UNIT,DMU_100K_FULL_NAME,DMU_100K_AGE,DMU_100K_DESCRIPTION",
            "orderByFields": "DMU_100K_MAP_UNIT",
        },
        page=2000,
    )
    rows = sorted((f["properties"] for f in rows), key=lambda a: (a["DMU_100K_MAP_UNIT"] or "", str(a)))
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(rows, indent=0, sort_keys=True))
    log.info("cached %d DMU rows -> %s", len(rows), cache)
    return rows


def fetch_dmu_names(dom: Domain) -> dict[str, str]:
    out = {}
    for a in fetch_dmu(dom):
        out[a["DMU_100K_MAP_UNIT"]] = " | ".join(
            str(a[k]) for k in ("DMU_100K_AGE", "DMU_100K_FULL_NAME") if a.get(k)
        )
    return out


def build_crosswalk(symbols: list[str], names: dict[str, str] | None = None) -> dict[str, dict]:
    cfg = units_config()
    rules = [(re.compile(rx), int(uid)) for rx, uid in cfg["crosswalk_rules"]]
    uname = {int(k): v["name"] for k, v in cfg["units"].items()}
    cw = {}
    for s in sorted(set(symbols)):
        uid = next((u for rx, u in rules if rx.search(s)), None)
        cw[s] = {"unit_id": uid, "unit": uname.get(uid), "dmu": (names or {}).get(s, "")}
    return cw


def write_crosswalk(cw: dict) -> None:
    CROSSWALK.write_text(json.dumps(cw, indent=1, ensure_ascii=False) + "\n")


def load_crosswalk() -> dict:
    return json.loads(CROSSWALK.read_text())


def rasterize_units(dom: Domain, gdf: gpd.GeoDataFrame, cw: dict) -> xr.DataArray:
    unmapped = sorted({s for s in gdf["MAP_UNIT_100K"] if cw.get(s, {}).get("unit_id") is None})
    if unmapped:
        raise ValueError(f"map symbols without a model unit: {unmapped}")
    r = dom.surface_res_m
    x0, y0, x1, y1 = dom.bounds
    from affine import Affine

    tr = Affine(r, 0, x0, 0, -r, y1)
    shapes = ((g, cw[s]["unit_id"]) for g, s in zip(gdf.geometry, gdf["MAP_UNIT_100K"], strict=True))
    arr = rasterize(
        shapes, out_shape=(int((y1 - y0) / r), int((x1 - x0) / r)), transform=tr, fill=0, dtype="uint8"
    )[::-1]
    da = xr.DataArray(arr, coords={"y": dom.y, "x": dom.x}, dims=("y", "x"), name="surface_unit")
    if (da == 0).any():
        log.warning("%d surface cells without a mapped unit", int((da == 0).sum()))
    da.attrs = {
        "long_name": "model unit at the ground surface",
        "flag_meanings": json.dumps({int(k): v["name"] for k, v in units_config()["units"].items()}),
    }
    return provenance(da, ["dnr_gems_100k"], "lithology", r)


def rasterize_thickness(dom: Domain, gdf: gpd.GeoDataFrame, cw: dict, units_cfg: dict) -> xr.DataArray:
    """Thickness of the surface deposit (m) per cell: the map symbol's value in symbol_thickness_m of
    configs/units.yaml when its DMU states one, else the unit default (geometry.unconsolidated_thickness_m);
    0 under other units."""
    geo = units_cfg["geometry"]
    default = {int(k): float(v) for k, v in geo["unconsolidated_thickness_m"].items()}
    per_sym = {s: float(v["thickness_m"]) for s, v in (geo.get("symbol_thickness_m") or {}).items()}
    val = {s: per_sym.get(s, default.get(cw[s]["unit_id"], 0.0)) for s in set(gdf["MAP_UNIT_100K"])}
    r = dom.surface_res_m
    x0, y0, x1, y1 = dom.bounds
    from affine import Affine

    tr = Affine(r, 0, x0, 0, -r, y1)
    shapes = ((g, val[s]) for g, s in zip(gdf.geometry, gdf["MAP_UNIT_100K"], strict=True))
    arr = rasterize(
        shapes, out_shape=(int((y1 - y0) / r), int((x1 - x0) / r)), transform=tr, fill=0, dtype="float32"
    )[::-1]
    da = xr.DataArray(arr, coords={"y": dom.y, "x": dom.x}, dims=("y", "x"), name="unconsolidated_thickness")
    da.attrs = {
        "units": "m",
        "long_name": "thickness of the surface deposit: DMU value of the map symbol, else the unit default",
    }
    keys = ["dnr_gems_100k", "m1_placeholder"]
    return provenance(da, keys, "unconsolidated_thickness", r)


def fill_nearest(unit: np.ndarray, keep: np.ndarray) -> np.ndarray:
    """Replace cells where ``keep`` is False by the nearest cell where it is True."""
    from scipy.ndimage import distance_transform_edt

    _, (iy, ix) = distance_transform_edt(~keep, return_indices=True)
    return unit[iy, ix]
