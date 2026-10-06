"""Rock physics of the critical-zone column (docs/critical_zone.md, "Equations, per column").

SI units throughout: stress and moduli in Pa, density in kg/m3, suction head in m. The chain is
  van Genuchten saturation -> suction stress (Lu, Godt and Wu 2010, chi = Se) -> effective stress
  -> Hertz-Mindlin / soft-sand frame (Dvorkin and Nur 1996)
  -> Gassmann with a Brie patchy fluid (Brie et al. 1995).
"""

from __future__ import annotations

import numpy as np

G = 9.81


def poisson(K, mu):
    return (3 * K - 2 * mu) / (2 * (3 * K + mu))


def hill(frac_clay, quartz, clay):
    """Hill average of (K, mu) for a clay fraction (0-1) mixed with quartz-feldspar grains."""
    f = np.asarray(frac_clay, float)
    out = []
    for i in (0, 1):
        voigt = f * clay[i] + (1 - f) * quartz[i]
        reuss = 1 / (f / clay[i] + (1 - f) / quartz[i])
        out.append(0.5 * (voigt + reuss))
    return out[0], out[1]


def hertz_mindlin(sigma, phi, K_s, mu_s, C, f):
    """Dry-frame moduli of a random pack of identical spheres under effective pressure sigma, with a slip
    fraction
    f (1: no slip, Mindlin; 0: frictionless)."""
    nu = poisson(K_s, mu_s)
    a = C**2 * (1 - phi) ** 2 * mu_s**2 * sigma / (np.pi**2 * (1 - nu) ** 2)
    K = (a / 18) ** (1 / 3)
    mu = (2 + 3 * f - nu * (1 + 3 * f)) / (5 * (2 - nu)) * (3 * a / 2) ** (1 / 3)
    return K, mu


def soft_sand(sigma, phi, K_s, mu_s, C, f, phi_c):
    """Dvorkin-Nur soft-sand model: Hertz-Mindlin at the critical porosity joined to the mineral by the
    modified
    Hashin-Shtrikman lower bound; above the critical porosity, Hertz-Mindlin at phi."""
    phi = np.asarray(phi, float)
    K_hm, mu_hm = hertz_mindlin(sigma, np.minimum(phi, phi_c), K_s, mu_s, C, f)
    x = np.clip(phi / phi_c, 0, 1)
    K = 1 / (x / (K_hm + 4 / 3 * mu_hm) + (1 - x) / (K_s + 4 / 3 * mu_hm)) - 4 / 3 * mu_hm
    z = mu_hm / 6 * (9 * K_hm + 8 * mu_hm) / (K_hm + 2 * mu_hm)
    mu = 1 / (x / (mu_hm + z) + (1 - x) / (mu_s + z)) - z
    loose = phi >= phi_c
    return np.where(loose, K_hm, K), np.where(loose, mu_hm, mu)


def vg_se(psi_m, alpha, n):
    """Effective saturation for a suction head psi_m >= 0 (m), van Genuchten alpha (1/m) and n."""
    psi = np.maximum(np.asarray(psi_m, float), 0)
    return (1 + (alpha * psi) ** n) ** -(1 - 1 / n)


def suction_stress(psi_m, se, rho_w=1000.0):
    """Suction stress (Pa, negative: it adds to the effective stress) for chi = Se (Lu, Godt and Wu 2010)."""
    return -rho_w * G * np.maximum(psi_m, 0) * se


def brie(S, K_w, K_a, e):
    """Patchy-mixing fluid modulus of water saturation S (Brie et al. 1995)."""
    return (K_w - K_a) * np.clip(S, 0, 1) ** e + K_a


def gassmann(K_dry, K_s, K_f, phi):
    """Saturated bulk modulus; the shear modulus is unchanged."""
    return K_dry + (1 - K_dry / K_s) ** 2 / (phi / K_f + (1 - phi) / K_s - K_dry / K_s**2)
