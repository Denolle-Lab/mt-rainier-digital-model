"""
02_process_chm.py

Computes CHM_height_meter (canopy height, ~10 m resolution) at every
station from the DSM/DTM tiles 01_download_lidar_tiles.py downloaded,
reproducing the original manual QGIS workflow (see this folder's
README.md for that record) without ever materializing its intermediate
products:

  QGIS workflow                          This script
  ------------------------------------   --------------------------------
  1. Build DSM/DTM virtual mosaics       Skipped -- for each station, the
                                          one tile (if any) whose footprint
                                          actually contains it is opened
                                          directly; no mosaic needed when
                                          you only ever read points out of
                                          it.
  2. CHM = (DSM - DTM) * 0.3048          Same formula, applied only to the
     (feet -> meters)                    small window read per station.
  3. Downsample to 10 m via average      Same result: the window read per
     resampling                          station is sized (from the tile's
                                          own native resolution) to cover
                                          one ~10 m output cell, and
                                          averaged the same way.
  4. Sample CHM_10m.tif at stations      Steps 2-3 already only ever
                                          touch this one window, so this
                                          step is implicit.
  5. Export CSV                          station_chm_values.csv, written
                                          here.

This is mathematically the same computation, restricted to the ~10 m x
10 m neighborhood of each station instead of the whole tile -- there is
no reason to reproject/resample the other 99.9%+ of each multi-hundred-
MB tile that no station falls anywhere near.

If a station's point isn't covered by any downloaded tile (see
01_download_lidar_tiles.py's own coverage report for which ones), its
CHM_height_meter comes out NaN here -- same graceful fallback
merge_station_veg.py already has for a missing/incomplete CHM file. This
can happen even for a station well within the general survey area: WA
DNR's lidar tiles follow each project's own (not perfectly gridded) flight
lines, so a station sitting right at a seam between tiles can fall in a
small real gap between them -- confirmed against the live portal while
writing this script, not just a hypothetical edge case.

Output: station_chm_values.csv (station, CHM_height_meter), written into
this folder -- NOT into output_non-seismic_code/, unlike this script's
own DSM/DTM input: CHM is grouped with GEDI/Sentinel-2 as one of the
per-station vegetation predictors merge_station_veg.py reads back
(CHM_CSV), same as before this was scripted.

Usage
-----
Run 01_download_lidar_tiles.py first, then:

    python 02_process_chm.py
"""

import os
import re
import glob
import numpy as np
import pandas as pd
import rasterio
from rasterio.windows import Window
from pyproj import Transformer

# ═════════════════════════════════════════════════════════════════════════════
# CONFIG
# ═════════════════════════════════════════════════════════════════════════════
STATIONS_CSV = "../../seismic_data/df_station_locations.csv"
RAW_DIR = "../../output_non-seismic_code/CHM/raw"
OUT_CSV = "station_chm_values.csv"

# Matches the QGIS workflow's own downsample target (README.md, step 3).
OUTPUT_RES_M = 10.0

FEET_TO_M = 0.3048   # international foot; matches the manual QGIS step
# ═════════════════════════════════════════════════════════════════════════════


def linear_unit_to_m(crs):
    """Factor to convert one CRS linear unit to meters -- these tiles are
    in US survey feet (WA State Plane), but this stays generic rather
    than hardcoding that."""
    units = crs.linear_units_factor
    if units is None:
        return 1.0
    return units[1]


def discover_tile_pairs(raw_dir):
    """Every (dsm_path, dtm_path) pair found under raw_dir, one per tile,
    grouped by project. Filenames follow
    <project_slug>_<dsm|dtm>_<tile_id>.tif (see 01_download_lidar_tiles.py);
    pairing is done by tile_id within each project, not by list position,
    since a project can have DSM without a matching DTM tile or vice
    versa (partial coverage at a project's edge)."""
    pairs = []
    for dsm_path in sorted(glob.glob(os.path.join(raw_dir, "*", "dsm", "*.tif"))):
        m = re.search(r"_dsm_([^/\\]+)\.tif$", dsm_path, re.IGNORECASE)
        if not m:
            print(f"  [warn] couldn't parse tile id from {dsm_path!r} -- skipping.")
            continue
        tile_id = m.group(1)
        dtm_path = dsm_path.replace(f"{os.sep}dsm{os.sep}", f"{os.sep}dtm{os.sep}") \
                            .replace("_dsm_", "_dtm_")
        if not os.path.isfile(dtm_path):
            print(f"  [warn] {dsm_path!r} has no matching DTM tile ({dtm_path!r}) -- skipping.")
            continue
        pairs.append(dict(project=os.path.basename(os.path.dirname(os.path.dirname(dsm_path))),
                           tile_id=tile_id, dsm_path=dsm_path, dtm_path=dtm_path))
    return pairs


def build_tile_index(pairs):
    """Opens every tile pair once (metadata only) to cache bounds/crs/res,
    and a lon/lat -> tile-CRS Transformer per distinct CRS (tiles across
    different WA DNR projects may not share one)."""
    transformers = {}
    index = []
    for pair in pairs:
        with rasterio.open(pair["dsm_path"]) as src:
            crs_wkt = src.crs.to_wkt()
            if crs_wkt not in transformers:
                transformers[crs_wkt] = Transformer.from_crs(
                    "EPSG:4326", src.crs, always_xy=True
                )
            index.append(dict(
                **pair,
                bounds=src.bounds,
                res=src.res,
                unit_to_m=linear_unit_to_m(src.crs),
                transformer=transformers[crs_wkt],
            ))
    return index


def find_tile_for_station(lon, lat, tile_index):
    """First tile pair (if any) whose bounds contain this station, plus
    how many candidates matched (>1 means overlapping project coverage --
    logged, not treated as an error)."""
    matches = []
    for tile in tile_index:
        x, y = tile["transformer"].transform(lon, lat)
        b = tile["bounds"]
        if b.left <= x <= b.right and b.bottom <= y <= b.top:
            matches.append((tile, x, y))
    return matches


def sample_chm(tile, x, y, output_res_m):
    """Mean (DSM - DTM) * FEET_TO_M over a window centered on (x, y) in
    the tile's own CRS, sized to cover one output_res_m x output_res_m
    cell at the tile's native resolution -- the 'downsample to 10 m via
    average resampling' step, computed only for this one output cell."""
    res_x, res_y = tile["res"]
    unit_to_m = tile["unit_to_m"]
    win_px_x = max(1, round(output_res_m / (res_x * unit_to_m)))
    win_px_y = max(1, round(output_res_m / (res_y * unit_to_m)))

    with rasterio.open(tile["dsm_path"]) as dsm, rasterio.open(tile["dtm_path"]) as dtm:
        row, col = dsm.index(x, y)
        window = Window(
            col - win_px_x // 2, row - win_px_y // 2, win_px_x, win_px_y
        )
        dsm_nodata, dtm_nodata = dsm.nodata, dtm.nodata
        dsm_arr = dsm.read(1, window=window, boundless=True, fill_value=dsm_nodata)
        dtm_arr = dtm.read(1, window=window, boundless=True, fill_value=dtm_nodata)

    valid = np.ones(dsm_arr.shape, dtype=bool)
    if dsm_nodata is not None:
        valid &= dsm_arr != dsm_nodata
    if dtm_nodata is not None:
        valid &= dtm_arr != dtm_nodata
    valid &= np.isfinite(dsm_arr) & np.isfinite(dtm_arr)

    if not valid.any():
        return np.nan
    chm_ft = (dsm_arr[valid] - dtm_arr[valid])
    return float(np.mean(chm_ft)) * FEET_TO_M


def main():
    stations = pd.read_csv(STATIONS_CSV, dtype={"station": str})

    pairs = discover_tile_pairs(RAW_DIR)
    if not pairs:
        raise SystemExit(
            f"No DSM/DTM tile pairs found under {RAW_DIR!r} -- "
            f"run 01_download_lidar_tiles.py first."
        )
    print(f"Found {len(pairs)} DSM/DTM tile pair(s) across "
          f"{len({p['project'] for p in pairs})} project(s). Indexing...")
    tile_index = build_tile_index(pairs)

    rows = []
    n_uncovered, n_overlap = 0, 0
    for _, row in stations.iterrows():
        lon, lat = row["longitude"], row["latitude"]
        matches = find_tile_for_station(lon, lat, tile_index)
        if not matches:
            rows.append(dict(station=row["station"], CHM_height_meter=np.nan))
            n_uncovered += 1
            continue
        if len(matches) > 1:
            n_overlap += 1
        tile, x, y = matches[0]
        chm = sample_chm(tile, x, y, OUTPUT_RES_M)
        rows.append(dict(station=row["station"], CHM_height_meter=chm))

    out = pd.DataFrame(rows)
    out.to_csv(OUT_CSV, index=False)

    n_valid = out["CHM_height_meter"].notna().sum()
    print(f"\nSaved {len(out)} stations -> {OUT_CSV} "
          f"({n_valid} with a value, {n_uncovered} with no tile coverage "
          f"-> NaN).")
    if n_overlap:
        print(f"{n_overlap} station(s) were covered by more than one "
              f"downloaded project -- the first match (by discovery "
              f"order) was used for each.")


if __name__ == "__main__":
    main()
