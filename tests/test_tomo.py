"""S37 tomography: node interpolation, regularisation, separation and a straight-ray recovery test."""

import numpy as np
import pandas as pd
import scipy.sparse as sp

from rainier3d.validate import tomo as TM
from rainier3d.validate.locate import Grid

NODES = TM.Nodes(np.arange(0, 10001, 2500.0), np.arange(0, 10001, 2500.0), [0.0, 2000, 5000, 9000])


def test_weights_reproduce_a_linear_field_and_sum_to_one():
    f = lambda x, y, d: 1e-4 * x - 2e-4 * y + 3e-4 * d  # noqa: E731
    X, Y, D = np.meshgrid(*NODES.axes, indexing="ij")
    m = f(X, Y, D).ravel()
    p = np.random.default_rng(0).uniform([0, 0, 0], [10000, 10000, 9000], (200, 3))
    k, w = NODES.weights(p)
    assert np.allclose(w.sum(1), 1.0)
    assert np.allclose((m[k] * w).sum(1), f(*p.T))
    grid = Grid(np.arange(0, 10001, 500.0), np.arange(0, 10001, 500.0), -np.arange(0, 9001, 500.0), 500.0)
    g = NODES.on_grid(m, grid)
    gx, gy, gd = np.meshgrid(grid.xs, grid.ys, -grid.zs, indexing="ij")
    assert np.allclose(g, f(gx, gy, gd))


def test_second_differences_vanish_on_linear_fields_only():
    D = NODES.second_differences()
    X, Y, Z = np.meshgrid(*NODES.axes, indexing="ij")
    assert np.allclose(D @ (2 * X + Y - Z).ravel(), 0)
    assert np.abs(D @ (X**2).ravel()).max() > 0


def test_separation_removes_origin_time_and_hypocentre_directions():
    # one event, 8 picks: a residual that is a pure origin-time shift is removed entirely
    rng = np.random.default_rng(1)
    grid = Grid(np.arange(0, 4001, 500.0), np.arange(0, 4001, 500.0), -np.arange(0, 4001, 500.0), 500.0)
    gx, gy, gd = np.meshgrid(grid.xs, grid.ys, -grid.zs, indexing="ij")
    T = {
        "P": np.stack(
            [
                np.sqrt((gx - sx) ** 2 + (gy - sy) ** 2 + gd**2) / 5000
                for sx, sy in rng.uniform(0, 4000, (8, 2))
            ]
        )
    }
    pk = pd.DataFrame(
        {"event": "e", "phase": "P", "si": np.arange(8), "row": np.arange(8), "w": 1.0, "res": 0.3}
    )
    cat = pd.DataFrame({"x": [2000.0], "y": [2000.0], "d": [2500.0]}, index=["e"])
    K = sp.csr_matrix(rng.normal(size=(8, 5)))
    A, r, ev = TM.separated(pk, cat, T, grid, K)
    assert A.shape == (8, 5) and np.allclose(r, 0, atol=1e-9) and (ev == "e").all()
    H = np.column_stack(
        [np.stack([grid.grad(T["P"][s], cat.loc[["e"]].values)[0] for s in range(8)]), np.ones(8)]
    )
    assert np.allclose(H.T @ A.toarray(), 0, atol=1e-8)


def test_straight_ray_checkerboard_is_recovered():
    # straight rays through a 2D-like slab, sampled densely: the regularised step recovers the pattern
    nodes = TM.Nodes(np.arange(0, 20001, 2000.0), np.arange(0, 20001, 2000.0), [0.0, 4000.0])
    rng = np.random.default_rng(2)
    a, b = rng.uniform(0, 20000, (3000, 2)), rng.uniform(0, 20000, (3000, 2))
    t = np.linspace(0, 1, 60)[:, None, None]
    pts = a[None] + t * (b - a)[None]
    ln = np.linalg.norm(b - a, axis=1) / 60
    p = np.column_stack([pts.reshape(-1, 2), np.full(pts.shape[0] * pts.shape[1], 2000.0)])
    k, w = nodes.weights(p)
    rows = np.repeat(np.tile(np.arange(3000), 60), 8)
    K = sp.csr_matrix(
        ((-np.tile(ln, 60)[:, None] / 5000 * w).ravel() / 0.05, (rows, k.ravel())), shape=(3000, nodes.n)
    )
    true = TM.checkerboard(nodes, 6000, 0.05)[: nodes.n]
    dm = TM.regularised_step(K, K @ true, np.zeros(nodes.n), nodes.second_differences(), 1e-3, 1e-3)
    assert np.corrcoef(dm, true)[0, 1] > 0.8
