"""The atlas exporter puts model cells at the right lon/lat on the atlas overview box."""

import numpy as np
from pyproj import Transformer

from rainier3d.config.domain import load_domain
from rainier3d.export.atlas import _values_u16, overview_grid, to_lonlat

MANIFEST = {"extent": {"overview": {"west": -122.16, "south": 46.58, "east": -121.36, "north": 47.12}}}


def test_overview_pixels_square_in_degrees():
    t, w, h = overview_grid(MANIFEST, 2040)
    assert (w, h) == (2040, 1377)
    assert np.isclose(t.a, -t.e)


def test_to_lonlat_places_a_marked_cell():
    dom = load_domain()
    a = np.zeros((dom.y.size, dom.x.size), "float32")
    j, i = 400, 300  # a cell well inside both boxes (rows south to north like dom.y)
    a[j - 2 : j + 3, i - 2 : i + 3] = 7
    out = to_lonlat(a, dom, MANIFEST, 2040, categorical=True)
    lon, lat = Transformer.from_crs(dom.crs, 4326, always_xy=True).transform(dom.x[i], dom.y[j])
    t, _, _ = overview_grid(MANIFEST, 2040)
    c, r = ~t * (lon, lat)
    assert out[int(r), int(c)] == 7
    assert np.isnan(out[:, -5:]).all()  # east of the model domain (-121.40) there is no data


def test_values_roundtrip_within_quantum():
    v = np.array([[0.1, 50.0], [np.nan, 99.9]], "float32")
    q, scale, off = _values_u16(v, False, 0.1, 100)
    back = np.where(q == 65535, np.nan, off + q * scale)
    assert np.allclose(back, v, atol=scale, equal_nan=True)


def test_temporary_networks_follow_fdsn_convention():
    from rainier3d.export.atlas import is_temporary

    for sid in ("XD.A1", "Z5.B2", "2N.1", "TA.K05A"):
        assert is_temporary(sid, "FDSN (EarthScope)")
    for sid in ("UW.RCM", "CC.OBSR", "PB.B941", "NP.1234"):
        assert not is_temporary(sid, "FDSN (EarthScope)")
    assert is_temporary("node-13217", "2025 Rainier node deployment (UW)")
    assert not is_temporary("gnss-P432", "EarthScope GNSS (UNAVCO)")


def test_viewer_kinds():
    from rainier3d.export.atlas import viewer_kind

    assert viewer_kind("geophone node (2025)", "nodes") == "geophone"
    assert viewer_kind("tiltmeter", "strain") == "tiltmeter"
    assert viewer_kind("borehole strainmeter", "strain") == "strainmeter"
    assert viewer_kind("GNSS receiver", "gnss") == "gnss"
    assert viewer_kind("", "meteorology") == "hydromet"
