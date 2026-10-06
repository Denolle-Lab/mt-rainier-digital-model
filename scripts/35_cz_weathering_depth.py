"""S35: weathering-depth estimators scored against the borehole bedrock picks ->
outputs/cz/weathering_depth.json. Build step 2 of docs/critical_zone.md.

Each estimator predicts the depth to bedrock at the bedrock picks of the Washington Geological Survey
boreholes (S31, data/processed/wells.csv); fitted estimators are scored by leave-one-out. Estimators: a
constant (the median of the other picks), SoilGrids 2017, SOLUS100 soil thickness, the curvature regression
of Flinchum et al. (2025), z = a kmin^2 + b kmin + c kmax^2 + d kmax + e, refitted here on principal
curvatures of the 100 m DEM smoothed at several scales, and a linear regression on the terrain geometry of
S30. The topographic-stress and drainage models are not implemented yet.

Usage: pixi run s35
"""

from __future__ import annotations

import json
import logging

import numpy as np
import pandas as pd
import xarray as xr
from scipy.ndimage import gaussian_filter

from rainier3d.config.domain import load_domain

log = logging.getLogger("s35")
SMOOTHING_CELLS = (1, 3, 5)
TERRAIN = ("surface_slope", "local_relief", "valley_depth")


def principal_curvatures(z: np.ndarray, dx: float) -> tuple[np.ndarray, np.ndarray]:
    zy, zx = np.gradient(z, dx)
    zyy, zyx = np.gradient(zy, dx)
    _, zxx = np.gradient(zx, dx)
    mean = 0.5 * (zxx + zyy)
    dev = np.sqrt(((zxx - zyy) / 2) ** 2 + zyx**2)
    return mean - dev, mean + dev


def loo(X: np.ndarray, y: np.ndarray) -> np.ndarray:
    pred = np.empty(len(y))
    for i in range(len(y)):
        m = np.arange(len(y)) != i
        pred[i] = X[i] @ np.linalg.lstsq(X[m], y[m], rcond=None)[0]
    return pred


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    dom = load_domain()
    w = pd.read_csv(dom.path("processed") / "wells.csv")
    b = w[w.depth_to_bedrock_m.notna()]
    obs = b.depth_to_bedrock_m.values
    s = xr.open_datatree(dom.path("processed") / "model.zarr", engine="zarr", consolidated=False)["surface"]
    s = s.to_dataset()
    tg = xr.open_zarr(dom.path("processed") / "terrain_geometry.zarr", consolidated=False)
    px, py = xr.DataArray(b.x.values, dims="w"), xr.DataArray(b.y.values, dims="w")

    def at(da):
        return da.sel(x=px, y=py, method="nearest").values

    one = np.ones(len(obs))
    pred = {
        "constant (median of the others)": np.array([np.median(np.delete(obs, i)) for i in range(len(obs))])
    }
    pred["SoilGrids 2017"] = at(s.depth_to_bedrock)
    pred["SOLUS100 soil thickness"] = at(s.soil_thickness)
    for k in SMOOTHING_CELLS:
        z = gaussian_filter(s.elevation.values.astype(float), k)
        kmin, kmax = (
            at(xr.DataArray(v, coords=s.elevation.coords)) for v in principal_curvatures(z, dom.surface_res_m)
        )
        X = np.column_stack([kmin**2, kmin, kmax**2, kmax, one])
        pred[f"curvature regression, {k * dom.surface_res_m:.0f} m smoothing"] = loo(X, obs)
    pred["terrain regression (" + ", ".join(TERRAIN) + ")"] = loo(
        np.column_stack([*(at(tg[v]) for v in TERRAIN), one]), obs
    )
    scores = {}
    for name, p in pred.items():
        ok = np.isfinite(p)
        e = p[ok] - obs[ok]
        scores[name] = {
            "n": int(ok.sum()),
            "mean_abs_error_m": round(float(np.mean(np.abs(e))), 1),
            "median_bias_m": round(float(np.median(e)), 1),
            "spearman_r": round(float(pd.Series(p[ok]).corr(pd.Series(obs[ok]), method="spearman")), 2),
        }
    out = {
        "picks": int(len(obs)),
        "obs_median_m": round(float(np.median(obs)), 1),
        "obs_range_m": [round(float(obs.min()), 1), round(float(obs.max()), 1)],
        "pick_elevation_m": [round(float(v)) for v in np.percentile(at(s.elevation), [0, 50, 100])],
        "scores": scores,
    }
    p = dom.path("outputs") / "cz" / "weathering_depth.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, indent=1))
    log.info("%s", json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
