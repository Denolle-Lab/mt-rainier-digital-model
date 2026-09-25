"""Mass movements and faults: fetch the open inventories, clip them to the domain, and build the catalogue.

Sources (configs/sources.yaml keys), each cached under data/raw/<source>/:
  wgs_landslide_inventory  DNR landslide inventory: lidar-protocol deposits (layer 21), recent landslides
                           (layer 1, points), compilation of older mapping (layer 131)
  allstadt_2017_esec       seismically recorded mass movements, western US 1977-2017 (Events.csv)
  schilling_2008           USGS lahar hazard zones of Hoblitt et al. (1998), shapefiles
  dnr_gems_100k            1:100k faults (layer 7); lahar deposits are the Qvl map units already cached by S1
  dnr_quaternary_faults    DNR Quaternary active faults

The catalogue has two parts. Flows (lahar deposits and debris flows) keep their polygons. Every other event
is a point: the seismic location for the seismic catalogue, the mapped point for recent landslides, and the
crown (highest boundary point on a 1 m 3DEP window) for landslide polygons, where the failure started.
Every service call is listed in docs/mass_movements.md.
"""

from __future__ import annotations

import logging

import geopandas as gpd
import numpy as np
import pandas as pd
import requests
from shapely.geometry import Point, box
from shapely.ops import polygonize, unary_union

from rainier3d.config.domain import Domain

log = logging.getLogger(__name__)

WGS_LS = "https://gis.dnr.wa.gov/site3/rest/services/Geology/Landslide_Inventory_Database/MapServer"
LS_RECENT, LS_DEPOSIT, LS_COMPILATION = 1, 21, 131
GEMS = "https://gis.dnr.wa.gov/site1/rest/services/Public_Geology/100K_Surface_Geology_WA_GeMS/FeatureServer"
GEMS_FAULTS = 7
QFAULTS = "https://gis.dnr.wa.gov/site1/rest/services/Public_Geology/Earthquakes_and_Faults/MapServer/12"
ALLSTADT = (
    "https://www.sciencebase.gov/catalog/file/get/597913dde4b0ec1a488a4990"
    "?f=__disk__88%2Fe4%2F4b%2F88e44b89ceede4a2a50578aeb487eb375e6b1b1b"
)
LAHAR_ZONES = "https://pubs.usgs.gov/of/2007/1220/data/rainier_98shapefiles.zip"
LAHAR_ZONES_CRS = "EPSG:26710"  # UTM 10N, NAD27 (metadata.txt of the archive)

# GeMS labels of the lahar deposits (DNR 1:100k description of map units)
LAHAR_UNITS = {"Qvl(o)": "Osceola Mudflow", "Qvl(e)": "Electron Mudflow", "Qvl": "lahar deposits"}
# inventory movement types that are flows; everything else becomes a point
FLOW_TYPES = {"Flow", "Debris flow", "Hyperconcentrated flows"}

# the classes of the viewer and the report: (key, label, colour)
FLOW_CLASSES = [
    (1, "Osceola Mudflow", "#b5651d"),
    (2, "Electron Mudflow", "#e0913a"),
    (3, "Other lahar deposits", "#d9b26f"),
    (4, "Debris flows (mapped)", "#7a4fa3"),
]
EVENT_CLASSES = [
    ("rock_avalanche", "Rock fall, rock and ice avalanche", "#e8554e"),
    ("snow_ice_avalanche", "Snow or ice avalanche", "#7fd3f5"),
    ("debris_flow", "Debris flow, outburst flood", "#b384e0"),
    ("slide", "Slide, debris slide", "#f2c14e"),
    ("complex", "Complex or unknown type", "#a8a39a"),
]


def _query(url: str, params: dict, page: int = 1000) -> list[dict]:
    """GeoJSON features of an ArcGIS REST query, paged until the server returns an empty page."""
    feats, off = [], 0
    while True:
        p = {"f": "geojson", "resultOffset": off, "resultRecordCount": page, **params}
        r = requests.get(f"{url}/query", params=p, timeout=180)
        r.raise_for_status()
        got = r.json().get("features", [])
        if not got:
            return feats
        feats += got
        off += len(got)


def _box_params(dom: Domain) -> dict:
    lon0, lat0, lon1, lat1 = dom.bbox_4326
    return {
        "where": "1=1",
        "geometry": f"{lon0},{lat0},{lon1},{lat1}",
        "geometryType": "esriGeometryEnvelope",
        "inSR": 4326,
        "outSR": 4326,
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "*",
    }


def _cached_layer(dom: Domain, url: str, source: str, name: str) -> gpd.GeoDataFrame:
    cache = dom.path("raw") / source / f"{name}.gpkg"
    if cache.exists():
        return gpd.read_file(cache)
    feats = _query(url, _box_params(dom))
    gdf = gpd.GeoDataFrame.from_features(feats, crs="EPSG:4326").to_crs(dom.crs)
    cache.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(cache)
    log.info("cached %d features -> %s", len(gdf), cache)
    return gdf


def fetch_landslides(dom: Domain) -> dict[str, gpd.GeoDataFrame]:
    src = "wgs_landslides"
    return {
        "recent": _cached_layer(dom, f"{WGS_LS}/{LS_RECENT}", src, "recent_landslides"),
        "deposits": _cached_layer(dom, f"{WGS_LS}/{LS_DEPOSIT}", src, "landslide_deposits"),
        "compilation": _cached_layer(dom, f"{WGS_LS}/{LS_COMPILATION}", src, "landslide_compilation"),
    }


def fetch_faults(dom: Domain) -> dict[str, gpd.GeoDataFrame]:
    return {
        "gems": _cached_layer(dom, f"{GEMS}/{GEMS_FAULTS}", "geology", "dnr_gems_100k_faults"),
        "quaternary": _cached_layer(dom, QFAULTS, "geology", "dnr_quaternary_faults"),
    }


def _download(url: str, path) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    r = requests.get(url, timeout=300)
    r.raise_for_status()
    path.write_bytes(r.content)
    log.info("downloaded %s (%.1f MB)", path, len(r.content) / 1e6)


def fetch_seismic_events(dom: Domain) -> pd.DataFrame:
    """Allstadt et al. (2017) events inside the domain. The second CSV row gives the units."""
    path = dom.path("raw") / "allstadt2017" / "Events.csv"
    _download(ALLSTADT, path)
    df = pd.read_csv(path, encoding="latin-1", skiprows=[1])
    lon0, lat0, lon1, lat1 = dom.bbox_4326
    inside = df.Longitude.between(lon0, lon1) & df.Latitude.between(lat0, lat1)
    return df[inside].reset_index(drop=True)


def fetch_lahar_zones(dom: Domain) -> gpd.GeoDataFrame:
    """The case 1-3 lahar inundation zones, post-lahar sedimentation and pyroclastic-flow zones (1998).

    The shapefiles have no .prj; metadata.txt in the archive gives UTM zone 10, NAD27, metres. The zones are
    stored as outlines (LineStrings) and are polygonised here.
    """
    path = dom.path("raw") / "usgs_rainier_hazards" / "rainier_98shapefiles.zip"
    _download(LAHAR_ZONES, path)
    parts = []
    for zone in ("case1", "case2", "case3", "postlahar", "pyroclastic"):
        g = gpd.read_file(f"zip://{path}!{zone}.shp")
        polys = list(polygonize(unary_union(g.geometry.values)))
        z = gpd.GeoDataFrame({"zone": zone}, index=range(len(polys)), geometry=polys, crs=LAHAR_ZONES_CRS)
        parts.append(z.to_crs(dom.crs))
    return gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), crs=dom.crs)


def lahar_deposits(map_units: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """The Qvl map units of the 1:100k geology, dissolved by label."""
    m = map_units[map_units.MAP_UNIT_100K_LABEL.isin(LAHAR_UNITS)]
    g = m.dissolve("MAP_UNIT_100K_LABEL").reset_index()
    g["name"] = g.MAP_UNIT_100K_LABEL.map(LAHAR_UNITS)
    g["cls"] = g.MAP_UNIT_100K_LABEL.map({"Qvl(o)": 1, "Qvl(e)": 2, "Qvl": 3})
    g["source"] = "dnr_gems_100k"
    return g[["cls", "name", "source", "geometry"]]


def _s(v) -> str:
    return "" if v is None or (isinstance(v, float) and np.isnan(v)) else str(v)


def _event_class(text) -> str:
    t = _s(text).lower()
    if "snow" in t or ("ice avalanche" in t and "rock" not in t):
        return "snow_ice_avalanche"
    if "flow" in t or "outburst" in t:
        return "debris_flow"
    if "rock" in t or "fall" in t or "topple" in t:
        return "rock_avalanche"
    if "slide" in t:
        return "slide"
    if "avalanche" in t:
        return "rock_avalanche"
    return "complex"


def fetch_crown_dems(dom: Domain, polys: gpd.GeoSeries, keys: list[str], workers: int = 4) -> list:
    """A 1 m elevation window around each landslide polygon (20 m margin), cached as one GeoTIFF per polygon.

    Service: USGS 3DEP dynamic elevation through py3dep.get_dem(bbox, resolution=1, crs=4326), which resamples
    the best 3DEP source at each point (1 m lidar where it exists, else 3 m or 10 m) and returns EPSG:5070.
    Cache: data/raw/dem_3dep_1m/landslides/<key>.tif. A window that fails is logged and left out (None).
    """
    from concurrent.futures import ThreadPoolExecutor

    import py3dep

    root = dom.path("raw") / "dem_3dep_1m" / "landslides"
    root.mkdir(parents=True, exist_ok=True)
    boxes = polys.buffer(20).to_crs(4326).bounds.to_numpy()

    def one(i):
        path = root / f"{keys[i]}.tif"
        if not path.exists():
            try:
                dem = py3dep.get_dem(tuple(boxes[i]), resolution=1, crs=4326)
                dem.rio.to_raster(path, compress="deflate", predictor=3)
            except Exception as e:  # noqa: BLE001 - one failed window must not stop the catalogue
                log.warning("3DEP 1 m window %s failed: %s", keys[i], e)
                return None
        return path

    with ThreadPoolExecutor(workers) as ex:
        out = list(ex.map(one, range(len(polys))))
    log.info(
        "3DEP 1 m windows: %d of %d polygons (cache %s)", sum(p is not None for p in out), len(out), root
    )
    return out


def fetch_3dep_sources(dom: Domain) -> gpd.GeoDataFrame:
    """Footprints of the 3DEP source DEMs (dem_res 1m, 3m, 10m, ...) over the box: py3dep.query_3dep_sources.
    Used only to record which resolution lies under each crown."""
    path = dom.path("raw") / "dem_3dep_1m" / "3dep_sources.gpkg"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        import py3dep

        src = py3dep.query_3dep_sources(dom.bbox_4326)[["dem_res", "geometry"]]
        src.to_file(path)
    return gpd.read_file(path).to_crs(dom.crs)


def crown_points(polys: gpd.GeoSeries, dems: list, step: float = 2.0) -> gpd.GeoSeries:
    """The highest point of each polygon's boundary, sampled every ``step`` m on that polygon's DEM window
    (or on one DEM for all, if ``dems`` is a single path): the head of the landslide."""
    import rasterio

    if not isinstance(dems, list):
        dems = [dems] * len(polys)
    out = []
    for geom, dem in zip(polys, dems, strict=True):
        ring = geom.boundary.segmentize(step)
        pts = np.array([p for line in getattr(ring, "geoms", [ring]) for p in line.coords])[:, :2]
        if dem is None:
            out.append(None)
            continue
        with rasterio.open(dem) as r:
            xy = gpd.GeoSeries(gpd.points_from_xy(pts[:, 0], pts[:, 1]), crs=polys.crs).to_crs(r.crs)
            z = np.array([v[0] for v in r.sample(zip(xy.x, xy.y, strict=True))], dtype=float)
            if r.nodata is not None:
                z[z == r.nodata] = np.nan
        z[~np.isfinite(z)] = -np.inf
        out.append(Point(pts[int(np.argmax(z))]) if np.isfinite(z).any() and z.max() > -np.inf else None)
    return gpd.GeoSeries(out, crs=polys.crs)


def _crowns(dom: Domain, polys: gpd.GeoSeries, keys: list[str], dem30, src: gpd.GeoDataFrame):
    """Crown points on the 1 m windows, falling back to the 30 m DEM; and the 3DEP resolution under each."""
    fine = crown_points(polys, fetch_crown_dems(dom, polys, keys))
    coarse = polys[fine.isna().to_numpy()]
    if len(coarse):
        fine[fine.isna()] = crown_points(coarse, dem30).to_numpy()
    res = []
    for p, used_1m in zip(fine, ~polys.index.isin(coarse.index), strict=True):
        hit = src[src.contains(p)].dem_res
        best = min(hit, key=lambda r: float(r.rstrip("m"))) if len(hit) else "unknown"
        res.append(f"3DEP {best}" if used_1m else "3DEP 30 m (window failed)")
    return fine, res


def build_catalogue(
    dom: Domain, map_units: gpd.GeoDataFrame, dem_path
) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    """(flows, events), both in the domain CRS and clipped to the domain box. ``dem_path`` is the 30 m DEM,
    the fallback for crowns whose 1 m window could not be fetched."""
    ls = fetch_landslides(dom)
    dep, comp = ls["deposits"], ls["compilation"]
    # the compilation repeats older mapping of some protocol deposits: keep a compilation polygon only if its
    # representative point is outside every protocol deposit
    dup = gpd.sjoin(
        gpd.GeoDataFrame(geometry=comp.representative_point(), crs=comp.crs),
        dep[["geometry"]],
        predicate="within",
    ).index.unique()
    comp = comp.drop(index=dup)
    log.info("landslide compilation: %d polygons dropped as repeats of protocol deposits", len(dup))

    dep_flow = dep.MOVEMENT.isin(FLOW_TYPES)
    comp_flow = comp.LANDSLIDE_TYPE.isin(FLOW_TYPES)
    debris = pd.concat(
        [
            gpd.GeoDataFrame({"name": "debris flow (lidar protocol)", "geometry": dep[dep_flow].geometry}),
            gpd.GeoDataFrame({"name": "debris flow (compilation)", "geometry": comp[comp_flow].geometry}),
        ],
        ignore_index=True,
    )
    debris["cls"], debris["source"] = 4, "wgs_landslide_inventory"
    flows = pd.concat([lahar_deposits(map_units), debris.set_crs(dom.crs)], ignore_index=True)
    flows = gpd.GeoDataFrame(flows, crs=dom.crs)

    rows = []
    inside = box(*dom.bounds)
    pd_dep = dep[~dep_flow & dep.intersects(inside)]
    pd_comp = comp[~comp_flow & comp.intersects(inside)]
    src = fetch_3dep_sources(dom)
    crown_dep, res_dep = _crowns(
        dom, pd_dep.geometry, [f"deposit_{k}" for k in pd_dep.LANDSLIDE_ID], dem_path, src
    )
    crown_comp, res_comp = _crowns(
        dom, pd_comp.geometry, [f"compilation_{k}" for k in pd_comp.LANDSLIDE_ID], dem_path, src
    )
    for geom, dres, r in zip(crown_dep, res_dep, pd_dep.itertuples(), strict=True):
        cls = "complex" if r.MOVEMENT == "Complex" else _event_class(r.MOVEMENT)
        rows.append(
            {
                "geometry": geom,
                "cls": cls,
                "name": _s(r.LS_NAME),
                "date": "",
                "age": _s(r.RELATIVE_AGE),
                "type": f"{_s(r.MATERIAL)}, {_s(r.MOVEMENT)}".lower(),
                "depth_m": _ft(r.FAIL_DEPTH_FT),
                "volume_m3": _ft3(r.VOLUME_FT3),
                "confidence": _s(r.CONFIDENCE),
                "located": "crown",
                "crown_dem": dres,
                "source": "wgs_landslide_inventory",
            }
        )
    for geom, dres, r in zip(crown_comp, res_comp, pd_comp.itertuples(), strict=True):
        date = _date(r.LANDSLIDE_DATE)
        rows.append(
            {
                "geometry": geom,
                "cls": _event_class(r.LANDSLIDE_TYPE),
                "name": _s(r.LANDSLIDE_NAME),
                "date": date,
                "age": "",
                "type": (_s(r.LANDSLIDE_TYPE) or "unknown").lower(),
                "depth_m": None,
                "volume_m3": None,
                "confidence": _s(r.DATA_CONFIDENCE),
                "located": "crown",
                "crown_dem": dres,
                "source": "wgs_landslide_inventory",
            }
        )
    for r in ls["recent"].itertuples():
        rows.append(
            {
                "geometry": r.geometry,
                "cls": _event_class(r.MOVEMENT),
                "name": "",
                "date": _s(r.YEAR_OBSV),
                "age": "historic",
                "type": f"{_s(r.MATERIAL)}, {_s(r.MOVEMENT)}".lower(),
                "depth_m": None,
                "volume_m3": None,
                "confidence": _s(r.CONFIDENCE),
                "located": "mapped point",
                "crown_dem": "",
                "source": "wgs_landslide_inventory",
            }
        )
    seis = fetch_seismic_events(dom)
    xy = gpd.points_from_xy(seis.Longitude, seis.Latitude, crs="EPSG:4326").to_crs(dom.crs)
    for geom, r in zip(xy, seis.itertuples(), strict=True):
        rows.append(
            {
                "geometry": geom,
                "cls": _event_class(r.Type),
                "name": r.Name.strip(),
                "date": r.StartTime,
                "age": "historic",
                "type": r.Type,
                "depth_m": None,
                "volume_m3": None if pd.isna(r.Volume) else float(r.Volume),
                "confidence": f"location ±{r.LocUncert_km:g} km",
                "located": "seismic",
                "crown_dem": "",
                "source": "allstadt_2017_esec",
            }
        )
    events = gpd.GeoDataFrame(rows, crs=dom.crs)
    x0, y0, x1, y1 = dom.bounds
    flows = flows.clip((x0, y0, x1, y1))
    events = events.cx[x0:x1, y0:y1].reset_index(drop=True)
    return flows[~flows.is_empty].reset_index(drop=True), events


def _date(v) -> str:
    """Service dates arrive as epoch milliseconds, or as datetimes once cached in a GeoPackage."""
    if v is None or pd.isna(v):
        return ""
    return (pd.to_datetime(v, unit="ms") if isinstance(v, (int, float)) else pd.Timestamp(v)).strftime(
        "%Y-%m-%d"
    )


def _ft(v) -> float | None:
    return None if v is None or pd.isna(v) or v <= 0 else round(float(v) * 0.3048, 1)


def _ft3(v) -> float | None:
    return None if v is None or pd.isna(v) or v <= 0 else round(float(v) * 0.3048**3)
