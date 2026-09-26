"""Viewer colour stretch: byte-space percentiles match the value percentiles, rounded outward to the step."""

import numpy as np

from rainier3d.export.atlas import _stretch


def test_stretch_matches_value_percentiles():
    rng = np.random.default_rng(0)
    q = rng.integers(0, 255, size=200_000).astype(np.uint8)
    q[:1000] = 255  # air is ignored
    vmin, vmax = 1500.0, 7200.0
    lut, lo, hi = _stretch(q, vmin, vmax, "cmc.roma", (2, 98), 50.0)
    v = vmin + q[q < 255] * (vmax - vmin) / 254
    p_lo, p_hi = np.percentile(v, (2, 98))
    step = (vmax - vmin) / 254
    assert p_lo - 50 - step <= lo <= p_lo + step and lo % 50 == 0
    assert p_hi - step <= hi <= p_hi + 50 + step and hi % 50 == 0
    assert len(lut) == 256
    assert lut[0] == lut[1]  # below lo the colour saturates
