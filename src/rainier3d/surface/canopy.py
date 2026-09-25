"""Canopy and soil layers from the canopy-storage project (koepflma/canopy-storage_seismic), on the surface
grid.

Inputs are the gridded products of that project's pipeline (configs/canopy_products.yaml gives each file,
its source and how it was made). Continuous layers are block-averaged onto the 100 m surface grid; GEDI
grids (1 km) are bilinearly resampled, since each 1 km cell is an estimate for the cell, not a sum. The soil
map is an RGB rendering, carried as an image for display only until its legend is documented."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import xarray as xr
from rasterio.enums import Resampling

from rainier3d.config.domain import Domain
from rainier3d.surface.layers import _da, warp


def source_path(spec: dict, root: Path) -> Path:
    """The delivered file of a layer or image spec, with ~/Downloads replaced by the configured root."""
    return Path(spec["file"].replace("~/Downloads", str(root))).expanduser()


def layer(dom: Domain, spec: dict, root: Path) -> xr.DataArray:
    """One product from its spec: file, resampling, valid range, units, long name, source key, native res."""
    src = str(source_path(spec, root))
    rs = {"average": Resampling.average, "bilinear": Resampling.bilinear, "mode": Resampling.mode}[
        spec["resampling"]
    ]
    a = warp(dom, src, rs)
    lo, hi = spec.get("valid_range", [-np.inf, np.inf])
    a = np.where((a >= lo) & (a <= hi), a * spec.get("scale", 1.0), np.nan).astype("float32")
    return _da(
        dom,
        a,
        spec["name"],
        {"units": spec["units"], "long_name": spec["long_name"]},
        [spec["source"]],
        spec["name"],
        spec["native_res_m"],
    )
