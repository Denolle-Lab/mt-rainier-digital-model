# Mass movements and faults (S24)

`pixi run s24` (`scripts/24_mass_movements.py`, code in `src/rainier3d/surface/mass_movements.py`) builds a
catalogue of landslides, lahars, debris flows and seismically recorded mass movements in the model box, the
fault traces, and the viewer layers. The paper section is "Mass movements" in `docs/paper/rainier3d_paper.md`.

## Service calls

Every download is a plain HTTP request (`requests`) or a `py3dep` call. No ArcGIS Python API, account or token is
used. Each response is cached under `data/raw/<folder>/`; a rerun reads the cache and makes no call. The cached
files and their SHA-256 are listed in `docs/data_manifest.csv` (`pixi run manifest -- --check`).

| Data | Endpoint | Call | Paging, limits | Cache | Registry key |
|---|---|---|---|---|---|
| Landslide deposits, lidar protocol | `https://gis.dnr.wa.gov/site3/rest/services/Geology/Landslide_Inventory_Database/MapServer/21/query` | `GET`, `f=geojson`, `where=1=1`, `geometry=<lon0,lat0,lon1,lat1>`, `geometryType=esriGeometryEnvelope`, `inSR=4326`, `outSR=4326`, `spatialRel=esriSpatialRelIntersects`, `outFields=*` | `resultOffset` / `resultRecordCount=1000`, repeated until an empty page (the server caps a page at 2000) | `wgs_landslides/landslide_deposits.gpkg` | `wgs_landslide_inventory` |
| Recent landslides (points) | same service, layer `1` | same | same | `wgs_landslides/recent_landslides.gpkg` | `wgs_landslide_inventory` |
| Landslide compilation | same service, layer `131` | same | same | `wgs_landslides/landslide_compilation.gpkg` | `wgs_landslide_inventory` |
| 1:100,000 faults | `https://gis.dnr.wa.gov/site1/rest/services/Public_Geology/100K_Surface_Geology_WA_GeMS/FeatureServer/7/query` | same | same | `geology/dnr_gems_100k_faults.gpkg` | `dnr_gems_100k` |
| Quaternary faults | `https://gis.dnr.wa.gov/site1/rest/services/Public_Geology/Earthquakes_and_Faults/MapServer/12/query` | same | same | `geology/dnr_quaternary_faults.gpkg` | `dnr_quaternary_faults` |
| Lahar deposits (Qvl units) | the S1 query of the 1:100,000 map units (layer 11) | read from the S1 cache | none | `geology/dnr_gems_100k_map_units.gpkg` | `dnr_gems_100k` |
| Seismogenic mass movements | `https://www.sciencebase.gov/catalog/file/get/597913dde4b0ec1a488a4990?f=__disk__88%2Fe4%2F…` (`Events.csv`) | `GET` of the file; the second CSV row holds units and is skipped | one file, 34 kB | `allstadt2017/Events.csv` | `allstadt_2017_esec` |
| Lahar hazard zones, 1998 | `https://pubs.usgs.gov/of/2007/1220/data/rainier_98shapefiles.zip` | `GET` of the zip; shapefiles read inside it, CRS set to EPSG:26710 (no `.prj`; UTM 10N NAD27 per `metadata.txt`); outlines polygonised | one file, 0.15 MB | `usgs_rainier_hazards/rainier_98shapefiles.zip` | `schilling_2008` |
| 1 m elevation windows at landslides | USGS 3DEP dynamic elevation service | `py3dep.get_dem(bbox, resolution=1, crs=4326)` per landslide polygon, bbox = polygon + 20 m; the service resamples the best 3DEP source at each point and returns EPSG:5070 | one call per polygon, 4 threads; a failed window falls back to the 30 m DEM and is flagged | `dem_3dep_1m/landslides/{deposit,compilation}_<LANDSLIDE_ID>.tif` (1,638 files, 1.8 GB; first run about 25 min) | `usgs_3dep` |
| 3DEP source footprints | USGS 3DEP index | `py3dep.query_3dep_sources(bbox)` | one call (~100 s) | `dem_3dep_1m/3dep_sources.gpkg` | `usgs_3dep` |
| 30 m DEM (fallback) | the S1 3DEP download | read from the S1 cache | none | `dem/3dep_30m_rainier-v0.tif` | `usgs_3dep` |

The box of every query is `Domain.bbox_4326`, the lon/lat box that contains the projected model grid, so the
feature services return a little more than the grid; S24 clips everything to the grid bounds afterwards.

## From sources to catalogue

- **Flows** keep their outlines: the Qvl lahar units (Osceola, Electron, other) and the inventory polygons of
  type Flow, Debris flow or Hyperconcentrated flows.
- **Events** are points:
  - seismic location for `Events.csv`;
  - the mapped point for recent landslides;
  - the crown for every other landslide polygon. The crown is the highest point of the polygon outline,
    sampled every 2 m on its 1 m window. The field `crown_dem` records the 3DEP resolution under the crown
    (`3DEP 1m`, `3m` or `10m`, from the source footprints), or the 30 m fallback.
    Run of 2026-09-25: 994 crowns on 1 m lidar, 441 on 3 m, 186 on 10 m; 3 on the 30 m fallback (windows
    `deposit_66`, `compilation_5699` and `compilation_6044` were refused by the service on every attempt).
- A compilation polygon whose representative point lies inside a lidar-protocol deposit repeats that deposit
  and is dropped.

Outputs: `outputs/mass_movements/{flows,events,faults,lahar_zones}.gpkg`, `events.csv`, `summary.csv`,
`docs/paper/figures/fig16_mass_movements.png`, and, when the viewer bundle exists, `model/mass_flows.png`,
`mass_flows.u16.bin`, `mass_events.json` and a `layers.json` entry (S11 re-appends them on a rebuild).

## Sources considered and not scripted

- **Washington Lidar Portal (DNR) bare-earth DTMs.** These are 3 ft (0.91 m) grids, including the 2022
  "Rainier Wali" acquisition (dataset 1693). The portal lists its projects at `https://lidarportal.dnr.wa.gov/project`
  (JSON) and returns tile counts and sizes for an area with `POST https://lidarportal.dnr.wa.gov/query`
  (`geojson=<polygon>`). Downloads are whole tiles from `download?ids=<dataset>` or
  `download?geojson=<polygon>&ids=<dataset>`, and they return HTTP 403 unless the client first loads the portal
  page, which sets a `dlgate` cookie. Clipped to the model box, dataset 1693 is 38.9 GB in 75 files, and the
  portal has no elevation image service: its ArcGIS server offers only hillshade (`lidar/wadnr_hillshade`) and a
  geocoder. The contact for scripted access is the DNR lidar manager (listed on the portal's help page).
- **Exotic Seismic Events Catalog v3** (`esec_v3`): its ScienceBase record is under revision and has no file.
- **NSHM23 fault sections** (`nshm23_fsd`): read once to check; no section lies in the box.
