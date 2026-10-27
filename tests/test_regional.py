import numpy as np
import pytest

from rainier3d.fusion.regional import CVM_MAX_DEPTH, crescent_weight


def test_crescent_weight_is_a_smooth_ramp_around_the_base_of_the_cvm_data():
    d = np.linspace(0, 20000, 4001)
    w = crescent_weight(d, (8000, 16000))
    assert np.all(w[d <= 8000] == 0) and np.all(w[d >= 16000] == 1)
    assert np.all(np.diff(w) >= 0)
    # raised cosine: no slope at either end, so neither end of the window is a step
    dw = np.diff(w) / np.diff(d)
    assert max(dw[np.searchsorted(d, 8000)], dw[np.searchsorted(d, 16000) - 1]) < 0.01 * dw.max()
    with pytest.raises(ValueError):
        crescent_weight(d, (6000, CVM_MAX_DEPTH - 100))  # the window must contain the jump
