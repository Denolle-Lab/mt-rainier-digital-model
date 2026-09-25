"""GNSS velocity and strain: synthetic checks against known answers."""

import numpy as np

from rainier3d.geodesy.strain import components, strain_grid, uniform_strain
from rainier3d.geodesy.velocity import midas


def test_midas_recovers_trend_through_seasonal_signal_and_a_step():
    t = np.arange(2015, 2025, 1 / 365.25)
    x = 0.004 * (t - 2015) + 0.003 * np.sin(2 * np.pi * t) + np.where(t > 2019.5, 0.02, 0.0)
    v, s, n = midas(t, x + np.random.default_rng(0).normal(0, 0.001, t.size), steps=np.array([2019.5]))
    assert abs(v - 0.004) < 2e-4 and n > 2000


def test_strain_grid_recovers_uniform_field():
    rng = np.random.default_rng(1)
    xy = rng.uniform(-50e3, 50e3, (40, 2))
    L = np.array([[2e-8, 1e-8], [3e-8, -1e-8]])  # 1/yr
    v = xy @ L.T + 0.002
    out, _ = strain_grid(xy, v, np.full(v.shape, 1e-4), np.array([[0.0, 0.0], [10e3, -5e3]]))
    assert np.allclose(out["dilatation"], 1e-8, atol=1e-12)
    assert np.allclose(out["exy"], 2e-8, atol=1e-12)
    assert np.allclose(out["rotation"], 1e-8, atol=1e-12)


def test_components_pure_shear_and_azimuth():
    c = components(1.0, -1.0, 0.0, 0.0)
    assert c["dilatation"] == 0 and c["max_shear"] == 1 and c["e1"] == 1 and c["azimuth"] == 90.0  # e1 east
    assert components(0.0, 0.0, 1.0, 0.0)["azimuth"] == 45.0


def test_uniform_strain_from_displacements():
    xy = np.array([[0, 0], [10e3, 0], [0, 10e3], [10e3, 10e3], [5e3, 3e3]], float)
    u = xy * 1e-6  # isotropic expansion
    c = uniform_strain(xy, u, np.full(u.shape, 1e-3))
    assert np.isclose(c["dilatation"], 2e-6) and np.isclose(c["max_shear"], 0, atol=1e-12)


def _one_load(P=1e12):
    return np.array([0.0]), np.array([0.0]), np.array([P]), 0.0


def test_boussinesq_vertical_force_balance():
    """The vertical stress integrated over a buried plane carries the whole load: sum(s_zz dA) = -P."""
    from rainier3d.geodesy.load import stress_at

    P, z, h = 1e12, 2000.0, 200.0
    g = np.arange(-60e3, 60e3 + h, h)
    X, Y = np.meshgrid(g, g)
    pts = np.c_[X.ravel(), Y.ravel(), np.full(X.size, -z)]
    s = stress_at(pts, _one_load(P), min_depth_m=0)
    assert abs(s[:, 2].sum() * h * h / -P - 1) < 0.01


def test_boussinesq_equilibrium_and_axis_limit():
    """div(sigma) = 0 off the axis (finite differences), and the on-axis branch matches the r -> 0 limit."""
    from rainier3d.geodesy.load import stress_at

    ld, x0, d = _one_load(), np.array([700.0, -400.0, -1500.0]), 1.0
    f = lambda p: stress_at(np.atleast_2d(p), ld, min_depth_m=0)[0]  # noqa: E731
    ex, ey, ez = np.eye(3) * d
    # z is elevation here (depth = -z), so d/d(depth) = -d/dz
    dxx = (f(x0 + ex)[0] - f(x0 - ex)[0]) / (2 * d)
    dxy_y = (f(x0 + ey)[3] - f(x0 - ey)[3]) / (2 * d)
    dxz_z = -(f(x0 + ez)[4] - f(x0 - ez)[4]) / (2 * d)
    scale = abs(f(x0)[2]) / 1000.0
    assert abs(dxx + dxy_y + dxz_z) < 1e-4 * scale
    on, near = f([0.0, 0.0, -1500.0]), f([0.01, 0.0, -1500.0])
    assert np.allclose(on[:3], near[:3], rtol=1e-4)


def test_trajectory_removes_steps_and_references_epoch():
    from rainier3d.geodesy.velocity import trajectory

    t = np.arange(2016, 2024, 1 / 365.25)
    x = 0.01 + 0.003 * (t - 2015) + 0.002 * np.sin(2 * np.pi * t) + np.where(t > 2020.3, -0.015, 0)
    f = trajectory(t, x, steps=[2020.3])
    assert abs(f["b"] - 0.003) < 1e-6 and abs(f["steps"][2020.3] + 0.015) < 1e-6
    assert np.allclose(f["corrected"], 0.003 * (t - 2015) + 0.002 * np.sin(2 * np.pi * t) - 0.0, atol=1e-6)


def test_fetch_streams_and_manifest_is_relative(tmp_path, monkeypatch):
    """fetch writes the streamed bytes, records the path relative to the manifest, and verify_manifest finds
    the file from any working directory (and flags it once its bytes change)."""
    from rainier3d.geodesy import archive as A

    class Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def raise_for_status(self):
            pass

        def iter_content(self, n):
            yield b"abc"
            yield b"def"

    monkeypatch.setattr(A.requests, "get", lambda *a, **k: Resp())
    man = tmp_path / "gnss" / "manifest.csv"
    p = A.fetch("https://example.org/x.txt", tmp_path / "gnss" / "unr" / "x.txt", "unr", man)
    assert p.read_bytes() == b"abcdef" and not p.with_name("x.txt.part").exists()
    assert "unr/x.txt" in man.read_text() and str(tmp_path) not in man.read_text()
    monkeypatch.chdir(tmp_path.parent)
    assert A.verify_manifest(man) == []
    p.write_bytes(b"changed")
    assert A.verify_manifest(man) == [str(p.resolve())]


def test_gnss_config_sections_have_registered_source_keys():
    """configs/gnss.yaml names the provenance of every section, and every key is in configs/sources.yaml."""
    import yaml

    from rainier3d.config.domain import REPO

    cfg = yaml.safe_load((REPO / "configs" / "gnss.yaml").read_text())
    reg = yaml.safe_load((REPO / "configs" / "sources.yaml").read_text())
    keys = cfg["source_keys"]
    assert {"archives", "min_years", "qc", "strain", "regions", "events", "load"} <= set(keys)
    assert [k for ks in keys.values() for k in ks if k not in reg] == []
