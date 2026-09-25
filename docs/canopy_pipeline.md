# Canopy-storage pipeline (S28)

`pixi run -e canopy canopy` (`scripts/28_canopy_pipeline.py`) runs the gridded-product scripts of Manuela
Köpfli's canopy-storage project, vendored unmodified in `third_party/canopy-storage_seismic/non-seismic_code/`
(MIT; commit and changes in `third_party/canopy-storage_seismic/PROVENANCE.md`). S19 then reads the products
from `data/raw/canopy_storage/output_non-seismic_code/` (`pipeline_file` in `configs/canopy_products.yaml`)
and falls back to the delivered files for the layers the pipeline does not make.

## How the scripts are run

The upstream scripts use paths relative to their own folder (`../../output_non-seismic_code/...`). S28 copies
`non-seismic_code/` to `data/raw/canopy_storage/non-seismic_code/` and runs each script from its folder, so
every download and product stays in the raw-data cache. A step whose product exists is skipped (`--force`
reruns it). A step without its credentials is skipped with a warning. Figures (`GEDI/03_*`) and station
sampling (`GEDI/04`, `Sentinel2/02`, `MRMS/`, `merge_station_veg.py`) are not run: they need the project's
station CSV.

## Service calls

All scripts query the box lon −122.5 to −120.5, lat 46.0 to 48.0 (set in each script), which contains the
model domain.

| Step | Script | Service | Call | Credentials | Output (under `output_non-seismic_code/`) | Registry key |
|---|---|---|---|---|---|---|
| `gedi_l3` | `GEDI/01_download_gedi_l3_height.py` | NASA CMR and ORNL DAAC cloud (earthaccess) | `earthaccess.login(persist=True)`; `earthaccess.search_data(concept_id="C2153683336-ORNL_CLOUD", bounding_box=BOX)`; `earthaccess.download(<rh100_mean, rh100_stddev, counts granules>)`; crop to the box | NASA Earthdata login: `~/.netrc` entry for `urs.earthdata.nasa.gov`, or `EARTHDATA_USERNAME` / `EARTHDATA_PASSWORD` | `GEDI/gedi_l3/raw/`, `GEDI/gedi_l3/cropped/L3_rh100_{mean,stddev,counts,SE}.tif` | `gedi_l3` |
| `gedi_l2b` | `GEDI/01_download_gedi_l2b_pai.py` | NASA CMR and LP DAAC cloud (earthaccess) | `earthaccess.search_data(concept_id="C2142776747-LPCLOUD", bounding_box=BOX, temporal=w)` for the summers (1 Jun to 31 Aug) of 2019–2022, 2024 and 2025; `earthaccess.download`; footprints kept if `quality_flag == 1`, `degrade_flag == 0`, sensitivity ≥ 0.9 | as above | `GEDI/gedi_l2b_pai/raw/*.h5`, `GEDI/gedi_l2b_pai/footprints/footprints_qcfiltered.csv` | `gedi_l2b` |
| `gedi_l2b_grid` | `GEDI/02_grid_gedi_l2b_pai.py` | none | footprints binned on a 1 km EPSG:6933 grid | none | `GEDI/gedi_l2b_pai/gridded/L2B_PAI_{max,count,ntracks}.tif` | `gedi_l2b` |
| `s2_lai` | `Sentinel2/01_download_lai.py` | Sentinel Hub Process API on the Copernicus Data Space (`https://sh.dataspace.copernicus.eu`, token `https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token`) | Sentinel-2 L2A, SNAP biophysical LAI evalscript, 2023-07-01 to 2023-08-15, `mosaicking_order="leastCC"`, 10 m, tiles of at most 2400 × 2400 px, 3 s between requests; tiles merged | `SH_CLIENT_ID`, `SH_CLIENT_SECRET` (environment, or a `.env` read by python-dotenv) | `Sentinel2/lai_tiles/`, `Sentinel2/lai_mosaic_pnw.tif` | `sentinel2_lai_2023` |

## Which S19 layers come from here

| S19 layer | From S28 | Otherwise |
|---|---|---|
| `gedi_canopy_height` | `GEDI/gedi_l3/cropped/L3_rh100_mean.tif` | delivered file |
| `lai_sentinel2` | `Sentinel2/lai_mosaic_pnw.tif` | delivered file |
| `gedi_pai` | not produced: the gridder writes the maximum, not the mean | delivered `L2B_PAI_mean.tif` |
| `gedi_biomass`, `gedi_biomass_se` | no script (GEDI L4B) | delivered files |
| `canopy_height_lidar`, `vegetation_cover_lidar` | no grid script: `CHM/01`–`02` give values at stations only, from the WA DNR Lidar Portal 2022–2023 "Wali" DSM and DTM; the grids were made from the same tiles in QGIS | delivered files |
| `soil_map` | no script | delivered file |
