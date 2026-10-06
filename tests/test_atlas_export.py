"""The atlas exporter puts model cells at the right lon/lat on the atlas overview box."""

import numpy as np
import xarray as xr
from pyproj import Transformer

from rainier3d.config.domain import load_domain
from rainier3d.export.atlas import _values_u16, overview_grid, surface_derived, to_lonlat

MANIFEST = {"extent": {"overview": {"west": -122.16, "south": 46.58, "east": -121.40, "north": 47.12}}}


def test_overview_pixels_square_in_degrees():
    from rainier3d.export.atlas import TEX_WIDTH, VAL_WIDTH

    b = MANIFEST["extent"]["overview"]
    for width in (TEX_WIDTH, VAL_WIDTH, 2 * TEX_WIDTH):
        t, w, h = overview_grid(MANIFEST, width)
        assert np.isclose(t.a, -t.e)
        assert np.isclose(h * t.a, b["north"] - b["south"], rtol=1e-9)  # whole rows end on the south edge


def test_to_lonlat_places_a_marked_cell():
    from rainier3d.export.atlas import TEX_WIDTH

    dom = load_domain()
    a = np.zeros((dom.y.size, dom.x.size), "float32")
    j, i = 400, 300  # a cell well inside both boxes (rows south to north like dom.y)
    a[j - 2 : j + 3, i - 2 : i + 3] = 7
    out = to_lonlat(a, dom, MANIFEST, TEX_WIDTH, categorical=True)
    lon, lat = Transformer.from_crs(dom.crs, 4326, always_xy=True).transform(dom.x[i], dom.y[j])
    t, _, _ = overview_grid(MANIFEST, TEX_WIDTH)
    c, r = ~t * (lon, lat)
    assert out[int(r), int(c)] == 7
    assert np.isfinite(out).all()  # the box lies inside the model domain: data up to every edge


def test_check_overview_stops_on_a_box_outside_the_model():
    import pytest

    from rainier3d.export.atlas import check_overview

    dom = load_domain()
    check_overview(MANIFEST, dom)
    first = {"extent": {"overview": {**MANIFEST["extent"]["overview"], "east": -121.36}}}  # the first box
    with pytest.raises(ValueError, match="not inside the model grid"):
        check_overview(first, dom)


def test_surface_derived_keeps_l1_cells_in_place():
    # 250 m L1 cells on the 100 m surface grid (not a whole factor): the map keeps the surface grid's shape
    # and each surface cell holds the L1 cell around its centre (cells centred on an L1 edge take either side)
    xs, x1 = np.arange(50.0, 1000, 100), np.arange(125.0, 1000, 250)
    vs = np.add.outer(10 * np.arange(4), np.arange(4)).astype("float32")  # L1 cell (j, i) holds 10 j + i
    cube = lambda a: (("z", "y", "x"), a[None])  # noqa: E731
    l1 = xr.Dataset(
        {
            "depth": cube(np.full((4, 4), 50.0)),
            "unit": cube(np.full((4, 4), 6)),
            "vs": cube(vs),
            "alteration": cube(np.zeros((4, 4))),
        },
        coords={"z": [0.0], "y": x1, "x": x1},
    )
    surface = xr.Dataset({"elev": (("y", "x"), np.zeros((10, 10)))}, coords={"y": xs, "x": xs})
    out = surface_derived(xr.DataTree.from_dict({"/surface": surface, "/L1": l1}))["vs_top"]
    assert out.shape == (10, 10)
    k, inner = (xs // 250).astype(int), xs % 250 != 0
    assert np.array_equal(out[np.ix_(inner, inner)], vs[np.ix_(k[inner], k[inner])])


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
    assert not is_temporary("gnss-P432", "EarthScope GNSS (UNAVCO)")


def test_viewer_kinds():
    from rainier3d.export.atlas import viewer_kind

    assert viewer_kind("geophone node (2025)", "nodes") == "geophone"
    assert viewer_kind("tiltmeter", "strain") == "tiltmeter"
    assert viewer_kind("borehole strainmeter", "strain") == "strainmeter"
    assert viewer_kind("GNSS receiver", "gnss") == "gnss"
    assert viewer_kind("", "meteorology") == "hydromet"


def test_surveys_tag_their_sites_and_the_das_fiber():
    import yaml

    from rainier3d.config.domain import REPO
    from rainier3d.export.atlas import apply_surveys

    meta = {"sites": [{"id": "Z5.001"}, {"id": "2N.1"}, {"id": "UW.RCM"}, {"id": "gnss-P432"}], "das": {}}
    apply_surveys(meta)
    assert [s["survey"] for s in meta["sites"]] == ["nodes_2025", None, None, None]
    assert meta["das"]["survey"] == "mora_das"
    assert [s["key"] for s in meta["surveys"]] == ["nodes_2025", "mora_das"]
    reg = yaml.safe_load((REPO / "configs" / "sources.yaml").read_text())
    cfg = yaml.safe_load((REPO / "configs" / "sensor_surveys.yaml").read_text())
    assert all(v["source"] in reg for v in cfg.values())  # every survey names a registry key


def test_retired_kinds_at_a_running_site():
    from rainier3d.export.atlas import retired_kinds

    pr01 = [  # CC.PR01: the broadband runs, the infrasound microphone ended in 2020
        {"family": "seismic", "kind": "broadband seismometer", "status": "operating", "start": "2016-11-03"},
        {
            "family": "infrasound",
            "kind": "infrasound microphone",
            "status": "retired",
            "start": "2018-10-04",
            "end": "2020-06-08",
        },
    ]
    assert retired_kinds(pr01, "seismic") == {"infrasound": ["2018-10-04", "2020-06-08"]}
    assert retired_kinds([dict(pr01[1])], "infrasound") == {}  # a past site: nothing singled out
