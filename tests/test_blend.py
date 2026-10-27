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


def test_vertical_lowpass_spreads_a_flat_contact_below_the_geology_only_depth():
    # a slow body 1 km wide (shorter than lambda_c, so the fusion keeps it) with a flat base at 1400 m below
    # the ground, 50 m cells; the regional model is uniform
    nz, dz, n = 60, 50.0, 40
    depth = np.broadcast_to((25 + dz * np.arange(nz))[:, None, None], (nz, n, n)).copy()
    mask = np.ones(depth.shape, bool)
    body = np.zeros((n, n), bool)
    body[18:22, 18:22] = True
    geo = np.where((depth < 1400) & body, 2000.0, 4000.0)
    reg = np.full(depth.shape, 4000.0)
    sharp = blend.fuse(geo, reg, depth, mask, TABLE, 250.0, 300, 1000)
    kw = {"lambda_z": 1000.0, "dz": dz, "z_smooth": 150.0}
    smooth = blend.fuse(geo, reg, depth, mask, TABLE, 250.0, 300, 1000, **kw)
    jump = lambda v: np.abs(np.diff(np.log(v[:, 20, 20]))).max()  # noqa: E731
    assert jump(sharp) > 0.4  # 2615 -> 4000 m/s between two cells
    assert jump(smooth) < 0.05
    top = depth[:, 0, 0] - dz / 2 < 150  # cells reaching above z_smooth: the geology as is
    assert np.allclose(smooth[top], geo[top])
    # a contact at 600 m, inside the fusion taper, is smoothed too, and the smoothing starts without a step
    geo2 = np.where((depth < 600) & body, 2000.0, 4000.0)
    assert jump(blend.fuse(geo2, reg, depth, mask, TABLE, 250.0, 300, 1000, **kw)) < 0.1


def test_lateral_lowpass_ramps_to_a_finite_cutoff_below_the_critical_zone():
    # a vertical wall between two map units, 250 m cells; the critical zone (above 150 m) stays as built, the
    # cutoff ramps up over a few cells below it to lambda_h0 (no vertical step at the base next to the wall)
    # and the smoothing widens with depth
    nz, dz, dx, n = 20, 50.0, 250.0, 40
    depth = np.broadcast_to((25 + dz * np.arange(nz))[:, None, None], (nz, n, n)).copy()
    mask = np.ones(depth.shape, bool)
    lg = np.log(np.where(np.arange(n)[None, None, :] < n // 2, 3000.0, 4500.0) * np.ones(depth.shape))
    kw = {"z_smooth": 150.0, "lambda_h": 2000.0, "growth_h": 1.0}
    step = lambda f, k: np.abs(np.diff(f[k, n // 2])).max()  # noqa: E731
    zero = blend.smooth_geology(lg, mask, depth, dx, dz, **kw)
    jump = blend.smooth_geology(lg, mask, depth, dx, dz, lambda_h0=750.0, **kw)
    ramp = blend.smooth_geology(lg, mask, depth, dx, dz, lambda_h0=750.0, ramp_h=6.0, **kw)
    k0 = int(np.argmax(depth[:, 0, 0] - dz / 2 >= 150))  # first cell entirely below the critical zone
    assert np.allclose(ramp[:k0], lg[:k0])  # the critical zone untouched
    assert step(zero, k0) > 0.99 * step(lg, k0)  # cutoff 0 at the base: the wall stays
    # vertical step at the base, in the cell next to the wall
    vstep = lambda f: np.abs(f[k0, 0, n // 2] - f[k0 - 1, 0, n // 2])  # noqa: E731
    assert vstep(jump) > 0.1 * step(lg, k0)  # a finite cutoff in the first cell: a step at the base
    assert vstep(ramp) < 0.3 * vstep(jump)
    # the change is spread over the ramp: the largest vertical step below the base is smaller too
    vmax = lambda f: np.abs(np.diff(f[k0 - 1 :, 0, n // 2])).max()  # noqa: E731
    assert vmax(ramp) < 0.75 * vmax(jump)
    k1 = int(np.argmax(depth[:, 0, 0] >= 400))  # 250 m below the base, past the ramp
    assert step(ramp, k1) < 0.9 * step(zero, k1)
    assert all(step(ramp, k) >= step(ramp, k + 1) - 1e-12 for k in range(k0, nz - 1))  # widens with depth