"""Strain in the model volume: tectonic strain rate carried down from the GNSS surface field, and the static
strain of the edifice load.

Tectonic rate. GNSS measures the horizontal strain rate at the surface only. Below it we assume (a) the
horizontal strain-rate tensor does not change with depth in the elastic upper crust, and (b) the vertical
normal stress rate is zero (plane stress), so e_zz = -nu / (1 - nu) (e_xx + e_yy). Both are assumptions.

Edifice load. The Boussinesq stress of rainier3d.geodesy.load (homogeneous half-space) is turned into strain
with the local stiffness of the velocity model (mu = rho Vs^2, lambda = rho Vp^2 - 2 mu), so soft rock strains
more under the same stress. The stress itself ignores the stiffness contrasts; this is a first-order estimate.

Conventions: x east, y north, z up; extension and tension positive; azimuths in degrees east of north, 0-180.
"""

from __future__ import annotations

import numpy as np
import xarray as xr
from scipy.interpolate import RegularGridInterpolator


def horizontal_rate_at(grid: xr.Dataset, x, y) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """exx, eyy, exy of the GNSS strain-rate grid (strain_grid.nc) at points (x, y), bilinear; NaN outside."""
    out = []
    for k in ("exx", "eyy", "exy"):
        f = RegularGridInterpolator(
            (grid.y.values, grid.x.values), grid[k].values, bounds_error=False, fill_value=np.nan
        )
        out.append(f(np.column_stack([np.ravel(y), np.ravel(x)])).reshape(np.shape(x)))
    return tuple(out)


def plane_stress_ezz(exx, eyy, nu: float):
    """Vertical normal strain under zero vertical normal stress."""
    return -nu / (1.0 - nu) * (np.asarray(exx) + np.asarray(eyy))


def principal_horizontal(exx, eyy, exy) -> dict[str, np.ndarray]:
    """Horizontal principal strains and axes: e1 >= e2; azimuths of e1 (most extensional) and e2 (most
    shortening); maximum horizontal shear (e1 - e2) / 2."""
    exx, eyy, exy = map(np.asarray, (exx, eyy, exy))
    c, r = (exx + eyy) / 2, np.sqrt(((exx - eyy) / 2) ** 2 + exy**2)
    ang = 0.5 * np.degrees(np.arctan2(2 * exy, exx - eyy))  # angle of e1 from +x, counter-clockwise
    az1 = np.mod(90.0 - ang, 180.0)
    return {
        "e1": c + r,
        "e2": c - r,
        "az_extension": az1,
        "az_shortening": np.mod(az1 + 90.0, 180.0),
        "max_shear": r,
    }


def resolved_on_strike(exx, eyy, exy, strike_deg: float) -> dict[str, np.ndarray]:
    """Strain on vertical planes of the given strike: normal strain across the planes and the shear strain
    along them, positive for right-lateral motion (the far side moves to the right, as on the WRSZ)."""
    phi = np.radians(strike_deg)
    s = np.array([np.sin(phi), np.cos(phi)])  # along strike (east, north)
    n = np.array([np.cos(phi), -np.sin(phi)])  # horizontal normal, 90 deg clockwise from s
    exx, eyy, exy = map(np.asarray, (exx, eyy, exy))

    def quad(a, b):
        return exx * a[0] * b[0] + eyy * a[1] * b[1] + exy * (a[0] * b[1] + a[1] * b[0])

    return {"normal": quad(n, n), "right_lateral_shear": -quad(s, n)}


def compliance(stress: np.ndarray, vp, vs, rho) -> np.ndarray:
    """Isotropic strain (xx, yy, zz, xy, xz, yz; tensor components) from stress (same order, Pa) and local
    velocities (m/s) and density (kg/m3)."""
    mu = np.asarray(rho) * np.asarray(vs) ** 2
    lam = np.asarray(rho) * np.asarray(vp) ** 2 - 2 * mu
    tr = stress[..., 0] + stress[..., 1] + stress[..., 2]
    a = 1.0 / (2 * mu)
    b = lam / (2 * mu * (3 * lam + 2 * mu))
    eps = stress * a[..., None]
    eps[..., :3] -= (b * tr)[..., None]
    return eps


def shmax_azimuth(sxx, syy, sxy) -> np.ndarray:
    """Azimuth of the most compressive horizontal stress (tension positive, so the smaller eigenvalue)."""
    return principal_horizontal(sxx, syy, sxy)["az_shortening"]


def strike_from_epicentres(x, y) -> tuple[float, float]:
    """Strike (azimuth of the long axis, 0-180) of a cloud of epicentres and its elongation (sqrt of the
    eigenvalue ratio), from the principal axes of their covariance."""
    xy = np.column_stack([np.ravel(x), np.ravel(y)])
    xy = xy - xy.mean(0)
    w, v = np.linalg.eigh(np.cov(xy.T))
    ax = v[:, 1]  # largest eigenvalue
    return float(np.mod(np.degrees(np.arctan2(ax[0], ax[1])), 180.0)), float(np.sqrt(w[1] / w[0]))
