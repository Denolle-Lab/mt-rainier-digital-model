"""S28: run the vendored canopy-storage pipeline (third_party/canopy-storage_seismic/non-seismic_code).

The upstream scripts are run unmodified, each from its own folder, in a working copy under
data/raw/canopy_storage/non-seismic_code/; their relative output paths land in
data/raw/canopy_storage/output_non-seismic_code/. S19 reads the gridded outputs from there when they exist
(`pipeline_file` in configs/canopy_products.yaml) and falls back to the delivered files otherwise.

Steps (docs/canopy_pipeline.md lists services, parameters and credentials):
  gedi_l3        GEDI/01_download_gedi_l3_height.py   earthaccess, NASA Earthdata login (~/.netrc or env)
  gedi_l2b       GEDI/01_download_gedi_l2b_pai.py     earthaccess, NASA Earthdata login; large granules
  gedi_l2b_grid  GEDI/02_grid_gedi_l2b_pai.py         local
  s2_lai         Sentinel2/01_download_lai.py         Sentinel Hub on the Copernicus Data Space;
                                                      SH_CLIENT_ID and SH_CLIENT_SECRET in the environment

A step whose product already exists is skipped (the cache rule of data/raw/); --force reruns it. A step
whose credentials are missing is skipped with a message. The station-sampling scripts (GEDI/04, Sentinel2/02,
MRMS, merge_station_veg.py) need a station CSV and are not run here.

Usage: pixi run -e canopy canopy [-- --steps gedi_l3,s2_lai] [--force]
"""

from __future__ import annotations

import argparse
import logging
import netrc
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
VENDOR = REPO / "third_party" / "canopy-storage_seismic" / "non-seismic_code"
WORK = REPO / "data" / "raw" / "canopy_storage"
OUT = WORK / "output_non-seismic_code"

# name: (folder, script, product that marks the step done, credential)
STEPS = {
    "gedi_l3": (
        "GEDI",
        "01_download_gedi_l3_height.py",
        OUT / "GEDI/gedi_l3/cropped/L3_rh100_mean.tif",
        "earthdata",
    ),
    "gedi_l2b": (
        "GEDI",
        "01_download_gedi_l2b_pai.py",
        OUT / "GEDI/gedi_l2b_pai/footprints/footprints_qcfiltered.csv",
        "earthdata",
    ),
    "gedi_l2b_grid": (
        "GEDI",
        "02_grid_gedi_l2b_pai.py",
        OUT / "GEDI/gedi_l2b_pai/gridded/L2B_PAI_max.tif",
        None,
    ),
    "s2_lai": ("Sentinel2", "01_download_lai.py", OUT / "Sentinel2/lai_mosaic_pnw.tif", "sentinelhub"),
}


def has_credentials(kind: str | None) -> bool:
    if kind is None:
        return True
    if kind == "earthdata":
        if os.getenv("EARTHDATA_USERNAME") and os.getenv("EARTHDATA_PASSWORD"):
            return True
        try:
            return netrc.netrc().authenticators("urs.earthdata.nasa.gov") is not None
        except (FileNotFoundError, netrc.NetrcParseError):
            return False
    if kind == "sentinelhub":
        return bool(os.getenv("SH_CLIENT_ID") and os.getenv("SH_CLIENT_SECRET"))
    raise ValueError(kind)


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--steps", default=",".join(STEPS), help="comma-separated subset of " + ", ".join(STEPS))
    ap.add_argument("--force", action="store_true", help="rerun steps whose product exists")
    a = ap.parse_args()
    steps = [s.strip() for s in a.steps.split(",") if s.strip()]
    unknown = set(steps) - set(STEPS)
    if unknown:
        raise SystemExit(f"unknown steps: {sorted(unknown)}")

    # a fresh copy of the unmodified upstream code; outputs under OUT are kept between runs
    code = WORK / "non-seismic_code"
    if code.exists():
        shutil.rmtree(code)
    shutil.copytree(VENDOR, code)

    failed = []
    for name in steps:
        folder, script, product, cred = STEPS[name]
        if product.exists() and not a.force:
            logging.info("%s: %s exists, skipped", name, product.relative_to(REPO))
            continue
        if not has_credentials(cred):
            logging.warning("%s: no %s credentials, skipped (see docs/canopy_pipeline.md)", name, cred)
            continue
        logging.info("%s: running %s/%s", name, folder, script)
        r = subprocess.run(
            [sys.executable, script], cwd=code / folder, env={**os.environ, "MPLBACKEND": "Agg"}
        )
        if r.returncode:
            failed.append(name)
            logging.error("%s: exit code %d", name, r.returncode)
        elif product.exists():
            logging.info("%s: wrote %s", name, product.relative_to(REPO))
    if failed:
        raise SystemExit(f"failed steps: {', '.join(failed)}")


if __name__ == "__main__":
    main()
