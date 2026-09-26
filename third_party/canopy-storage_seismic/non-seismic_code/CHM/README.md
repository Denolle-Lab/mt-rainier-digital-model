# CHM (Canopy Height Model) — station values

`CHM_height_meter` is a finer, ~100 m² resolution canopy-height product —
distinct from GEDI L3's 1 km gridded `rh100_mean` (see `BIO_COL_MAP`'s
`'CH 100m²'` vs `'CH 1km²'` in `07_rainfall_spearman_hist.py` /
`07_storage_capacity_sup.py`).

## Canopy height from airborne LiDAR

Canopy height at each station is derived from airborne LiDAR (source:
WGS2023RainierWali — see the paper's references), via two scripts:

1. **`01_download_lidar_tiles.py`** — downloads only the DSM/DTM tiles
   that actually cover a station, from the WA DNR Lidar Portal
   (https://lidarportal.dnr.wa.gov/). The 240 stations span several WA
   DNR lidar acquisition projects (all part of the same 2022/2023 "Wali"
   campaign this citation refers to, e.g. "Rainier Wali 2022", "White
   Watershed Wali 2022"), not one single project — this script finds
   whichever project(s) cover each station and downloads from those.
   Still large: DSM/DTM tiles are ~1.5 ft resolution, so this is
   realistically 100+ GB. Resumable if interrupted.
2. **`02_process_chm.py`** — for each station, reads a small window
   (sized to ~10 m at each tile's native resolution) directly out of the
   one DSM and DTM tile that contains it, computes
   `CHM = mean(DSM - DTM) * 0.3048` (feet → meters) over that window, and
   writes `station_chm_values.csv`.

This is the scripted equivalent of building a full DSM/DTM mosaic,
computing CHM over it, downsampling to 10 m by averaging, and sampling at
station points in QGIS — restricted to just the ~10 m neighborhood each
station actually needs, which is what `02_process_chm.py`'s own docstring
walks through step by step.

A station can come out with `CHM_height_meter = NaN` for two different
reasons, both reported by the two scripts as they run: it falls outside
every "Wali"-project footprint entirely, or (confirmed to happen in
practice) it sits right at a seam between two tiles where WA DNR's own
tile grid has a small real gap.

## Output

`station_chm_values.csv`, with at minimum:

    station, CHM_height_meter

written to `../output_non-seismic_code/CHM/` (never overwriting reference
data, same convention as GEDI and Sentinel-2's own outputs) —
`merge_station_veg.py` reads it from there and merges it into
`station_veg.csv` alongside the GEDI and Sentinel-2 columns. Until this
file is produced, `merge_station_veg.py` still runs; `CHM_height_meter`
comes out all-NaN with a warning.
