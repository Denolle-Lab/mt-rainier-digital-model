"""
Grid GEDI L2B PAI footprints (from download_gedi_l2b_pai.py) into a
1km raster, using the same EPSG:6933 equal-area convention GEDI itself
uses for L4B.

In addition to max PAI, this computes per grid cell:
  - counts   : total footprint count (like L4B's NS)
  - ntracks  : number of DISTINCT ground-track passes (granule+beam)
               contributing to the cell (like L4B's NC / "Number of
               Clusters"). Footprints from the same overpass are
               spatially correlated, not independent samples, so this
               matters more than raw footprint count for judging
               how many independent observations the max is drawn from.

Note: standard error is a property of a *mean* estimator, so it isn't
computed here -- it wouldn't be meaningful for a per-cell max. Use
counts/ntracks to gauge how well-sampled a cell is instead.

Requirements:
    pip install pandas numpy rasterio pyproj
"""

import os
import numpy as np
import pandas as pd
import rasterio
from rasterio.transform import from_origin
from pyproj import Transformer

# ---------------------------------------------------------------
# USER SETTINGS
# ---------------------------------------------------------------
IN_CSV = "../../output_non-seismic_code/GEDI/gedi_l2b_pai/footprints/footprints_qcfiltered.csv"
OUT_DIR = "../../output_non-seismic_code/GEDI/gedi_l2b_pai/gridded"

CELL_SIZE_M = 1000       # 1 km, matching GEDI L4B's grid convention
GRID_CRS = "EPSG:6933"   # equal-area, meters -- same as L4B
# ---------------------------------------------------------------

os.makedirs(OUT_DIR, exist_ok=True)

df = pd.read_csv(IN_CSV)
print(f"Loaded {len(df)} footprints from {IN_CSV}")

transformer = Transformer.from_crs("EPSG:4326", GRID_CRS, always_xy=True)
df["x"], df["y"] = transformer.transform(df["lon"].values, df["lat"].values)

xmin = np.floor(df["x"].min() / CELL_SIZE_M) * CELL_SIZE_M
xmax = np.ceil(df["x"].max() / CELL_SIZE_M) * CELL_SIZE_M
ymin = np.floor(df["y"].min() / CELL_SIZE_M) * CELL_SIZE_M
ymax = np.ceil(df["y"].max() / CELL_SIZE_M) * CELL_SIZE_M

n_cols = int((xmax - xmin) / CELL_SIZE_M)
n_rows = int((ymax - ymin) / CELL_SIZE_M)
print(f"Grid size: {n_rows} rows x {n_cols} cols at {CELL_SIZE_M} m cells")

df["col"] = ((df["x"] - xmin) / CELL_SIZE_M).astype(int).clip(0, n_cols - 1)
df["row"] = ((ymax - df["y"]) / CELL_SIZE_M).astype(int).clip(0, n_rows - 1)

grouped = df.groupby(["row", "col"]).agg(
    max=("pai", "max"),
    count=("pai", "count"),
    ntracks=("track_id", "nunique"),
).reset_index()

layers = {
    "max": np.full((n_rows, n_cols), np.nan, dtype=np.float64),
    "count": np.zeros((n_rows, n_cols), dtype=np.int64),
    "ntracks": np.zeros((n_rows, n_cols), dtype=np.int64),
}
rows, cols = grouped["row"].values, grouped["col"].values
layers["max"][rows, cols] = grouped["max"].values
layers["count"][rows, cols] = grouped["count"].values
layers["ntracks"][rows, cols] = grouped["ntracks"].values

n_populated = int(np.sum(layers["count"] > 0))
n_multi_track = int(np.sum(layers["ntracks"] >= 2))
print(f"Populated cells: {n_populated} / {n_rows * n_cols} "
      f"({100 * n_populated / (n_rows * n_cols):.1f}%)")
print(f"Cells with >= 2 distinct tracks: {n_multi_track} / {n_populated} populated "
      f"({100 * n_multi_track / max(n_populated, 1):.1f}%)")

transform = from_origin(xmin, ymax, CELL_SIZE_M, CELL_SIZE_M)
base_profile = {
    "driver": "GTiff", "height": n_rows, "width": n_cols, "count": 1,
    "crs": GRID_CRS, "transform": transform,
}
dtypes_nodata = {
    "max": ("float32", np.nan),
    "count": ("int32", 0), "ntracks": ("int32", 0),
}

for var_name, array in layers.items():
    dtype, nodata = dtypes_nodata[var_name]
    profile = base_profile.copy()
    profile.update(dtype=dtype, nodata=nodata)
    out_path = os.path.join(OUT_DIR, f"L2B_PAI_{var_name}.tif")
    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(array.astype(dtype), 1)
    print(f"Saved -> {out_path}")

print(f"\nDone. Gridded files are in: {os.path.abspath(OUT_DIR)}")