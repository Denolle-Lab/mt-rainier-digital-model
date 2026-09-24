"""Wavenumber-domain fusion of the geology model with the regional model, in ln V.

    ln V_fused = LP(ln V_regional) + [ln V_geology - LP(ln V_geology)]

LP is a horizontal Gaussian low-pass with half-power at the cutoff wavelength lambda_c,
sigma = sqrt(2 ln 2) * lambda_c / (2 pi). lambda_c depends on depth below the ground: LP is
computed for each tabulated lambda_c and interpolated cell by cell in depth. Air cells are handled
by normalised convolution. Overshoot is then removed by alternating projections: clamp each cell
between its geology and regional values, restore LP(ln V_regional), repeat. Above
``geology_only_depth_m`` the geology model is kept as is; a
linear taper reaches the fused model at ``taper_depth_m``.

Density follows Vp: rho_fused = rho_geology * rho_ND(Vp_fused) / rho_ND(Vp_geology), with rho_ND
the Nafe-Drake fit, so that unit contrasts in density survive. Ice keeps its density.
"""

from __future__ import annotations

import numpy as np
from scipy.ndimage import gaussian_filter

SIGMA_PER_LAMBDA = np.sqrt(2 * np.log(2)) / (2 * np.pi)


def lowpass_h(f: np.ndarray, mask: np.ndarray, lam_m: float, dx: float) -> np.ndarray:
    """Masked horizontal Gaussian low-pass of f (nz, ny, nx); NaN where mask is False."""
    s = SIGMA_PER_LAMBDA * lam_m / dx
    num = gaussian_filter(np.where(mask, f, 0.0), sigma=(0, s, s), mode="nearest")
    den = gaussian_filter(mask.astype(float), sigma=(0, s, s), mode="nearest")
    with np.errstate(invalid="ignore", divide="ignore"):
        out = num / den
    return np.where(mask, out, np.nan)


def lowpass_depth_varying(f, mask, depth, table, dx):
    """LP with lambda_c interpolated in depth from ``table`` [[depth_m, lambda_m], ...]."""
    dep = np.array([t[0] for t in table], float)
    lam = np.array([t[1] for t in table], float)
    lps = [lowpass_h(f, mask, lm, dx) for lm in lam]
    if len(lps) == 1:
        return lps[0]
    dc = np.clip(depth, dep[0], dep[-1])
    i = np.clip(np.searchsorted(dep, dc) - 1, 0, dep.size - 2)
    w = (dc - dep[i]) / (dep[i + 1] - dep[i])
    stack = np.stack(lps)
    lo = np.take_along_axis(stack, i[None], 0)[0]
    hi = np.take_along_axis(stack, (i + 1)[None], 0)[0]
    return (1 - w) * lo + w * hi


def fuse(v_geo, v_reg, depth, mask, table, dx, d_geo, d_taper, n_iter=6):
    lg, lr = np.log(v_geo), np.log(v_reg)
    lp_reg = lowpass_depth_varying(lr, mask, depth, table, dx)
    fused = lp_reg + lg - lowpass_depth_varying(lg, mask, depth, table, dx)
    # A Gaussian high-pass overshoots at sharp contrasts (fast rims around slow bodies). Alternate
    # two projections: keep each cell between its geology and regional values (no new extremes),
    # and restore the regional low-pass.
    lo, hi = np.fmin(lg, lr), np.fmax(lg, lr)
    for _ in range(n_iter):
        fused = np.clip(fused, lo, hi)
        fused = fused + lp_reg - lowpass_depth_varying(fused, mask, depth, table, dx)
    fused = np.clip(fused, lo, hi)
    w = np.clip((depth - d_geo) / max(d_taper - d_geo, 1e-9), 0, 1)
    out = (1 - w) * lg + w * fused
    return np.where(mask, np.exp(out), np.nan)


def lowpass_misfit(v_fused, v_reg, depth, mask, table, dx, min_depth):
    """RMS over cells deeper than ``min_depth`` of LP(ln V_fused) - LP(ln V_regional)."""
    a = lowpass_depth_varying(np.log(v_fused), mask, depth, table, dx)
    b = lowpass_depth_varying(np.log(v_reg), mask, depth, table, dx)
    sel = mask & (depth > min_depth)
    return float(np.sqrt(np.nanmean((a - b)[sel] ** 2))) if sel.any() else float("nan")
