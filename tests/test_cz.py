import numpy as np
import pytest
import yaml

from rainier3d.config.domain import REPO
from rainier3d.cz import medium as M
from rainier3d.cz import rockphysics as R
from rainier3d.cz import synthetics as SY

CFG = yaml.safe_load((REPO / "configs" / "cz.yaml").read_text())
K_S, MU_S = 40e9, 25e9


def test_hertz_mindlin_shear_velocity_scales_as_stress_to_one_sixth():
    _, mu1 = R.hertz_mindlin(10e3, 0.36, K_S, MU_S, 9, 1.0)
    _, mu2 = R.hertz_mindlin(640e3, 0.36, K_S, MU_S, 9, 1.0)
    assert np.sqrt(mu2 / mu1) == pytest.approx(64 ** (1 / 6), rel=1e-9)  # Vs ~ sigma^(1/6) at fixed density


def test_soft_sand_meets_hertz_mindlin_at_the_critical_porosity():
    K1, mu1 = R.soft_sand(100e3, 0.4, K_S, MU_S, 9, 0.5, 0.4)
    K2, mu2 = R.hertz_mindlin(100e3, 0.4, K_S, MU_S, 9, 0.5)
    assert K1 == pytest.approx(K2) and mu1 == pytest.approx(mu2)
    _, mu_dense = R.soft_sand(100e3, 0.1, K_S, MU_S, 9, 0.5, 0.4)
    assert mu_dense > mu1  # less porous is stiffer


def test_fluids_suction_and_gassmann_limits():
    assert R.brie(1.0, 2.25e9, 1.42e5, 3) == pytest.approx(2.25e9)
    assert R.brie(0.0, 2.25e9, 1.42e5, 3) == pytest.approx(1.42e5)
    assert R.suction_stress(0.0, 1.0) == 0  # saturated: no suction stress
    assert R.suction_stress(5.0, 0.5) == pytest.approx(-1000 * R.G * 5 * 0.5)
    assert R.vg_se(0.0, 3.0, 1.5) == pytest.approx(1.0)
    Kd = 50e6
    assert R.gassmann(Kd, K_S, 1e3, 0.3) == pytest.approx(Kd, rel=1e-3)  # air-filled: the dry frame


def _inputs(water_table=10.0, prior=20.0):
    return {
        "soil_thickness": 1.4,
        "cover_base": 5.0,
        "weathered_prior": prior,
        "unit_factor": {},
        "surface_unit": 6,
        "canopy_height": 0.0,
        "under_ice": False,
        "ice_thickness": 0.0,
        "overburden_pa": 0.0,
        "water_table": water_table,
        "bulk_density": 0.98,
        "clay_fraction": 0.08,
        "log10_ksat": -4.8,
        "theta_r": 0.03,
        "theta_s": 0.65,
        "alpha": 12.0,
        "n": 1.48,
    }


def _rock(p_mpa):  # a uniform rock end-member: m/s and kg/m3
    shape = np.shape(p_mpa)
    return np.full(shape, 3500.0), np.full(shape, 2000.0), np.full(shape, 2500.0)


def _column(**kw):
    z, dz = M.fine_grid(CFG)
    return M.profile(z, dz, _inputs(**kw), _rock, CFG), z, dz


def test_medium_is_continuous_from_regolith_to_the_rock_law():
    pr, z, _ = _column()
    W = pr["weathering_index"]
    assert W[0] == 1 and W[-1] == 0 and np.all(np.diff(W) <= 1e-12)
    rock = W == 0
    assert np.allclose(pr["vs"][rock], 2000.0) and np.allclose(pr["vp"][rock], 3500.0)  # the rock law
    assert np.max(np.abs(np.diff(np.log(pr["vs"][z > 25])))) < 0.25  # no jump across the fractured zone
    assert (
        pr["porosity"][0] > pr["porosity"][-1] and pr["log10_permeability"][0] > pr["log10_permeability"][-1]
    )


def test_vp_jumps_at_the_water_table_in_the_regolith():
    z, dz = M.fine_grid(CFG)
    wet = M.profile(z, dz, _inputs(water_table=3.0), _rock, CFG)
    dry = M.profile(z, dz, _inputs(water_table=8.0), _rock, CFG)
    i = np.searchsorted(z, 5.0)
    assert wet["vp"][i] > 1.3 * dry["vp"][i] and wet["saturation"][i] == 1  # 1.43 in the cover at 5 m


def test_soft_layer_over_rock_is_dispersive():
    pr, _, dz = _column()
    pr["dz"] = dz
    col = SY.stack(pr, [200.0, 250.0], [3500.0] * 2, [2000.0] * 2, [2500.0] * 2)
    c = SY.phase_velocity(col, [2, 10, 40])
    assert c[0] > c[1] > c[2]


def test_calibration_recovers_the_weathered_base_from_synthetic_dispersion():
    import pandas as pd

    from rainier3d.cz import calibrate as CA

    def build(d):
        pr, _, dz = _column(prior=float(d))
        pr["dz"] = dz
        return SY.stack(pr, [200.0, 250.0], [3500.0] * 2, [2000.0] * 2, [2500.0] * 2)

    f = [3, 5, 7, 10, 15, 20]
    c = SY.phase_velocity(build(30.0), f)
    obs = pd.DataFrame({"site": "X", "frequency_hz": f, "phase_velocity_ms": c, "sigma_ms": 0.02 * c})
    assert CA.fit(build, obs, np.arange(10, 51, 5))["best"] == 30.0
