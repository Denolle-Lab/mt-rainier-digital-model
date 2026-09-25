"""S19: canopy and soil layers of the canopy-storage project -> data/processed/surface_canopy.zarr.

Reads configs/canopy_products.yaml (files, units, source keys). The layers share the 100 m surface grid and
are kept in their own store, not merged into model.zarr; S11 appends them (and the soil-map image) to the 3D
viewer bundle when the store exists. A layer whose delivered file is missing is skipped with a warning; any
other error stops the stage.

Usage: pixi run python scripts/19_canopy_layers.py
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import xarray as xr
import yaml

from rainier3d.config.domain import REPO, load_domain
from rainier3d.io.store import write
from rainier3d.surface.canopy import layer, source_path


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    dom = load_domain()
    cfg = yaml.safe_load((REPO / "configs" / "canopy_products.yaml").read_text())
    root = Path(cfg["root"]).expanduser()
    out = {}
    for spec in cfg["layers"]:
        if not source_path(spec, root).exists():  # a missing delivery skips the layer, never fills it
            logging.warning("%s skipped: %s not found", spec["name"], source_path(spec, root))
            continue
        out[spec["name"]] = layer(dom, spec, root)
    ds = xr.Dataset(out)
    ds.attrs = {"crs": dom.crs, "vertical_datum": dom.vertical_datum, "domain": dom.name}
    p = write(ds, dom.path("processed") / "surface_canopy.zarr")
    for k, v in ds.data_vars.items():
        a = v.values.astype(float)
        ok = np.isfinite(a)
        logging.info(
            "%-24s %5.1f %% valid  p5/p50/p95 = %s %s",
            k,
            100 * ok.mean(),
            np.round(np.percentile(a[ok], [5, 50, 95]), 2) if ok.any() else "-",
            v.attrs["units"],
        )
    logging.info("wrote %s", p)


if __name__ == "__main__":
    main()
