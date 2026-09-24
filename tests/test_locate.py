"""Synthetic checks of the 3D locator, the ray derivatives and parameter separation (S13, S14)."""

import numpy as np
import pandas as pd

from rainier3d.validate import locate as L

KNOTS = np.array([0.0, 2000, 5000, 9000])


def _setup(v=5000.0):
    dx = 500.0
    xs, ys = np.arange(0, 20001, dx), np.arange(0, 20001, dx)
    zs = np.arange(1000, -12001, -dx)
    g = L.Grid(xs, ys, zs, dx)
    rng = np.random.default_rng(0)
    sta = np.column_stack([rng.uniform(1000, 19000, (8, 2)), np.full(8, -500.0)])
    vel = np.full(g.shape, v)
    return g, sta, vel


def test_locate_recovers_synthetic_hypocentre():
    g, sta, vel = _setup()
    T = {"P": L.fields(vel, g, sta, workers=4)}
    true = np.array([9300.0, 11200.0, 6100.0])
    t = np.array([g.sample(T["P"][i], true[None])[0] for i in range(len(sta))]) + 0.3
    out = L.locate_event(
        T, g, np.array(["P"] * len(sta)), np.arange(len(sta)), t, (10000, 10000, 5000), half=8000
    )
    assert np.linalg.norm(np.array([out["x"], out["y"], out["d"]]) - true) < 100
    assert abs(out["t0"] - 0.3) < 0.02


def test_ray_derivatives_sum_to_minus_travel_time():
    """With taper 1, the hat weights sum to 1, so sum_k dT/dm_k = -T (uniform factor: T -> T exp(-m))."""
    g, sta, vel = _setup()
    Tst = L.fields(vel, g, sta[:1], workers=1)[0]
    src = np.array([[15000.0, 4000.0, 8000.0], [3000.0, 17000.0, 2500.0]])
    ones = np.ones(g.shape)
    depth = np.broadcast_to(-g.zs[None, None, :], g.shape).copy()
    K, t_ray, failed = L.ray_kernels(Tst, g, sta[0], src, vel, ones, depth, KNOTS)
    t_true = np.linalg.norm(src - sta[0], axis=1) / 5000.0
    assert np.allclose(t_ray, t_true, rtol=0.01)
    assert np.allclose(K.sum(axis=1), -t_ray, rtol=1e-6)
    assert not failed.any()


def test_separation_annihilates_hypocentre_partials():
    rng = np.random.default_rng(1)
    n = 12
    H = np.column_stack([rng.normal(size=(n, 3)), np.ones(n)])
    A = rng.normal(size=(n, 3))
    Q, _ = np.linalg.qr(H, mode="complete")
    assert np.allclose(Q[:, 4:].T @ H, 0, atol=1e-12)
    # a residual made only of a hypocentre shift is invisible to the model update
    r = H @ rng.normal(size=4)
    assert np.allclose(Q[:, 4:].T @ r, 0, atol=1e-12)
    assert np.linalg.matrix_rank(Q[:, 4:].T @ A) == 3


def test_residual_stats_counts_rejections():
    pk = pd.DataFrame({"phase": ["P", "P", "S"], "res": [0.1, -0.1, 2.0], "w": [1.0, 1.0, 0.0]})
    s = L.residual_stats(pk)
    assert s["P"]["n"] == 2 and s["S"]["rejected"] == 1


def test_topography_mask_keeps_skin_and_slows_air():
    g, sta, vel = _setup()
    ground = np.full(g.shape[:2], 0.0)
    v = L.with_topography(np.transpose(vel, (2, 0, 1)), g, ground, skin_cells=1)
    z = g.zs
    assert np.all(v[z > 500.0] == L.AIR_V)  # more than one cell above the ground
    assert np.all(v[z <= 500.0] == 5000.0)  # ground and the one-cell skin
    assert L.with_topography(vel, g, ground, skin_cells=-1) is vel


def test_ground_bound_keeps_shallow_event_below_ground():
    """A source just below the ground, located with the bound, stays below it (within GROUND_TOL)."""
    g, sta, vel = _setup()
    ground = np.full(g.shape[:2], 0.0)
    T = {"P": L.fields(vel, g, sta, workers=4)}
    true = np.array([9300.0, 11200.0, 100.0])  # 100 m below ground
    t = np.array([g.sample(T["P"][i], true[None])[0] for i in range(len(sta))])
    out = L.locate_event(
        T,
        g,
        np.array(["P"] * len(sta)),
        np.arange(len(sta)),
        t,
        (10000, 10000, 3000),
        half=8000,
        ground=ground,
    )
    assert out["above_ground_m"] <= L.GROUND_TOL + 1
    assert np.linalg.norm(np.array([out["x"], out["y"], out["d"]]) - true) < 250
