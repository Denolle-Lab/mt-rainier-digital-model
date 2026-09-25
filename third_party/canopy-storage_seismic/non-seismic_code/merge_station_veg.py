"""
merge_station_veg.py

Consolidates the vegetation/canopy predictors from GEDI (canopy height +
PAI), Sentinel-2 (LAI), and the QGIS-derived CHM -- plus the station
locations themselves -- into ONE per-station table, station_veg.csv,
matching the shipped reference (result_non-seismic_code/station_veg.csv)
and the format the seismic_code pipeline reads (BIO_COL_MAP in
07_rainfall_spearman_hist.py / 07_storage_capacity_sup.py):

    station, latitude, longitude, elevation_m,
    lai, lai_n_valid_px, lai_n_total_px,
    CHM_height_meter,
    gedi_l3_rh100_mean, gedi_l2b_pai_mean

Run AFTER:
    - GEDI/04_extract_values_at_stations.py
      (produces ../output_non-seismic_code/GEDI/stations_with_gedi_values.csv)
    - Sentinel2/02_sample_stations_from_mosaic.py
      (produces ../output_non-seismic_code/Sentinel2/station_lai_values.csv)
    - the CHM step, which is a MANUAL QGIS workflow, not a script (see
      CHM/README.md) -- its output is checked in directly at CHM_CSV
      below, the same way seismic_data/ and result_seismic_code/ are
      provided reference data rather than something regenerated here.

CHM_height_meter is a finer, ~100 m^2-resolution canopy-height product,
distinct from GEDI L3's 1 km gridded rh100_mean (see BIO_COL_MAP's
'CH 100m^2' vs 'CH 1km^2'). If CHM_CSV isn't present yet, this script still
runs -- CHM_height_meter is written as all-NaN with a warning, rather than
failing, so station_veg.csv stays usable while that step is pending.
"""

import os
import numpy as np
import pandas as pd

STATIONS_CSV = "../seismic_data/df_station_locations.csv"
GEDI_CSV = "../output_non-seismic_code/GEDI/stations_with_gedi_values.csv"
LAI_CSV = "../output_non-seismic_code/Sentinel2/station_lai_values.csv"
# Manual QGIS output (station, CHM_height_meter) -- see CHM/README.md for
# the source raster and exact QGIS steps used to produce it.
CHM_CSV = "CHM/station_chm_values.csv"

OUT_CSV = "../output_non-seismic_code/station_veg.csv"

# Columns pulled from stations_with_gedi_values.csv (that file's own
# _dist_m QC columns are intentionally dropped here -- not part of this
# consolidated table, still available in the GEDI output itself for QC).
GEDI_COLS = ["gedi_l3_rh100_mean", "gedi_l2b_pai_mean"]

OUT_COLUMNS = [
    "station", "latitude", "longitude", "elevation_m",
    "lai", "lai_n_valid_px", "lai_n_total_px",
    "CHM_height_meter",
    "gedi_l3_rh100_mean", "gedi_l2b_pai_mean",
]


def load_chm(path):
    """station -> CHM_height_meter, from the manual QGIS output. All-NaN
    (with a warning) if that file hasn't been added yet, so this script
    stays runnable while the CHM step is pending."""
    if not os.path.isfile(path):
        print(f"[merge_station_veg] WARNING: {path} not found -- "
              f"CHM_height_meter written as all-NaN. See CHM/README.md "
              f"for how to produce it (QGIS, manual step, not a script).")
        return pd.DataFrame(columns=["station", "CHM_height_meter"])

    chm = pd.read_csv(path)
    if "CHM_height_meter" not in chm.columns:
        raise KeyError(
            f"{path} has no 'CHM_height_meter' column -- found {list(chm.columns)}. "
            f"Check the QGIS export (see CHM/README.md).")
    return chm[["station", "CHM_height_meter"]]


def main():
    stations = pd.read_csv(STATIONS_CSV)

    lai = pd.read_csv(LAI_CSV)[["station", "lai", "lai_n_valid_px", "lai_n_total_px"]]

    gedi = pd.read_csv(GEDI_CSV)
    missing_gedi_cols = [c for c in GEDI_COLS if c not in gedi.columns]
    if missing_gedi_cols:
        raise KeyError(
            f"{GEDI_CSV} is missing expected column(s) {missing_gedi_cols} -- "
            f"check PARAMETERS in GEDI/04_extract_values_at_stations.py.")
    gedi = gedi[["station"] + GEDI_COLS]

    chm = load_chm(CHM_CSV)

    out = (stations
           .merge(lai, on="station", how="left")
           .merge(gedi, on="station", how="left")
           .merge(chm, on="station", how="left"))

    out = out[OUT_COLUMNS]

    os.makedirs(os.path.dirname(OUT_CSV) or ".", exist_ok=True)
    out.to_csv(OUT_CSV, index=False)
    print(f"Saved {len(out)} station(s) -> {OUT_CSV}")


if __name__ == "__main__":
    main()
