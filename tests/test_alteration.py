"""The near-surface alteration model (S22, rainier3d.alteration.finn2001)."""

import numpy as np

from rainier3d.alteration.finn2001 import FREQS, alteration_3d, taper


def test_taper_full_to_doi_then_linear_to_zero():
    doi = np.array(100.0)
    d = np.array([-5.0, 0.0, 50.0, 100.0, 112.5, 125.0, 200.0])
    assert np.allclose(taper(d, doi), [0, 1, 1, 1, 0.5, 0, 0])
    assert taper(np.array(10.0), np.array(0.0)) == 0  # outside the survey


def test_alteration_takes_the_strongest_frequency_at_each_depth_and_respects_units():
    f = {f"alt_a_{k}": np.array([[0.0]]) for k in FREQS} | {f"alt_doi_{k}": np.array([[0.0]]) for k in FREQS}
    f["alt_a_33k"], f["alt_doi_33k"] = np.array([[1.0]]), np.array([[20.0]])  # shallow, strong
    f["alt_a_837"], f["alt_doi_837"] = np.array([[0.4]]), np.array([[150.0]])  # deep, weak
    d = np.array([10.0, 60.0, 180.0, 300.0])[:, None, None]
    a = alteration_3d(f, d, np.ones((1, 1, 1), bool))[:, 0, 0]
    assert np.allclose(a, [1.0, 0.4, 0.4 * (1.25 * 150 - 180) / (0.25 * 150), 0.0])
    assert np.all(alteration_3d(f, d, np.zeros((1, 1, 1), bool)) == 0)
