"""Model -> PyVista/VTK objects and files (VTI per level, VTS for the surface)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pyvista as pv
import xarray as xr

LEVEL_VARS = ("unit", "alteration", "vp", "vs", "rho", "qp", "qs", "vp_geology", "vp_regional")


def level_grid(ds: xr.Dataset, variables=LEVEL_VARS) -> pv.ImageData:
    """Cell-data ImageData; the dataset is (z top-down, y, x) at cell centres."""
    dx, dz = float(ds.attrs["dx"]), float(ds.attrs["dz"])
    nz, ny, nx = ds["unit"].shape
    g = pv.ImageData(
        dimensions=(nx + 1, ny + 1, nz + 1),
        spacing=(dx, dx, dz),
        origin=(float(ds.x[0]) - dx / 2, float(ds.y[0]) - dx / 2, float(ds.z[-1]) - dz / 2),
    )
    for v in variables:
        if v in ds:
            a = ds[v].values[::-1]  # bottom-up for VTK
            g.cell_data[v] = np.ascontiguousarray(a).ravel(order="C").astype(np.float32)
    return g


def surface_grid(surf: xr.Dataset, stride: int = 1) -> pv.StructuredGrid:
    s = surf.isel(x=slice(None, None, stride), y=slice(None, None, stride))
    xx, yy = np.meshgrid(s.x.values, s.y.values)
    g = pv.StructuredGrid(xx, yy, s["elevation"].values)
    for v in ("elevation", "surface_unit", "ice_thickness"):
        g.point_data[v] = s[v].values.ravel(order="F").astype(np.float32)
    return g


def write_all(tree: xr.DataTree, outdir: Path) -> list[Path]:
    outdir.mkdir(parents=True, exist_ok=True)
    paths = []
    for lev in ("L1", "L2", "L3"):
        p = outdir / f"rainier3d_{lev}.vti"
        level_grid(tree[lev].to_dataset()).save(p)
        paths.append(p)
    p = outdir / "rainier3d_surface.vts"
    surface_grid(tree["surface"].to_dataset()).save(p)
    return paths + [p]
