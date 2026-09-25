# CHM (Canopy Height Model) — station values

`CHM_height_meter` is a finer, ~100 m² resolution canopy-height product —
distinct from GEDI L3's 1 km gridded `rh100_mean` (see `BIO_COL_MAP`'s
`'CH 100m²'` vs `'CH 1km²'` in `07_rainfall_spearman_hist.py` /
`07_storage_capacity_sup.py`).

Unlike GEDI, Sentinel-2, and MRMS, this one was produced **manually in
QGIS**, not through a scriptable download/processing pipeline — so there's
no `0X_*.py` script here, and none is planned; the steps below are the
record of how it was made instead.

## Canopy height from airborne LiDAR

Canopy height at each station is derived from airborne LiDAR (source:
WGS2023RainierWali — see the paper's references) following these
processing steps:

1. **Build virtual mosaics.** In QGIS (Raster → Miscellaneous → Build
   Virtual Raster), combine all Digital Surface Model (DSM) tiles into a
   single virtual mosaic (`dsm_mosaic.vrt`), and repeat separately for the
   Digital Terrain Model (DTM) tiles (`dtm_mosaic.vrt`), without placing
   each input into a separate band.
2. **Compute canopy height.** Using the Raster Calculator, subtract the
   DTM from the DSM and convert from feet to meters:

       CHM = (DSM - DTM) * 0.3048

   with the output extent calculated from the DSM mosaic and the output
   CRS matching the input layers. This yields a full-resolution canopy
   height model (CHM).
3. **Downsample to 10 m.** Using Warp (Reproject) with the *average*
   resampling method (giving the mean canopy height per output cell) and
   an output resolution of 10 m (32.8 ft), producing `CHM_10m.tif`.
4. **Sample at station locations.** Using the "Sample Raster Values" tool
   with the station coordinates as input points and `CHM_10m.tif` as the
   raster layer, extract a canopy height value per station.
5. **Export.** Save the sampled layer as a CSV with station coordinates
   included as separate X/Y columns.

## Output

`station_chm_values.csv`, with at minimum:

    station, CHM_height_meter

placed in this folder — `merge_station_veg.py` reads it from here
(`CHM_CSV = "CHM/station_chm_values.csv"`) and merges it into
`station_veg.csv` alongside the GEDI and Sentinel-2 columns. Until this
file is added, `merge_station_veg.py` still runs; `CHM_height_meter` comes
out all-NaN with a warning.
