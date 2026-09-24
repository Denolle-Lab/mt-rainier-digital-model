"""Glacier ice thickness.

Default: IceBoost v2 per-glacier grids (OGGM data server) for the RGI 6.0 glaciers in the domain,
checked against the GlaThiDa survey summaries (Driedger & Kennard 1986, 1981 GPR). Farinotti et al.
2019 (ETH Research Collection) blocks scripted downloads; Millan et al. 2022 not tried yet.
Fallback: perfect plasticity, H = tau / (rho_i g sin(alpha)), slope smoothed over ~1 km, floored,
H capped, applied where the mapped surface unit is ice.
"""

from __future__ import annotations

import numpy as np
import xarray as xr
from scipy.ndimage import uniform_filter

from rainier3d.io.store import provenance


def perfect_plasticity_thickness(
    dem: xr.DataArray,
    ice_mask: xr.DataArray,
    res_m: float,
    tau_pa: float,
    rho_kgm3: float,
    slope_smoothing_m: float,
    min_slope_deg: float,
    max_thickness_m: float,
) -> xr.DataArray:
    n = max(1, int(round(slope_smoothing_m / res_m)))
    z = uniform_filter(dem.values, size=n, mode="nearest")
    gy, gx = np.gradient(z, res_m)
    alpha = np.maximum(np.arctan(np.hypot(gx, gy)), np.deg2rad(min_slope_deg))
    h = np.minimum(tau_pa / (rho_kgm3 * 9.81 * np.sin(alpha)), max_thickness_m)
    h = np.where(ice_mask.values, h, 0.0)
    da = xr.DataArray(
        h,
        coords=dem.coords,
        dims=dem.dims,
        name="ice_thickness",
        attrs={"units": "m", "long_name": "glacier ice thickness (M1 perfect-plasticity placeholder)"},
    )
    return provenance(da, ["dnr_gems_100k", "m1_placeholder"], "ice_thickness", res_m)


def iceboost_thickness(dom, tif_dir, glacier_csv) -> tuple[xr.DataArray, xr.DataArray]:
    """IceBoost v2 per-glacier thickness GeoTIFFs (band 1 thickness, band 2 its error, m), area-averaged
    onto the surface grid and summed over glaciers, each rescaled to the volume IceBoost reports for it.
    Glaciers: RGI 6.0 with centroid in the domain (glacier_csv). Returns (thickness, error), 0 off-glacier."""
    import pandas as pd
    import rioxarray  # noqa: F401
    from affine import Affine
    from rasterio.enums import Resampling

    r = dom.surface_res_m
    x0, y0, x1, y1 = dom.bounds
    shape, tr = (int((y1 - y0) / r), int((x1 - x0) / r)), Affine(r, 0, x0, 0, -r, y1)
    h = np.zeros(shape)
    err2 = np.zeros(shape)
    ids = pd.read_csv(glacier_csv)["RGIId"]
    for gid in ids:
        f = tif_dir / f"{gid}.tif"
        if not f.exists():
            continue
        d = xr.open_dataarray(f, engine="rasterio").sel(band=[1, 2])
        # ice-free = 0 before averaging, so partly covered cells are diluted, not filled
        d = d.fillna(0.0).rio.write_nodata(None, encoded=False)
        g = d.rio.reproject(dom.crs, shape=shape, transform=tr, resampling=Resampling.average)
        hi = np.nan_to_num(g.sel(band=1).values)
        # IceBoost's own volume is computed inside the RGI outline; rescale so the gridded glacier matches it
        v_grid = hi.sum() * r * r / 1e9
        if v_grid > 0:
            hi *= float(d.attrs["volume"]) / v_grid
        h += hi
        err2 += np.nan_to_num(g.sel(band=2).values) ** 2
    err = np.sqrt(err2)
    h, err = h[::-1], err[::-1]  # grid rows south -> north like dom.y
    coords = {"y": dom.y, "x": dom.x}
    th = xr.DataArray(
        h,
        coords=coords,
        dims=("y", "x"),
        name="ice_thickness",
        attrs={"units": "m", "long_name": "glacier ice thickness (IceBoost v2, RGI 6.0 glaciers)"},
    )
    er = xr.DataArray(
        err,
        coords=coords,
        dims=("y", "x"),
        name="ice_thickness_error",
        attrs={"units": "m", "long_name": "IceBoost v2 thickness error"},
    )
    return (
        provenance(th, ["iceboost_v2", "rgi60"], "ice_thickness", r, "ice_thickness_error"),
        provenance(er, ["iceboost_v2"], "ice_thickness_error", r),
    )


def glathida_check(tif_dir, glacier_csv, glathida_rows: list[dict]) -> list[dict]:
    """Per-glacier mean/max thickness from the native IceBoost grids vs GlaThiDa survey summaries."""
    import pandas as pd

    g = pd.read_csv(glacier_csv)
    out = []
    for r in glathida_rows:
        key = r["GLACIER_NAME"].split()[0].title()
        m = g[g.Name.fillna("").str.startswith(key)]
        if m.empty:
            continue
        gid = m.sort_values("Area").RGIId.iloc[-1]
        d = xr.open_dataarray(tif_dir / f"{gid}.tif", engine="rasterio").sel(band=1).values
        d = d[np.isfinite(d) & (d > 0)]
        out.append(
            {
                "glacier": r["GLACIER_NAME"],
                "rgi": gid,
                "survey_year": r["SURVEY_DATE"][:4],
                "glathida_mean_m": float(r["MEAN_THICKNESS"]),
                "glathida_max_m": float(r["MAXIMUM_THICKNESS"]),
                "iceboost_mean_m": round(float(d.mean()), 1),
                "iceboost_max_m": round(float(d.max()), 1),
            }
        )
    return out
