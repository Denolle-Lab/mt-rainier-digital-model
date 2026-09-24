"""Horizontal strain from GNSS velocities or displacements.

At each point, a uniform velocity-gradient field v(x) = v0 + L (x - x0) is fitted to nearby stations by
weighted least squares, with Gaussian distance weights whose scale grows until the summed weight reaches
``min_weight`` (an adaptive smoothing in the spirit of Shen et al., 2015, BSSA 105,
doi:10.1785/0120140247). L gives the strain rate e = (L + L^T)/2 and rotation w = (L - L^T)/2. Components
returned (all in the same units as L, e.g. 1/yr):

  exx, eyy, exy        horizontal strain tensor (x east, y north)
  dilatation           exx + eyy (areal strain; > 0 extension)
  max_shear            sqrt(((exx - eyy) / 2)^2 + exy^2)
  e1, e2, azimuth      principal strains (e1 >= e2) and the azimuth of e1, degrees east of north
  rotation             w_xy (> 0 counter-clockwise)
  second_invariant     sqrt(exx^2 + eyy^2 + 2 exy^2)

Stations enter in a local tangent frame (metres); velocities in m/yr give strain rates in 1/yr."""

from __future__ import annotations

import numpy as np

COMPONENTS = (
    "exx",
    "eyy",
    "exy",
    "dilatation",
    "max_shear",
    "e1",
    "e2",
    "azimuth",
    "rotation",
    "second_invariant",
)


def components(exx, eyy, exy, w):
    exx, eyy, exy = map(np.asarray, (exx, eyy, exy))
    c = (exx + eyy) / 2
    r = np.sqrt(((exx - eyy) / 2) ** 2 + exy**2)
    az = np.degrees(0.5 * np.arctan2(2 * exy, exx - eyy))  # angle of e1 from +x (east), counter-clockwise
    return {
        "exx": exx,
        "eyy": eyy,
        "exy": exy,
        "dilatation": exx + eyy,
        "max_shear": r,
        "e1": c + r,
        "e2": c - r,
        "azimuth": np.mod(90.0 - az, 180.0),
        "rotation": np.asarray(w),
        "second_invariant": np.sqrt(exx**2 + eyy**2 + 2 * exy**2),
    }


def fit_gradient(xy: np.ndarray, v: np.ndarray, sig: np.ndarray, x0: np.ndarray, weights: np.ndarray):
    """Weighted LSQ for (v0x, v0y, Lxx, Lxy, Lyx, Lyy) around x0; returns the parameters and their
    covariance."""
    dx = xy - x0
    n = len(xy)
    A = np.zeros((2 * n, 6))
    A[0::2, 0], A[1::2, 1] = 1, 1
    A[0::2, 2], A[0::2, 3] = dx[:, 0], dx[:, 1]
    A[1::2, 4], A[1::2, 5] = dx[:, 0], dx[:, 1]
    b = v.reshape(-1)
    w = np.repeat(weights, 2) / np.maximum(sig.reshape(-1), 1e-6) ** 2
    AtW = A.T * w
    N = AtW @ A
    cov = np.linalg.pinv(N)
    return cov @ (AtW @ b), cov


def strain_grid(
    xy,
    v,
    sig,
    grid_xy,
    min_weight: float = 6.0,
    scales=(5e3, 7.5e3, 1e4, 1.5e4, 2e4, 3e4, 4e4, 6e4),
    min_stations: int = 4,
):
    """Strain-rate components on points ``grid_xy`` (metres). Returns (dict of arrays, scale used per
    point)."""
    out = {k: np.full(len(grid_xy), np.nan) for k in COMPONENTS}
    out["dilatation_sigma"] = np.full(len(grid_xy), np.nan)
    used = np.full(len(grid_xy), np.nan)
    for i, g in enumerate(grid_xy):
        d = np.hypot(*(xy - g).T)
        for s in scales:
            wts = np.exp(-((d / s) ** 2))
            if wts.sum() >= min_weight and (wts > 0.05).sum() >= min_stations:
                break
        else:
            continue
        keep = wts > 1e-3
        p, cov = fit_gradient(xy[keep], v[keep], sig[keep], g, wts[keep])
        Lxx, Lxy, Lyx, Lyy = p[2:]
        c = components(Lxx, Lyy, 0.5 * (Lxy + Lyx), 0.5 * (Lyx - Lxy))
        for k in COMPONENTS:
            out[k][i] = c[k]
        J = np.zeros(6)
        J[2], J[5] = 1, 1
        out["dilatation_sigma"][i] = np.sqrt(J @ cov @ J)
        used[i] = s
    return out, used


def uniform_strain(xy, u, sig):
    """Uniform strain of a station group from one displacement field (e.g. one day): components at the
    centroid."""
    x0 = xy.mean(axis=0)
    p, cov = fit_gradient(xy, u, sig, x0, np.ones(len(xy)))
    Lxx, Lxy, Lyx, Lyy = p[2:]
    c = components(Lxx, Lyy, 0.5 * (Lxy + Lyx), 0.5 * (Lyx - Lxy))
    J = np.zeros(6)
    J[2], J[5] = 1, 1
    c["dilatation_sigma"] = float(np.sqrt(J @ cov @ J))
    return c
