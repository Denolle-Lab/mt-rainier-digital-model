"""Wavenumber-domain fusion of the geology model with the regional model, in ln V.

    ln V_fused = LP(ln V_regional) + [ln V_geology - LP(ln V_geology)]

LP is a horizontal Gaussian low-pass with half-power at the cutoff wavelength lambda_c,
sigma = sqrt(2 ln 2) * lambda_c / (2 pi). lambda_c depends on depth below the ground: LP is
computed for each tabulated lambda_c and interpolated cell by cell in depth. Air cells are handled
by normalised convolution. Overshoot is then removed by alternating projections: clamp each cell
between its geology and regional values, restore LP(ln V_regional), repeat. Above
``geology_only_depth_m`` the geology model is kept as is; a
linear taper reaches the fused model at ``taper_depth_m``.

LP is horizontal, and the geology is kept as is down to ``geology_only_depth_m``, so flat-lying contacts of
the geology (the edifice base, the bases of the cap and of the units with a maximum thickness, 93% of them
100-1000 m below the ground) would pass into the model as steps of up to a factor 2 in V between two cells.
With ``lambda_z`` > 0 the geology is first low-passed in the vertical (the same Gaussian) in the cells
entirely deeper than ``z_smooth`` below the ground, both where it is kept as is and where it is fused. The
cutoff grows from 0 at ``z_smooth`` to lambda_z, as min(4 (d - z_smooth), lambda_z), so that the smoothing
starts without a step; the column above is extended with the value of its first smoothed cell, so shallower
cells (soil, ice, the critical-zone columns) are neither smoothed nor smoothed into the cells below.

The geology also extends each map unit straight down, so unit boundaries are vertical walls (to the base of
the basement units at -4 km). With ``lambda_h`` > 0 the same cells are then low-passed horizontally, among
themselves at each elevation, with a cutoff min(growth_h (d - z_smooth), lambda_h): mapped contacts stay as
mapped near the surface and fade with depth, where the extrusion rule is least constrained. Both filters are
``smooth_geology``, which the invariant tests reuse.

Density follows Vp: rho_fused = rho_geology * rho_ND(Vp_fused) / rho_ND(Vp_geology), with rho_ND
the Nafe-Drake fit, so that unit contrasts in density survive. Ice keeps its density.
"""

from __future__ import annotations

import numpy as np
from scipy.ndimage import gaussian_filter, gaussian_filter1d

SIGMA_PER_LAMBDA = np.sqrt(2 * np.log(2)) / (2 * np.pi)


def lowpass_h(f: np.ndarray, mask: np.ndarray, lam_m: float, dx: float) -> np.ndarray:
    """Masked horizontal Gaussian low-pass of f (nz, ny, nx); NaN where mask is False."""
    s = SIGMA_PER_LAMBDA * lam_m / dx
    num = gaussian_filter(np.where(mask, f, 0.0), sigma=(0, s, s), mode="nearest")
    den = gaussian_filter(mask.astype(float), sigma=(0, s, s), mode="nearest")
    with np.errstate(invalid="ignore", divide="ignore"):
        out = num / den
    return np.where(mask, out, np.nan)


def lowpass_v(f: np.ndarray, below: np.ndarray, lam_m: float, dz: float) -> np.ndarray:
    """Vertical Gaussian low-pass of f (nz, ny, nx, top first) in the cells ``below``, the lower part of each
    column; above its first such cell a column takes that cell's value. NaN outside ``below``."""
    if lam_m <= 0:
        return np.where(below, f, np.nan)
    k0 = np.argmax(below, axis=0)[None]
    g = np.where(np.arange(f.shape[0])[:, None, None] < k0, np.take_along_axis(f, k0, 0), f)
    g = np.where(below.any(0)[None], g, 0.0)
    out = gaussian_filter1d(g, sigma=SIGMA_PER_LAMBDA * lam_m / dz, axis=0, mode="nearest")
    return np.where(below, out, np.nan)


def lowpass_v_growing(f, below, depth, z0, lam_m, dz, n=5):
    """``lowpass_v`` with the cutoff min(4 (depth - z0), lam_m), interpolated cell by cell between n cutoffs:
    full lam_m at lam_m / 4 below z0."""
    lams = np.linspace(0.0, lam_m, n)
    stack = np.stack([lowpass_v(f, below, lm, dz) for lm in lams])
    lam = np.clip(4 * (depth - z0), 0.0, lam_m)
    i = np.clip(np.searchsorted(lams, lam) - 1, 0, n - 2)
    w = (lam - lams[i]) / (lams[i + 1] - lams[i])
    lo = np.take_along_axis(stack, i[None], 0)[0]
    hi = np.take_along_axis(stack, (i + 1)[None], 0)[0]
    return (1 - w) * lo + w * hi


def lowpass_h_growing(f, below, depth, z0, lam_m, dx, growth, n=5):
    """``lowpass_h`` among the cells ``below`` with the cutoff min(growth (depth - z0), lam_m), interpolated
    cell by cell between n cutoffs; NaN outside ``below``."""
    lams = np.linspace(0.0, lam_m, n)
    stack = np.stack([np.where(below, f, np.nan) if lm == 0 else lowpass_h(f, below, lm, dx) for lm in lams])
    lam = np.clip(growth * (depth - z0), 0.0, lam_m)
    i = np.clip(np.searchsorted(lams, lam) - 1, 0, n - 2)
    w = (lam - lams[i]) / (lams[i + 1] - lams[i])
    lo = np.take_along_axis(stack, i[None], 0)[0]
    hi = np.take_along_axis(stack, (i + 1)[None], 0)[0]
    return (1 - w) * lo + w * hi


def smooth_geology(lg, mask, depth, dx, dz, z_smooth=0.0, lambda_z=0.0, lambda_h=0.0, growth_h=1.0):
    """ln V of the geology low-passed in the vertical, then horizontally, in the cells entirely below
    z_smooth (see the module docstring); other cells unchanged."""
    vm = mask & (depth - dz / 2 >= z_smooth)
    if lambda_z > 0:
        lg = np.where(vm, lowpass_v_growing(lg, vm, depth, z_smooth, lambda_z, dz), lg)
    if lambda_h > 0:
        lg = np.where(vm, lowpass_h_growing(lg, vm, depth, z_smooth, lambda_h, dx, growth_h), lg)
    return lg


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


def fuse(v_geo, v_reg, depth, mask, table, dx, d_geo, d_taper, n_iter=6, dz=None, **smooth):
    """Fused V; ``smooth`` (z_smooth, lambda_z, lambda_h, growth_h) are the geology filters of
    ``smooth_geology``."""
    lg, lr = np.log(v_geo), np.log(v_reg)
    if smooth.get("lambda_z", 0) > 0 or smooth.get("lambda_h", 0) > 0:
        lg = smooth_geology(lg, mask, depth, dx, dz, **smooth)
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
