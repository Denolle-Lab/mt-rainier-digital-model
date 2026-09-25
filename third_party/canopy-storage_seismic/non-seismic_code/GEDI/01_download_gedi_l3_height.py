"""
Download GEDI L3 Gridded Land Surface Metrics (canopy height + ground
elevation, 1km), cropped to a region of interest.

Unlike a single static composite, NASA has periodically reprocessed
and re-released this product with more accumulated data over time
(each release has a different end date). This script keeps only the
most recent release by default.

Requirements:
    pip install earthaccess rasterio shapely numpy

Authentication:
    Uses your NASA Earthdata Login credentials (free account at
    https://urs.earthdata.nasa.gov/users/new if you don't have one).
    earthaccess.login(persist=True) prompts once and caches creds.
"""

import os
import warnings
import numpy as np
import rasterio
import earthaccess
from gedi_utils import crop_to_bbox, compute_se

warnings.filterwarnings("ignore", category=FutureWarning)

# ---------------------------------------------------------------
# USER SETTINGS
# ---------------------------------------------------------------
BBOX = (-122.5, 46.0, -120.5, 48.0)   # (min_lon, min_lat, max_lon, max_lat)

# Variables available in this product. Set to None to keep all.
#   rh100_mean, rh100_stddev     -- canopy height
#   elev_lowestmode_mean/stddev  -- ground elevation, not canopy height
#   counts                       -- footprint count per cell
VARIABLES_WANTED = ["rh100_mean", "rh100_stddev", "counts"]

# Keep only the newest reprocessing release instead of all historical ones
USE_LATEST_RELEASE_ONLY = True

RAW_DIR = "../../output_non-seismic_code/GEDI/gedi_l3/raw"
CROP_DIR = "../../output_non-seismic_code/GEDI/gedi_l3/cropped"

# Confirmed via CMR lookup: GEDI_L3_LandSurface_Metrics_V2_1952, v2
CONCEPT_ID = "C2153683336-ORNL_CLOUD"
# ---------------------------------------------------------------

os.makedirs(RAW_DIR, exist_ok=True)
os.makedirs(CROP_DIR, exist_ok=True)

print("Authenticating with NASA Earthdata Login...")
earthaccess.login(persist=True)

print(f"Searching concept-id {CONCEPT_ID} for granules over bbox {BBOX} ...")
results = earthaccess.search_data(concept_id=CONCEPT_ID, bounding_box=BBOX)
print(f"Found {len(results)} matching granule(s).")

if not results:
    print("\nNo granules matched this bbox. Check BBOX and CONCEPT_ID.")
    raise SystemExit(0)


def parse_filename(fname):
    """e.g. GEDI03_rh100_mean_2019108_2025190_002_05.tif
    -> ('rh100_mean', '2025190', '002_05')"""
    stem = fname.replace(".tif", "")
    parts = stem.split("_")
    end_date = parts[-3]
    release = parts[-2] + "_" + parts[-1]
    variable = "_".join(parts[1:-4])
    return variable, end_date, release


all_tif_urls = [
    url for granule in results for url in granule.data_links()
    if url.lower().endswith(".tif")
]
parsed = [(url, *parse_filename(os.path.basename(url))) for url in all_tif_urls]

if USE_LATEST_RELEASE_ONLY:
    latest_end_date = max(p[2] for p in parsed)
    parsed = [p for p in parsed if p[2] == latest_end_date]
    print(f"Keeping only the most recent release (end_date={latest_end_date})")

files_to_download = [p[0] for p in parsed if VARIABLES_WANTED is None or p[1] in VARIABLES_WANTED]

print(f"Downloading {len(files_to_download)} file(s):")
for f in files_to_download:
    print("  ", os.path.basename(f))

if not files_to_download:
    print("No matching files. Check VARIABLES_WANTED against available "
          "variables printed above.")
    raise SystemExit(0)

downloaded_paths = earthaccess.download(files_to_download, RAW_DIR)

# Crop each to the bbox and rename to a standardized "L3_<VAR>.tif" name
cropped = {}
for path in sorted(set(str(p) for p in downloaded_paths)):
    if not path.endswith(".tif"):
        continue
    fname = os.path.basename(path)
    var_name, _, _ = parse_filename(fname)
    out_path = os.path.join(CROP_DIR, f"L3_{var_name}.tif")

    info = crop_to_bbox(path, out_path, BBOX)
    print(f"{fname} -> {os.path.basename(out_path)} "
          f"(native CRS: {info['native_crs']}, shape: {info['shape']}, "
          f"valid pixels: {info['n_valid']})")
    if info["shape"][0] <= 1 or info["shape"][1] <= 1:
        print("  WARNING: crop is 1 pixel or smaller -- bbox may not overlap this tile.")
    cropped[var_name] = out_path

# Derive a standard-error layer (stddev / sqrt(counts)) for each mean/stddev
# pair present, matching how uncertainty is handled for L2B PAI. This is
# NOT provided natively by L3 -- only stddev and counts are.
for base in ["rh100", "elev_lowestmode"]:
    mean_key, std_key = f"{base}_mean", f"{base}_stddev"
    if mean_key in cropped and std_key in cropped and "counts" in cropped:
        with rasterio.open(cropped[std_key]) as src_std:
            std_data = src_std.read(1).astype(float)
            nodata = src_std.nodata
            if nodata is not None:
                std_data[std_data == nodata] = np.nan
            profile = src_std.profile.copy()
        with rasterio.open(cropped["counts"]) as src_count:
            count_data = src_count.read(1).astype(float)

        se_data = compute_se(std_data, count_data)
        se_var = base.replace("_lowestmode", "") + "_SE"
        se_path = os.path.join(CROP_DIR, f"L3_{se_var}.tif")
        profile.update(dtype="float32", nodata=np.nan)
        with rasterio.open(se_path, "w", **profile) as dst:
            dst.write(se_data.astype("float32"), 1)
        print(f"Derived {os.path.basename(se_path)} from {std_key} and counts")

print(f"\nDone. Cropped files are in: {os.path.abspath(CROP_DIR)}")
