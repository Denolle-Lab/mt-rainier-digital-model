"""Vs calibration helpers (S12)."""

import numpy as np

from rainier3d.validate import calibrate as C


def test_log_factor_interpolates_and_holds_ends():
    m = np.arange(C.KNOTS_M.size, dtype=float)
    assert C.log_factor(np.array([0.0, 1500.0, 1e6, -50.0]), m).tolist() == [0.0, 1.5, m[-1], 0.0]


def test_fusion_taper():
    assert C.fusion_taper(np.array([0, 300, 650, 1000, 5000]), 300, 1000).tolist() == [0, 0, 0.5, 1, 1]


def test_gn_step_recovers_linear_truth():
    rng = np.random.default_rng(1)
    J = rng.normal(size=(400, C.KNOTS_M.size))
    m_true = np.linspace(0.05, -0.03, C.KNOTS_M.size)
    r = J @ m_true  # residual of the starting model m = 0
    m = C.gn_step(J, r, np.zeros_like(m_true), np.ones(400, bool), lam_s=1e-6, lam_d=1e-6)
    assert np.allclose(m, m_true, atol=1e-4)


def test_stats_demeaning():
    s = C.stats(np.array([1.0, 3.0, -2.0, 2.0]), np.array(["a", "a", "b", "b"]))
    assert s["mean_s"] == 1.0 and np.isclose(s["rms_demeaned_s"], np.sqrt((1 + 1 + 4 + 4) / 4))
