"""
Extract raster values at station locations, for any GEDI-derived
raster (L3 canopy height, self-gridded L2B PAI, ...).

For each station:
  1. Try the exact pixel at the station's location.
  2. If that pixel is nodata, search outward (in meters) up to
     SEARCH_RADIUS_M and take the value from the nearest valid pixel.
  3. If nothing valid is found within the radius, report NaN.

Distance is measured from the station's exact (sub-pixel) location to
each candidate cell's boundary -- not center-to-center. This means:
  - dist_m == 0   : the station falls inside a cell that already has
                     valid data (no need to reach for a neighbor)
  - dist_m > 0    : the station's own cell was empty; this is the
                     distance to the nearest edge of the nearest cell
                     that did have valid data
  - dist_m is NaN : nothing valid was found within SEARCH_RADIUS_M

Every raster is reprojected on the fly to EPSG:6933 (equal-area,
meters) before sampling, so the radius search is a true metric
distance regardless of the raster's native CRS.

Requirements:
    pip install rasterio pandas numpy pyproj
"""

import glob
import os
import numpy as np
import pandas as pd
import rasterio
from rasterio.vrt import WarpedVRT
from rasterio.enums import Resampling
from pyproj import Transformer
from gedi_utils import strip_product_prefix

# ---------------------------------------------------------------
# USER SETTINGS
# ---------------------------------------------------------------
# List of specific raster files to extract, one column per entry.
# Defaults to just the MAIN value from each product (not SE/count/QF/
# ntracks) -- add more paths here if you also want those extracted,

PARAMETERS = [
    "../../output_non-seismic_code/GEDI/gedi_l3/cropped/L3_rh100_mean.tif",
    "../../output_non-seismic_code/GEDI/gedi_l2b_pai/gridded/L2B_PAI_mean.tif",
]
PRODUCT_PREFIXES = [ "L3_", "L2B_PAI_"]

STATION_CSV = "../../seismic_data/df_station_locations.csv"
OUT_CSV = "../../output_non-seismic_code/GEDI/stations_with_gedi_values.csv"

SEARCH_RADIUS_M = 500   # how far to look for the nearest valid pixel
WORK_CRS = "EPSG:6933"   # equal-area, meters -- all rasters reprojected here
# ---------------------------------------------------------------


def sample_raster_at_points(raster_path, xs, ys, search_radius_m):
    """xs, ys must already be in WORK_CRS."""
    with rasterio.open(raster_path) as src:
        with WarpedVRT(src, crs=WORK_CRS, resampling=Resampling.nearest) as vrt:
            data = vrt.read(1).astype(float)
            nodata = vrt.nodata
            if nodata is not None and not np.isnan(nodata):
                data[data == nodata] = np.nan
            transform = vrt.transform
            n_rows, n_cols = data.shape
            inv_transform = ~transform

    # Affine transform coefficients: x = a*col + b*row + c, y = d*col + e*row + f.
    # Our rasters are always north-up / axis-aligned (b == d == 0), so cell
    # boundaries in world coordinates come directly from a, e, c, f.
    a, e, c, f = transform.a, transform.e, transform.c, transform.f
    px_size = abs(a)
    radius_px = int(np.ceil(search_radius_m / px_size)) + 1  # small safety margin

    values = np.full(len(xs), np.nan)
    distances_m = np.full(len(xs), np.nan)

    for i, (x, y) in enumerate(zip(xs, ys)):
        col_f, row_f = inv_transform * (x, y)
        row_home, col_home = int(np.floor(row_f)), int(np.floor(col_f))

        if (0 <= row_home < n_rows and 0 <= col_home < n_cols
                and not np.isnan(data[row_home, col_home])):
            values[i] = data[row_home, col_home]
            distances_m[i] = 0.0
            continue

        r0, r1 = max(0, row_home - radius_px), min(n_rows, row_home + radius_px + 1)
        c0, c1 = max(0, col_home - radius_px), min(n_cols, col_home + radius_px + 1)
        window = data[r0:r1, c0:c1]
        if not np.any(~np.isnan(window)):
            continue  # stays NaN -- nothing valid anywhere in the window

        rr, cc = np.meshgrid(np.arange(r0, r1), np.arange(c0, c1), indexing="ij")

        # Cell boundaries for every candidate pixel (world coordinates)
        cell_xmin = a * cc + c
        cell_xmax = a * (cc + 1) + c
        cell_ymax = e * rr + f       # e < 0 for north-up rasters, so row 0 is the north edge
        cell_ymin = e * (rr + 1) + f

        # True point-to-rectangle distance: 0 if (x,y) is inside/on the
        # cell, otherwise distance to the nearest edge/corner.
        dx = np.maximum(cell_xmin - x, 0)
        dx = np.maximum(dx, x - cell_xmax)
        dy = np.maximum(cell_ymin - y, 0)
        dy = np.maximum(dy, y - cell_ymax)
        dist_m = np.sqrt(dx ** 2 + dy ** 2)

        valid = ~np.isnan(window) & (dist_m <= search_radius_m)
        if not np.any(valid):
            continue  # stays NaN -- nothing valid within the radius

        nearest_idx = np.argmin(np.where(valid, dist_m, np.inf))
        values[i] = window.flat[nearest_idx]
        distances_m[i] = dist_m.flat[nearest_idx]

    return values, distances_m


stations = pd.read_csv(STATION_CSV)
transformer = Transformer.from_crs("EPSG:4326", WORK_CRS, always_xy=True)
xs, ys = transformer.transform(stations["longitude"].values, stations["latitude"].values)

raster_paths = []
for entry in PARAMETERS:
    if "*" in entry:
        matches = sorted(glob.glob(entry))
        if not matches:
            print(f"WARNING: no files matched pattern '{entry}'")
        raster_paths.extend(matches)
    elif os.path.exists(entry):
        raster_paths.append(entry)
    else:
        print(f"WARNING: file not found, skipping: {entry}")

if not raster_paths:
    raise FileNotFoundError("No raster files found. Check PARAMETERS.")

print(f"Sampling {len(raster_paths)} raster(s) at {len(stations)} station(s), "
      f"search radius = {SEARCH_RADIUS_M} m\n")

out = stations.copy()
for path in raster_paths:
    var_name = strip_product_prefix(path, PRODUCT_PREFIXES)
    # Prefix with product folder name to avoid collisions between
    # products that happen to share a variable name (e.g. "SE")
    product = os.path.basename(os.path.dirname(os.path.dirname(path)))
    col_name = f"{product}_{var_name}"

    values, distances_m = sample_raster_at_points(path, xs, ys, SEARCH_RADIUS_M)
    out[col_name] = values
    out[f"{col_name}_dist_m"] = distances_m

    n_direct = int(np.sum(distances_m == 0))
    n_fallback = int(np.sum(distances_m > 0))
    n_missing = int(np.sum(np.isnan(values)))
    print(f"{col_name}: {n_direct} direct hit(s), {n_fallback} fallback "
          f"(nearest within {SEARCH_RADIUS_M}m), {n_missing} still NaN")

os.makedirs(os.path.dirname(OUT_CSV) or ".", exist_ok=True)
out.to_csv(OUT_CSV, index=False)
print(f"\nSaved {os.path.abspath(OUT_CSV)}")
