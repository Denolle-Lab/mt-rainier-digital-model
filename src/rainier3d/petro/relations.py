"""Rock-physics relations used to turn units into Vp, Vs, density and Q.

Brocher (2005, BSSA 95, doi:10.1785/0120050077): polynomial fits, Vp and Vs in km/s,
density in g/cm^3. The Vs(Vp) fit ("Brocher's regression fit", his Eq. 6) and the Nafe-Drake
density fit (his Eq. 1) are stated valid for 1.5 < Vp < 8.5 km/s.
"""

from __future__ import annotations

import numpy as np


def brocher_vs_from_vp(vp):
    vp = np.asarray(vp, dtype=float)
    return 0.7858 - 1.2344 * vp + 0.7949 * vp**2 - 0.1238 * vp**3 + 0.0064 * vp**4


def nafe_drake_rho_from_vp(vp):
    vp = np.asarray(vp, dtype=float)
    return 1.6612 * vp - 0.4721 * vp**2 + 0.0671 * vp**3 - 0.0043 * vp**4 + 0.000106 * vp**5


def brocher_vp_from_vs(vs):
    vs = np.asarray(vs, dtype=float)
    return 0.9409 + 2.0947 * vs - 0.8206 * vs**2 + 0.2683 * vs**3 - 0.0251 * vs**4


def crack_closure(v0, vinf, p_mpa, pstar_mpa):
    """V(P) = Vinf - (Vinf - V0) exp(-P / P*): velocity rising with effective pressure as cracks close."""
    return vinf - (vinf - v0) * np.exp(-np.asarray(p_mpa) / pstar_mpa)


def q_from_vs(vs_kms, qs_per_vs=0.05, qp_over_qs=2.0):
    qs = qs_per_vs * np.asarray(vs_kms) * 1000.0
    return qp_over_qs * qs, qs
