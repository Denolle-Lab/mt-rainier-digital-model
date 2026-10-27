"""Roughness measures (rainier3d.report.roughness)."""

import numpy as np
import pytest
import xarray as xr

from rainier3d.report.roughness import continuity


def _level(z, xy, a, b):
    lv = a + b * z[:, None, None] * np.ones((1, xy.size, xy.size))
    return xr.Dataset({"vs": (("z", "y", "x"), np.exp(lv))}, coords={"z": z, "y": xy, "x": xy})


def test_continuity_of_levels_that_agree_and_of_a_step():
    # ln Vs linear in z across both levels: the change over the gap is the gradient's prediction
    z2, z3 = np.arange(-125.0, -6000, -250), np.arange(-6500.0, -20000, -1000)
    xy2, xy3 = np.arange(250.0, 5000, 500), np.arange(500.0, 5000, 1000)
    l2, l3 = _level(z2, xy2, 8.0, -2e-5), _level(z3, xy3, 8.0, -2e-5)
    c = continuity(l2, l3, variables=("vs",))
    assert c["gap_m"] == 625.0
    assert c["vs"]["change_median"] == pytest.approx(2e-5 * 625)
    assert c["vs"]["residual_median"] == pytest.approx(0.0, abs=1e-12)
    # L3 0.01 faster than L2 continued: the residual is the step
    c = continuity(l2, _level(z3, xy3, 8.01, -2e-5), variables=("vs",))
    assert c["vs"]["residual_median"] == pytest.approx(0.01)
    with pytest.raises(ValueError):
        continuity(l2.isel(z=slice(None, None, -1)), l3, variables=("vs",))
