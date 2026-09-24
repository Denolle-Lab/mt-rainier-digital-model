import numpy as np

from rainier3d.fusion import blend

TABLE = [[0, 6000], [2000, 10000]]


def _setup(shape=(6, 40, 50), seed=0):
    rng = np.random.default_rng(seed)
    mask = np.ones(shape, bool)
    mask[0, :10] = False  # some air
    depth = np.broadcast_to(np.linspace(1500, 4000, shape[0])[:, None, None], shape).copy()
    return rng, mask, depth


def test_identical_inputs_are_unchanged():
    rng, mask, depth = _setup()
    v = 3000 + 500 * rng.random(mask.shape)
    out = blend.fuse(v, v, depth, mask, TABLE, 250.0, 300, 1000)
    assert np.allclose(out[mask], v[mask])
    assert np.isnan(out[~mask]).all()


def test_lowpass_of_constant_is_constant_despite_mask():
    _, mask, depth = _setup()
    lp = blend.lowpass_depth_varying(np.full(mask.shape, 7.0), mask, depth, TABLE, 250.0)
    assert np.allclose(lp[mask], 7.0)


def test_fusion_keeps_regional_long_wavelengths_and_adds_no_extremes():
    rng, mask, depth = _setup(seed=1)
    reg = 5000 + 300 * np.sin(np.arange(50) / 50 * 2 * np.pi)[None, None, :] * np.ones(mask.shape)
    geo = 4000 + 800 * rng.random(mask.shape)
    out = blend.fuse(geo, reg, depth, mask, TABLE, 250.0, 300, 1000)
    lo, hi = np.fmin(geo, reg), np.fmax(geo, reg)
    assert np.all((out[mask] >= lo[mask] * (1 - 1e-6)) & (out[mask] <= hi[mask] * (1 + 1e-6)))
    assert blend.lowpass_misfit(out, reg, depth, mask, TABLE, 250.0, 1000) < 0.05
