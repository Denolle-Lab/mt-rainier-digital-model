"""DEM on the surface grid.

M1 source: USGS 3DEP through py3dep at 30 m, block-averaged onto the surface grid. The fetch is
cached as a GeoTIFF in ``data/raw/dem``. M2 swaps in 3DEP 1 m and the MORA 2021 SfM DSM.
"""

from __future__ import annotations

import logging

import numpy as np
import rioxarray  # noqa: F401  (registers .rio)
import xarray as xr
from rasterio.enums import Resampling

from rainier3d.config.domain import Domain
from rainier3d.io.store import provenance

log = logging.getLogger(__name__)


def fetch_3dep(dom: Domain, res_m: int = 30) -> xr.DataArray:
    cache = dom.path("raw") / "dem" / f"3dep_{res_m}m_{dom.name}.tif"
    if cache.exists():
        return xr.open_dataarray(cache, engine="rasterio").squeeze("band", drop=True)
    import py3dep

    lon0, lat0, lon1, lat1 = dom.bbox_4326
    pad = 0.02
    log.info("fetching 3DEP %d m for %s", res_m, dom.bbox_4326)
    # py3dep's ``crs`` is the CRS of the input box, not of the output; reprojection happens in dem_on_grid
    dem = py3dep.get_dem((lon0 - pad, lat0 - pad, lon1 + pad, lat1 + pad), resolution=res_m, crs=4326)
    cache.parent.mkdir(parents=True, exist_ok=True)
    dem.rio.to_raster(cache)
    return dem


def dem_on_grid(dom: Domain, src: xr.DataArray) -> xr.DataArray:
    """Average ``src`` onto the domain surface grid (cell centres dom.x, dom.y)."""
    r = dom.surface_res_m
    x0, y0, x1, y1 = dom.bounds
    nx, ny = int((x1 - x0) / r), int((y1 - y0) / r)
    from affine import Affine

    out = src.rio.reproject(
        dom.crs,
        shape=(ny, nx),
        transform=Affine(r, 0, x0, 0, -r, y1),
        resampling=Resampling.average,
    )
    out = out.where(out > -1000)
    out = out.assign_coords(x=dom.x, y=dom.y[::-1]).sortby("y")
    if np.isnan(out).any():
        raise ValueError(f"DEM has {int(np.isnan(out).sum())} empty cells on the domain grid")
    out.name = "elevation"
    out.attrs = {"units": "m", "long_name": "ground-surface elevation (NAVD88)"}
    return provenance(out, ["usgs_3dep"], "elevation", r)
