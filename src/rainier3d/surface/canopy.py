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

from rainier3d.config.domain import REPO, Domain
from rainier3d.surface.layers import _da, warp

# where S28 (the vendored canopy-storage pipeline) writes its products
PIPELINE_OUT = REPO / "data" / "raw" / "canopy_storage" / "output_non-seismic_code"


def source_path(spec: dict, root: Path) -> Path:
    """The file of a layer or image spec: the S28 pipeline product (``pipeline_file``) when it exists,
    else the delivered file, with ~/Downloads replaced by the configured root."""
    if spec.get("pipeline_file"):
        rel = Path(spec["pipeline_file"])
        if rel.is_absolute() or ".." in rel.parts:
            raise ValueError(f"pipeline_file must be relative to {PIPELINE_OUT}: {rel}")
        if (PIPELINE_OUT / rel).exists():
            return PIPELINE_OUT / rel
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
