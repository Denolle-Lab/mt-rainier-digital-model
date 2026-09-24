"""Calibrate a depth-dependent Vs scale factor on PNSN S-P times.

The fused Vs inherits its long wavelengths from the regional model, which predicts S-P times that are too long
at Rainier (outputs/vs_calibration/attribution.txt). The correction is a smooth factor of depth below ground,

    Vs_regional'(d) = Vs_regional(d) * exp(m(d)),   m piecewise linear on KNOTS_M, constant beyond the ends,

applied to the regional Vs before fusion (S5). A factor that depends on depth only passes through the
horizontal low-pass unchanged, so the fused model keeps its lateral pattern; Vp is not touched, so Vp/Vs
drops where Vs rises. For the inversion the factor is applied to the fused Vs grid of S6 directly, with the
same taper as the fusion (none above geology_only_depth_m, full from taper_depth_m), which is what S5 then
produces; the final S5 + S6 rerun checks that.

Data: S-P residuals (origin time cancels) with P from the fused Vp, fixed PNSN/ComCat hypocentres.
Objective: sum r^2 + lam_s |D2 m|^2 + lam_d |m|^2, Gauss-Newton with finite-difference Jacobians.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

KNOTS_M = np.array([0.0, 1000, 2000, 4000, 7000, 11000, 16000, 25000])


def log_factor(depth_m: np.ndarray, m: np.ndarray, knots: np.ndarray = KNOTS_M) -> np.ndarray:
    return np.interp(np.maximum(depth_m, 0.0), knots, m)


def fusion_taper(depth_m: np.ndarray, d0: float, d1: float) -> np.ndarray:
    return np.clip((np.asarray(depth_m) - d0) / (d1 - d0), 0.0, 1.0)


def depth_below_ground(tree, xs, ys, zs) -> np.ndarray:
    """(nz, nx, ny) depth below the model ground surface on the S6 grid (negative in air)."""
    s = tree["surface"].to_dataset()
    surf = s["elevation"].sel(x=xs, y=ys, method="nearest").transpose("x", "y").values
    return surf[None, :, :] - zs[:, None, None]


def second_difference(n: int) -> np.ndarray:
    d = np.zeros((n - 2, n))
    for i in range(n - 2):
        d[i, i : i + 3] = (1.0, -2.0, 1.0)
    return d


class SPProblem:
    """S-P residuals as a function of m, for one set of stations/events and a base fused Vs grid."""

    def __init__(self, vs_fused, depth, taper, pairs: pd.DataFrame, tt_fn):
        self.vs, self.lf_depth, self.taper, self.pairs, self.tt_fn = vs_fused, depth, taper, pairs, tt_fn
        self.d_obs = (pairs.ts_obs - pairs.tp_obs).values
        self.tp = pairs.tp3d.values
        self.si, self.ei = pairs.si.values, pairs.ei.values

    def predict_ts(self, m: np.ndarray) -> np.ndarray:
        vel = self.vs * np.exp(self.taper * log_factor(self.lf_depth, m))
        T = self.tt_fn(vel)
        return T[self.si, self.ei]

    def residual(self, ts: np.ndarray) -> np.ndarray:
        return self.d_obs - (ts - self.tp)

    def jacobian(self, m: np.ndarray, ts0: np.ndarray, h: float = 0.03) -> np.ndarray:
        J = np.zeros((ts0.size, m.size))
        for k in range(m.size):
            mk = m.copy()
            mk[k] += h
            J[:, k] = (self.predict_ts(mk) - ts0) / h  # d ts / d m_k (residual derivative is -J)
            log.info("jacobian column %d/%d", k + 1, m.size)
        return J


def gn_step(J, r, m, train, lam_s: float, lam_d: float) -> np.ndarray:
    """One regularised Gauss-Newton update on the rows in ``train`` (r = d_obs - pred, d pred/dm = J)."""
    D = second_difference(m.size)
    A = J[train].T @ J[train] + lam_s * D.T @ D + lam_d * np.eye(m.size)
    b = J[train].T @ r[train] - lam_s * D.T @ D @ m - lam_d * m
    return m + np.linalg.solve(A, b)


def stats(r: np.ndarray, events: np.ndarray) -> dict:
    s = pd.Series(r)
    dm = s - s.groupby(events).transform("mean")
    return {
        "mean_s": float(s.mean()),
        "rms_s": float(np.sqrt((s**2).mean())),
        "rms_demeaned_s": float(np.sqrt((dm**2).mean())),
        "n": int(s.size),
    }
