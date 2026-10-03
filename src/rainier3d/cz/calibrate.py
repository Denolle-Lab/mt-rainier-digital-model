"""Calibration of the critical-zone medium against observed dispersion (build step 4 of
docs/critical_zone.md).

Observed Rayleigh phase velocities come as a table with one row per site and frequency: ``site``,
``frequency_hz``, ``phase_velocity_ms`` and ``sigma_ms`` (for example from noisepy or codameter
cross-correlations of the node array or the DAS). A parameter of the medium is searched on a grid: for each
value the model column is rebuilt and the chi-square misfit to the observations returned with its minimum.
``fit_weathered_base`` does this for the depth of the weathered layer at a site; the placeholders of
configs/cz.yaml (stress exponent, Brie exponent) are searched the same way once dv/v observations are added.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from rainier3d.cz import synthetics as SY

COLUMNS = ("site", "frequency_hz", "phase_velocity_ms", "sigma_ms")


def read_observed(path) -> pd.DataFrame:
    d = pd.read_csv(path)
    missing = set(COLUMNS) - set(d.columns)
    if missing:
        raise ValueError(f"{path}: missing columns {sorted(missing)}")
    return d[list(COLUMNS)].sort_values(["site", "frequency_hz"]).reset_index(drop=True)


def fit(build, obs: pd.DataFrame, values) -> dict:
    """Grid search: ``build(value)`` returns a layered column (rainier3d.cz.synthetics.stack); ``obs`` holds
    one site's rows."""
    f = obs.frequency_hz.values
    c_obs, sig = obs.phase_velocity_ms.values, obs.sigma_ms.values
    chi2 = np.full(len(values), np.nan)
    for i, v in enumerate(values):
        c = SY.phase_velocity(build(v), f)
        ok = np.isfinite(c)
        if ok.any():
            chi2[i] = float(np.sum(((c[ok] - c_obs[ok]) / sig[ok]) ** 2) / ok.sum())
    k = int(np.nanargmin(chi2))
    return {"values": np.asarray(values, float), "chi2": chi2, "best": float(values[k]), "chi2_min": chi2[k]}


def fit_weathered_base(m, site: dict, obs: pd.DataFrame, depths_m) -> dict:
    """The weathered-layer depth at a site (rainier3d.cz.sites.model ``m``): the prior is replaced by each
    trial depth, with the young-surface and forest factors switched off."""
    from rainier3d.cz.sites import site_column

    def build(d):
        return site_column(
            m, site, override={"weathered_prior": float(d), "unit_factor": {}, "canopy_height": 0.0}
        )[0]

    return fit(build, obs, depths_m)
