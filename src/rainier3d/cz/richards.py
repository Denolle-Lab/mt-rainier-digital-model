"""1D Richards equation for a critical-zone column (build step 3 of docs/critical_zone.md).

Mixed form with the modified Picard iteration of Celia et al. (1990), cell-centred on the layers of
rainier3d.cz.columns, depth z positive down:

    d theta(h) / dt = d/dz [ K(h) (dh/dz - 1) ]

van Genuchten (1980) retention with Mualem conductivity. Top: rain as a flux; where the surface saturates, a
ponding condition h = 0 with the excess counted as runoff. Bottom: the static water table as a fixed head when
it lies inside the domain, free drainage (unit gradient) when it lies below. No lateral flow,
evapotranspiration, interception or snow yet (placeholders of configs/cz.yaml).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.linalg import solve_banded

SS = 1.0e-5  # specific storage of the saturated column (1/m), keeps the system well posed


@dataclass
class Column:
    dz: np.ndarray  # layer thickness (m)
    z: np.ndarray  # layer centre depth (m)
    theta_r: np.ndarray
    theta_s: np.ndarray
    alpha: np.ndarray  # 1/m
    n: np.ndarray
    ksat: np.ndarray  # m/s
    bottom_head: float | None  # fixed head at the bottom layer (m), or None for free drainage


def theta(c: Column, h):
    m = 1 - 1 / c.n
    se = np.where(h < 0, (1 + (c.alpha * np.abs(h)) ** c.n) ** -m, 1.0)
    return c.theta_r + (c.theta_s - c.theta_r) * se, se


def capacity(c: Column, h):
    m = 1 - 1 / c.n
    a = c.alpha * np.abs(h)
    dth = (c.theta_s - c.theta_r) * c.alpha * c.n * m * a ** (c.n - 1) * (1 + a**c.n) ** -(m + 1)
    return np.where(h < 0, dth, 0.0) + SS


def conductivity(c: Column, se):
    m = 1 - 1 / c.n
    return c.ksat * np.sqrt(se) * (1 - (1 - se ** (1 / m)) ** m) ** 2


def _step(c: Column, h0, dt, q_top, tol, itmax):
    """One implicit step; returns (h, converged, infiltration rate, bottom flux, iterations)."""
    th0, _ = theta(c, h0)
    d = (c.dz[:-1] + c.dz[1:]) / 2  # centre-to-centre distances
    h = h0.copy()
    ponded = False
    it = 0
    while it < itmax:
        it += 1
        th, se = theta(c, h)
        K = conductivity(c, se)
        Kf = 0.5 * (K[:-1] + K[1:])  # interface conductivity
        a = Kf / d
        Cm = capacity(c, h)
        diag = c.dz * Cm / dt
        rhs = c.dz * (Cm * h - th + th0) / dt
        lo, up = np.zeros_like(h), np.zeros_like(h)
        diag[:-1] += a
        diag[1:] += a
        up[1:] = -a  # coefficient of h[i+1] in row i, stored at i+1 for solve_banded
        lo[:-1] = -a  # coefficient of h[i-1] in row i, stored at i-1
        rhs[:-1] -= Kf
        rhs[1:] += Kf
        if ponded:  # h = 0 at the surface
            diag[0], up[1], rhs[0] = 1.0, 0.0, 0.0
        else:
            rhs[0] += q_top
        if c.bottom_head is None:  # free drainage: K leaves the bottom layer
            rhs[-1] -= K[-1]
        else:
            diag[-1], lo[-2], rhs[-1] = 1.0, 0.0, c.bottom_head
        hn = solve_banded((1, 1), np.vstack([up, diag, lo]), rhs)
        if not ponded and hn[0] > 0:  # the surface cannot take the rain: pond and recompute
            ponded = True
            continue
        if np.max(np.abs(hn - h)) < tol:
            h = hn
            break
        h = hn
    else:
        return h0, False, 0.0, 0.0, itmax  # no convergence within itmax iterations
    th, se = theta(c, h)
    K = conductivity(c, se)
    stored = np.sum(c.dz * (th - th0)) / dt
    if c.bottom_head is None:
        q_bot = K[-1]
    else:  # flux across the interface above the fixed-head layer
        Kf = 0.5 * (K[-2] + K[-1])
        q_bot = -Kf * ((h[-1] - h[-2]) / ((c.dz[-2] + c.dz[-1]) / 2) - 1)
    infil = stored + q_bot if ponded else q_top
    return h, True, infil, q_bot, it


def run(c: Column, h_init, rain_ms, hours_s: float, dt_range, tol, itmax, out_every: int):
    """Integrate through hourly rain (m/s per hour); return heads at every ``out_every`` hours (including 0)
    and the totals (m) of rain, infiltration, runoff, bottom outflow and storage change."""
    h = np.asarray(h_init, float).copy()
    dt = dt_range[0]
    out = [h.copy()]
    tot = dict(rain=0.0, infiltration=0.0, runoff=0.0, bottom=0.0)
    th_start = np.sum(c.dz * theta(c, h)[0])
    for k, q in enumerate(rain_ms):
        t = 0.0
        while t < hours_s - 1e-6:
            step = min(dt, hours_s - t)
            hn, ok, infil, q_bot, it = _step(c, h, step, q, tol, itmax)
            if not ok:
                if dt <= dt_range[0]:
                    raise RuntimeError("Richards step failed at the minimum time step")
                dt = max(dt / 3, dt_range[0])
                continue
            h, t = hn, t + step
            tot["rain"] += q * step
            tot["infiltration"] += infil * step
            tot["runoff"] += (q - infil) * step
            tot["bottom"] += q_bot * step
            dt = min(dt * 1.5, dt_range[1]) if it <= 5 else dt
        if (k + 1) % out_every == 0:
            out.append(h.copy())
    tot["storage_change"] = float(np.sum(c.dz * theta(c, h)[0]) - th_start)
    tot["mass_balance_error"] = tot["infiltration"] - tot["bottom"] - tot["storage_change"]
    return np.array(out), tot
