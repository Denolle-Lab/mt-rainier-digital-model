"""Strain in the model volume (rainier3d.geodesy.volume): signs, orientations and the elastic compliance."""

import numpy as np

from rainier3d.geodesy import volume as V


def test_right_lateral_shear_on_north_south_planes_is_positive():
    # right-lateral on N-S planes: the east side moves south, so dv_y/dx < 0 and e_xy < 0
    r = V.resolved_on_strike(0.0, 0.0, -1e-8, strike_deg=0.0)
    assert np.isclose(r["right_lateral_shear"], 1e-8) and np.isclose(r["normal"], 0.0)
    r = V.resolved_on_strike(0.0, 0.0, -1e-8, strike_deg=90.0)  # E-W planes see left-lateral
    assert np.isclose(r["right_lateral_shear"], -1e-8)


def test_principal_axes_of_north_south_shortening():
    p = V.principal_horizontal(exx=1e-8, eyy=-2e-8, exy=0.0)
    assert np.isclose(p["az_shortening"], 0.0) and np.isclose(p["az_extension"], 90.0)
    assert np.isclose(p["max_shear"], 1.5e-8)
    q = V.principal_horizontal(exx=0.0, eyy=0.0, exy=-1e-8)  # simple shear: shortening NE-SW
    assert np.isclose(q["az_shortening"], 45.0)


def test_compliance_uniaxial_matches_youngs_modulus():
    vp, vs, rho = 6000.0, 3464.1, 2700.0  # nu = 0.25
    mu = rho * vs**2
    nu = (vp**2 - 2 * vs**2) / (2 * (vp**2 - vs**2))
    E = 2 * mu * (1 + nu)
    s = np.zeros((1, 6))
    s[0, 2] = -1e6  # 1 MPa vertical compression
    e = V.compliance(s, np.array([vp]), np.array([vs]), np.array([rho]))[0]
    assert np.isclose(e[2], -1e6 / E, rtol=1e-6)
    assert np.isclose(e[0], nu * 1e6 / E, rtol=1e-4) and np.isclose(e[0], e[1])


def test_plane_stress_and_strike_from_epicentres():
    assert np.isclose(V.plane_stress_ezz(1e-8, 1e-8, 0.25), -2e-8 / 3)
    rng = np.random.default_rng(0)
    t = rng.uniform(-20e3, 20e3, 500)
    x, y = t * np.sin(np.radians(170)) + rng.normal(0, 1e3, 500), t * np.cos(np.radians(170))
    strike, elong = V.strike_from_epicentres(x, y)
    assert abs(strike - 170.0) < 2.0 and elong > 5
