"""
Download GEDI L2B footprint data and extract PAI (Plant Area Index --
the closest available proxy for LAI; GEDI has no native LAI product)
for a region of interest.

Output: a CSV of footprint-level points (lon, lat, pai, quality info,
track info) that 02_grid_gedi_l2b_pai.py then bins into a 1km raster.

Requirements:
    pip install earthaccess h5py numpy pandas

Authentication:
    Uses your NASA Earthdata Login credentials (free account at
    https://urs.earthdata.nasa.gov/users/new if you don't have one).
    earthaccess.login(persist=True) prompts once and caches creds.
"""

import os
import warnings
import h5py
import numpy as np
import pandas as pd
import earthaccess

warnings.filterwarnings("ignore", category=FutureWarning)

# ---------------------------------------------------------------
# USER SETTINGS
# ---------------------------------------------------------------
BBOX = (-122.5, 46.0, -120.5, 48.0)   # (min_lon, min_lat, max_lon, max_lat)

# PAI is seasonally variable (unlike L3 height or L4B biomass), so every
# window is restricted to the SAME season (summer) across multiple years
# rather than pooling all seasons -- pooling leaf-on and leaf-off data
# together would produce a physically meaningless average. Skip 2023
# (instrument in storage Mar 2023 - Apr 2024).
TEMPORAL_WINDOWS = [
    ("2019-06-01", "2019-08-31"),
    ("2020-06-01", "2020-08-31"),
    ("2021-06-01", "2021-08-31"),
    ("2022-06-01", "2022-08-31"),
    ("2024-06-01", "2024-08-31"),
    ("2025-06-01", "2025-08-31"),
]

# Quality filtering. GEDI's own recommended thresholds are strict
# (l2b_quality_flag==1, degrade_flag==0, sensitivity>=0.9). In steep
# terrain a lot of otherwise-usable shots get dropped by these, so both
# options are supported -- compare the two before deciding which to use.
#   True  -- apply GEDI's recommended quality filter
#   False -- keep every footprint (only literal fill/invalid PAI values
#            are dropped; that's not "low quality data", it's simply
#            not a measurement)
APPLY_QUALITY_FILTER = True
MIN_SENSITIVITY = 0.9
REQUIRE_QUALITY_FLAG = 1
REQUIRE_DEGRADE_FLAG = 0

RAW_DIR = "../../output_non-seismic_code/GEDI/gedi_l2b_pai/raw"
OUT_DIR = "../../output_non-seismic_code/GEDI/gedi_l2b_pai/footprints"

# Confirmed via CMR lookup: GEDI02_B, v002
CONCEPT_ID = "C2142776747-LPCLOUD"
# ---------------------------------------------------------------

os.makedirs(RAW_DIR, exist_ok=True)
os.makedirs(OUT_DIR, exist_ok=True)

print("Authenticating with NASA Earthdata Login...")
earthaccess.login(persist=True)

print(f"Searching concept-id {CONCEPT_ID} for granules over bbox {BBOX} "
      f"across {len(TEMPORAL_WINDOWS)} summer window(s)...")

all_results = []
for temporal in TEMPORAL_WINDOWS:
    results = earthaccess.search_data(
        concept_id=CONCEPT_ID, bounding_box=BBOX, temporal=temporal,
    )
    print(f"  {temporal}: {len(results)} granule(s)")
    all_results.extend(results)

print(f"Total granules across all windows: {len(all_results)}")
if not all_results:
    print("\nNo granules matched any window. Check BBOX, CONCEPT_ID, "
          "or widen TEMPORAL_WINDOWS.")
    raise SystemExit(0)

print("Downloading granules (this can be slow -- L2B files are large)...")
downloaded_paths = sorted(set(str(p) for p in earthaccess.download(all_results, RAW_DIR)))

# --- Extract PAI per footprint from each HDF5 granule ---
minlon, minlat, maxlon, maxlat = BBOX
records = []

for path in downloaded_paths:
    if not path.endswith(".h5"):
        continue
    fname = os.path.basename(path)
    try:
        year = int(fname.split("_")[2][:4])  # GEDI filenames encode YYYYDDD
    except (IndexError, ValueError):
        year = None

    with h5py.File(path, "r") as f:
        for beam in (k for k in f.keys() if k.startswith("BEAM")):
            grp = f[beam]
            if "pai" not in grp:
                continue

            geo = grp["geolocation"]
            lat = geo["lat_lowestmode"][:]
            lon = geo["lon_lowestmode"][:]
            pai = grp["pai"][:]
            quality_flag = grp["l2b_quality_flag"][:]
            degrade_flag = geo["degrade_flag"][:]
            sensitivity = grp["sensitivity"][:] if "sensitivity" in grp else np.ones_like(pai)

            in_bbox = (
                (lon >= minlon) & (lon <= maxlon) &
                (lat >= minlat) & (lat <= maxlat)
            )
            if APPLY_QUALITY_FILTER:
                good_quality = (
                    (quality_flag == REQUIRE_QUALITY_FLAG) &
                    (degrade_flag == REQUIRE_DEGRADE_FLAG) &
                    (sensitivity >= MIN_SENSITIVITY) &
                    (pai >= 0)
                )
            else:
                good_quality = (pai >= 0)  # drop literal fill/invalid values only

            keep = in_bbox & good_quality
            if not np.any(keep):
                continue

            records.append(pd.DataFrame({
                "lon": lon[keep],
                "lat": lat[keep],
                "pai": pai[keep],
                "beam": beam,
                "granule": fname,
                "year": year,
                # (granule, beam) = one distinct ground-track pass, used
                # later to avoid treating footprints from a single
                # overpass as independent samples
                "track_id": f"{fname}_{beam}",
            }))

if not records:
    print("\nNo footprints passed the bbox/quality filters. Check BBOX, "
          "TEMPORAL_WINDOWS, and quality settings.")
    raise SystemExit(0)

all_points = pd.concat(records, ignore_index=True)
suffix = "qcfiltered" if APPLY_QUALITY_FILTER else "noqcfilter"
out_path = os.path.join(OUT_DIR, f"footprints_{suffix}.csv")
all_points.to_csv(out_path, index=False)

print(f"\nSaved {len(all_points)} footprints to {os.path.abspath(out_path)}")
print(f"Next: point IN_CSV in 02_grid_gedi_l2b_pai.py to this file.")
