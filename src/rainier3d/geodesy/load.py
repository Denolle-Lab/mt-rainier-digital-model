"""Stress under Mount Rainier from the weight of the edifice (Boussinesq point loads, elastic half-space).

The load is the edifice above the pre-volcanic surface of the geology model (surface node ``edifice_base``):
each column of thickness h carries a vertical force rho g h A, aggregated onto ``load_cell_m`` cells. The
half-space surface is a flat reference plane at the mean base elevation, and the medium is homogeneous, so
stresses depend on Poisson's ratio only (not on the elastic moduli). Point-load stresses, tension positive,
force P downward, r horizontal distance, z depth below the plane, R = sqrt(r^2 + z^2) (Johnson, 1985, Contact
Mechanics, eqs. 3.4):

  s_zz = -3 P z^3 / (2 pi R^5)                 s_rz = -3 P r z^2 / (2 pi R^5)
  s_rr = P / (2 pi) [ (1 - 2 nu) / r^2 (1 - z / R) - 3 r^2 z / R^5 ]
  s_tt = -P (1 - 2 nu) / (2 pi) [ (1 / r^2)(1 - z / R) - z / R^3 ]

Limitations: no lateral density or stiffness contrasts, no topography of the reference plane, and points
shallower than ``min_depth_m`` below the plane are left out (the point-load field is singular there).
"""

from __future__ import annotations

import numpy as np
from numba import njit, prange

G = 9.81


@njit(parallel=True, cache=True)
def _boussinesq(px, py, pf, tx, ty, tz, nu):
    n = tx.size
    out = np.zeros((n, 6))  # xx, yy, zz, xy, xz, yz
    for i in prange(n):
        sxx = syy = szz = sxy = sxz = syz = 0.0
        z = tz[i]
        for k in range(px.size):
            dx, dy = tx[i] - px[k], ty[i] - py[k]
            r2 = dx * dx + dy * dy
            R2 = r2 + z * z
            R = np.sqrt(R2)
            R5 = R2 * R2 * R
            P = pf[k]
            c = P / (2 * np.pi)
            s_zz = -3 * c * z**3 / R5
            s_rz = -3 * c * np.sqrt(r2) * z * z / R5
            if r2 > 1e-6:
                s_rr = c * ((1 - 2 * nu) / r2 * (1 - z / R) - 3 * r2 * z / R5)
                s_tt = -c * (1 - 2 * nu) * ((1 / r2) * (1 - z / R) - z / (R2 * R))
                cf, sf = dx / np.sqrt(r2), dy / np.sqrt(r2)
            else:  # on the axis, (1/r^2)(1 - z/R) -> 1/(2 z^2): s_rr = s_tt = P (1 - 2 nu) / (4 pi z^2)
                s_rr = s_tt = c * (1 - 2 * nu) / (2 * z * z)
                cf, sf = 1.0, 0.0
            sxx += s_rr * cf * cf + s_tt * sf * sf
            syy += s_rr * sf * sf + s_tt * cf * cf
            sxy += (s_rr - s_tt) * sf * cf
            sxz += s_rz * cf
            syz += s_rz * sf
            szz += s_zz
        out[i, 0], out[i, 1], out[i, 2], out[i, 3], out[i, 4], out[i, 5] = sxx, syy, szz, sxy, sxz, syz
    return out


def edifice_loads(surface, footprint_only: bool = True, load_cell_m: float = 500.0, rho: float = 2500.0):
    """Point loads (x, y, force N, downward) and the reference-plane elevation from the surface node."""
    elev, base = surface["elevation"].values.astype(float), surface["edifice_base"].values.astype(float)
    h = np.where(np.isfinite(base), elev - base, 0.0)
    if footprint_only:
        h = np.where(surface["footprint"].values.astype(bool), h, 0.0)
    h = np.clip(h, 0, None)
    x, y = surface["x"].values, surface["y"].values
    res = float(abs(x[1] - x[0]))
    f = int(round(load_cell_m / res))
    ny, nx = (h.shape[0] // f) * f, (h.shape[1] // f) * f
    hb = h[:ny, :nx].reshape(ny // f, f, nx // f, f)
    force = rho * G * hb.sum(axis=(1, 3)) * res * res
    xc = x[:nx].reshape(-1, f).mean(1)
    yc = y[:ny].reshape(-1, f).mean(1)
    X, Y = np.meshgrid(xc, yc)
    keep = force > 0
    z_ref = float(np.nanmean(base[np.isfinite(base) & (h > 0)])) if (h > 0).any() else 0.0
    return X[keep], Y[keep], force[keep], z_ref


def stress_at(points_xyz, loads, nu: float = 0.25, min_depth_m: float = 250.0) -> np.ndarray:
    """Stress tensor components (Pa, tension positive) at points (x, y, elevation) from the edifice loads."""
    px, py, pf, z_ref = loads
    p = np.asarray(points_xyz, float)
    depth = z_ref - p[:, 2]
    out = np.full((len(p), 6), np.nan)
    ok = depth >= min_depth_m
    out[ok] = _boussinesq(px, py, pf, p[ok, 0], p[ok, 1], depth[ok], nu)
    return out


def invariants(s: np.ndarray) -> dict[str, np.ndarray]:
    """Mean stress (tension positive), maximum shear and principal stresses from (xx, yy, zz, xy, xz, yz)."""
    T = np.zeros(s.shape[:-1] + (3, 3))
    T[..., 0, 0], T[..., 1, 1], T[..., 2, 2] = s[..., 0], s[..., 1], s[..., 2]
    T[..., 0, 1] = T[..., 1, 0] = s[..., 3]
    T[..., 0, 2] = T[..., 2, 0] = s[..., 4]
    T[..., 1, 2] = T[..., 2, 1] = s[..., 5]
    ok = np.isfinite(T).all(axis=(-1, -2))
    ev = np.full(s.shape[:-1] + (3,), np.nan)
    ev[ok] = np.linalg.eigvalsh(T[ok])
    return {
        "mean": s[..., :3].sum(-1) / 3,
        "max_shear": (ev[..., 2] - ev[..., 0]) / 2,
        "s1": ev[..., 2],
        "s3": ev[..., 0],
    }
