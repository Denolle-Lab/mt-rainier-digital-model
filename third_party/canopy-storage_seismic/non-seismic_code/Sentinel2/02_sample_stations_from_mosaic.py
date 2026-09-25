"""
Step 3 (mosaic version): Extract LAI at station points from the downloaded mosaic,
and add the result as new columns directly onto the existing stations CSV.

Run AFTER 01_download_lai.py has produced lai_mosaic_pnw.tif.

For each station, samples a small window (default 3x3 px) centered on the point
and takes the mean of valid (non-nodata, non-NaN) pixels -- more robust than a
single pixel against nodata/cloud gaps or minor coordinate rounding.
"""
import os
import numpy as np
import pandas as pd
import rasterio
from rasterio.transform import rowcol

MOSAIC_PATH = "../../output_non-seismic_code/Sentinel2/lai_mosaic_pnw.tif"
STATIONS_CSV = "../../seismic_data/df_station_locations.csv"
OUTPUT_CSV = "../../output_non-seismic_code/Sentinel2/station_lai_values.csv"
WINDOW = 1   # NxN pixel window centered on each point (must be odd)
NODATA = -9999


def sample_window(arr, row, col, window, nodata):
    half = window // 2
    r0, r1 = max(row - half, 0), min(row + half + 1, arr.shape[0])
    c0, c1 = max(col - half, 0), min(col + half + 1, arr.shape[1])
    patch = arr[r0:r1, c0:c1]
    # NaN-aware: NaN != nodata evaluates True in numpy, so NaN would otherwise
    # slip through as "valid" and silently poison np.mean(). Exclude explicitly.
    valid = patch[np.isfinite(patch) & (patch != nodata)]
    if valid.size == 0:
        return np.nan, 0, patch.size
    return float(np.mean(valid)), int(valid.size), int(patch.size)


if __name__ == "__main__":
    with rasterio.open(MOSAIC_PATH) as src:
        arr = src.read(1)
        transform = src.transform
        raster_crs = src.crs
        print(f"Mosaic loaded: shape={arr.shape}, crs={raster_crs}, nodata={src.nodata}")

    df = pd.read_csv(STATIONS_CSV)
    print(f"Loaded {len(df)} stations from {STATIONS_CSV}")
    print(f"Existing columns: {df.columns.tolist()}")

    lai_vals, n_valid_list, n_total_list = [], [], []
    n_outside = 0

    for _, row in df.iterrows():
        lat = float(row["latitude"])
        lon = float(row["longitude"])

        # station coords are WGS84 (EPSG:4326); mosaic should also be EPSG:4326
        # since all requests were made with CRS.WGS84 bboxes
        r, c = rowcol(transform, lon, lat)

        if r < 0 or r >= arr.shape[0] or c < 0 or c >= arr.shape[1]:
            lai_vals.append(np.nan)
            n_valid_list.append(0)
            n_total_list.append(0)
            n_outside += 1
            continue

        lai_mean, n_valid, n_total = sample_window(arr, r, c, WINDOW, NODATA)
        lai_vals.append(lai_mean)
        n_valid_list.append(n_valid)
        n_total_list.append(n_total)

    df["lai"] = lai_vals
    df["lai_n_valid_px"] = n_valid_list
    df["lai_n_total_px"] = n_total_list

    os.makedirs(os.path.dirname(OUTPUT_CSV) or ".", exist_ok=True)
    df.to_csv(OUTPUT_CSV, index=False)

    n_missing = df["lai"].isna().sum()
    print(f"\nDone. Wrote LAI columns back into {OUTPUT_CSV}")
    print(f"{n_outside} stations outside mosaic extent, "
          f"{n_missing - n_outside} inside but no valid pixels (cloud/nodata), "
          f"{len(df) - n_missing} with valid LAI values.")