"""
MRMS Time Series Extractor
==========================
Extracts time series at station locations from MRMS GRIB2 files.
Processes BOTH products this pipeline needs (reflectivity + hourly QPE) in
one run -- see PRODUCTS below -- so a single `python
extract_mrms_timeseries.py` always leaves both timeseries CSVs available,
matching download_mrms.sh's own default of downloading both.

Command to download the data:
aws s3 cp s3://noaa-mrms-pds/CONUS/MultiSensor_QPE_01H_Pass2_00.00/20250731/ ./20250731/ --recursive --no-sign-request
OR run bash download_mrms.sh 20250710 20250801   (downloads both products)

Works with single or multiple day folders:
    data_dir/
        20240701/
            MRMS_*.grib2.gz
        20240702/
            ...

Output:
    wide-format CSV: rows = timestamps, columns = zero-padded station IDs

Note on ECCODES warnings:
    Reflectivity files have sub-minute timestamps (e.g. 00:02:42) which
    the GRIB2 standard does not support. ECCODES prints harmless warnings
    about truncating seconds. Timestamps are parsed from the filename, so
    no data is lost. Suppress warnings by running:
        ECCODES_WARNINGS=0 python extract_mrms_timeseries.py
"""

import os
import sys
import glob
import gzip
import shutil
import tempfile
import re
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import cfgrib

# ─────────────────────────────────────────────
# CONFIGURATION — edit these
# ─────────────────────────────────────────────

# Every product to extract in one run. DATA_DIR (raw downloaded GRIB2
# files, intermediate) must match the LOCAL_DIR download_mrms.sh writes
# that product into. OUTPUT (the final extracted timeseries) goes to
# ../../output_non-seismic_code/ -- mirroring result_non-seismic_code/'s
# flat layout -- with a filename matching what the seismic_code pipeline
# reads it back as (e.g. 07_storage_capacity_sup.py, 08_storage_capacity.py).
PRODUCTS = {
    "REFLECTIVITY": dict(
        DATA_DIR="../../output_non-seismic_code/MRMS/MergedReflectivityQComposite",
        OUTPUT="../../output_non-seismic_code/timeseries_reflectivity.csv",
        VALID_MIN=-10,   # dBZ
        VALID_MAX=80,    # dBZ
    ),
    "QPE": dict(
        DATA_DIR="../../output_non-seismic_code/MRMS/MultiSensor_QPE_01H_Pass2",
        OUTPUT="../../output_non-seismic_code/timeseries_MultiSensor_QPE_01H_Pass2.csv",
        VALID_MIN=0,     # mm
        VALID_MAX=10,    # mm
    ),
}

STATIONS_CSV = "../../seismic_data/df_station_locations.csv"

# ─────────────────────────────────────────────


def parse_timestamp_from_filename(fname):
    """
    Parse timestamp directly from filename — not from GRIB2 metadata.
    This correctly captures seconds, e.g. 000242 -> 00:02:42,
    which GRIB2/ECCODES would otherwise truncate.
    """
    match = re.search(r"(\d{8})-(\d{6})", fname)
    if match:
        return datetime.strptime(match.group(1) + match.group(2), "%Y%m%d%H%M%S")
    return None


def load_grib2_gz(filepath):
    """Decompress to temp file, eagerly load into memory, then delete temp."""
    with tempfile.NamedTemporaryFile(suffix=".grib2", delete=False) as tmp:
        tmp_path = tmp.name
        with gzip.open(filepath, "rb") as gz:
            shutil.copyfileobj(gz, tmp)
    try:
        ds = cfgrib.open_dataset(tmp_path, indexpath=None)
        ds.load()
    finally:
        os.unlink(tmp_path)
    return ds


def build_station_indices(ds, stations_df):
    """
    Compute nearest grid (row, col) index for each station.
    Called ONCE on the first file — the MRMS grid is identical across all files.
    """
    lats = ds.latitude.values
    lons = ds.longitude.values

    if lats.ndim == 1 and lons.ndim == 1:
        lons_2d, lats_2d = np.meshgrid(lons, lats)
    else:
        lats_2d, lons_2d = lats, lons

    indices = []
    for _, row in stations_df.iterrows():
        slat = row["latitude"]
        slon = row["longitude"] % 360   # MRMS uses 0-360

        dist = np.sqrt((lats_2d - slat) ** 2 + (lons_2d - slon) ** 2)
        idx  = np.unravel_index(np.argmin(dist), dist.shape)
        indices.append((row["station"], idx[0], idx[1]))

    return indices


def extract_with_indices(ds, station_indices, valid_min, valid_max):
    """Direct array lookup per station using pre-computed grid indices."""
    var_name = list(ds.data_vars)[0]
    data = ds[var_name].values

    if data.ndim == 1:
        n_lat = ds.latitude.values.shape[0]
        n_lon = ds.longitude.values.shape[0]
        data = data.reshape(n_lat, n_lon)

    results = {}
    for station_id, row_idx, col_idx in station_indices:
        value = data[row_idx, col_idx]
        if value < valid_min or value > valid_max:
            value = np.nan
        results[station_id] = value

    return results


def extract_one_product(product_name, data_dir, output, valid_min, valid_max, stations):
    """Extract one product's GRIB2 files under data_dir into a wide-format
    timeseries CSV at output. Returns True if a file was written."""
    print(f"\n=== {product_name} ===")
    print(f"Data dir: {data_dir}")
    print(f"Output  : {output}")

    files = sorted(glob.glob(os.path.join(data_dir, "**", "*.grib2.gz")))
    print(f"Found {len(files)} GRIB2 files")

    if not files:
        print(f"No files found under {data_dir} -- skipping {product_name}. "
              f"(Run download_mrms.sh first to fetch this product.)")
        return False

    station_indices = None
    rows = {}

    for i, fpath in enumerate(files):
        fname = Path(fpath).name
        timestamp = parse_timestamp_from_filename(fname)
        if timestamp is None:
            print(f"  [SKIP] Cannot parse timestamp: {fname}")
            continue

        print(f"  [{i+1}/{len(files)}] {timestamp}  {fname}")

        try:
            ds = load_grib2_gz(fpath)

            if station_indices is None:
                print("  Building station grid indices (once)...")
                station_indices = build_station_indices(ds, stations)
                print(f"  Done — {len(station_indices)} stations mapped to grid cells")

            rows[timestamp] = extract_with_indices(ds, station_indices, valid_min, valid_max)
            ds.close()

        except Exception as e:
            print(f"    WARNING: skipped {fname}: {e}")

    if not rows:
        print(f"No data extracted for {product_name}.")
        return False

    df = pd.DataFrame.from_dict(rows, orient="index")
    df.index.name = "timestamp"
    df = df.sort_index()
    df.columns = [f"{int(c):03d}" for c in df.columns]
    os.makedirs(os.path.dirname(output) or ".", exist_ok=True)
    df.to_csv(output)

    print(f"Saved: {output}  ({len(df)} rows x {len(df.columns)} stations)")
    print(f"Time range: {df.index.min()}  →  {df.index.max()}")
    print(f"Missing values: {df.isna().sum().sum()}")
    return True


def main():
    stations = pd.read_csv(STATIONS_CSV)
    print(f"Loaded {len(stations)} stations")

    for product_name, cfg in PRODUCTS.items():
        extract_one_product(product_name, cfg["DATA_DIR"], cfg["OUTPUT"],
                             cfg["VALID_MIN"], cfg["VALID_MAX"], stations)


if __name__ == "__main__":
    main()
