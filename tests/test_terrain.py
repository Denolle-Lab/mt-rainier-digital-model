"""S30 terrain-geometry operators on synthetic surfaces, and the viewer export (no network, no model data)."""

from __future__ import annotations

import json

import geopandas as gpd
import numpy as np
import pytest
import xarray as xr
from shapely.geometry import Point, box

from rainier3d.config.domain import load_domain
from rainier3d.surface import terrain as T

DX = 30.0


def _xy(n=121):
    c = (np.arange(n) - n // 2) * DX
    return np.meshgrid(c, c)  # X east, Y north; rows south to north


def test_planar_slope_gives_its_angle():
    x, y = _xy()
    for deg, az in ((12.0, 0.3), (35.0, 2.0), (55.0, 4.0)):
        k = np.tan(np.radians(deg))
        z = k * (np.cos(az) * x + np.sin(az) * y)
        s = T.slope_deg(z, DX)
        assert np.allclose(s[1:-1, 1:-1], deg, atol=1e-4)


def test_slope_uses_the_60_m_baseline():
    # a 1-cell spike: its neighbours see (spike - 0) / 60 m, the spike itself sees 0
    z = np.zeros((9, 9))
    z[4, 4] = 60.0
    s = T.slope_deg(z, DX)
    assert s[4, 4] == pytest.approx(0.0)
    assert s[4, 3] == pytest.approx(45.0)


def test_disk_halfwidths():
    hw = T.disk_halfwidths(17.0)  # the 510 m disk on 30 m cells
    assert hw.size == 35 and hw[17] == 17 and hw[0] == 0 and hw[1] == 5
    assert T.disk_halfwidths(33.0).size == 67


def test_disk_filter_matches_brute_force():
    rng = np.random.default_rng(1)
    z = rng.normal(size=(40, 37))
    r = 4.5
    zp = np.pad(z, 5, mode="symmetric")
    ii, jj = np.mgrid[-5:6, -5:6]
    fp = ii**2 + jj**2 <= r**2
    want = np.array(
        [[zp[i : i + 11, j : j + 11][fp].max() for j in range(z.shape[1])] for i in range(z.shape[0])]
    )
    assert np.allclose(T.disk_filter(z, r, "max"), want)


def test_cone_relief_is_the_drop_within_the_radius():
    x, y = _xy(161)
    k, h = 0.4, 3000.0  # 21.8 degree cone
    z = h - k * np.hypot(x, y)
    rel = T.local_relief(z, 510.0, DX)
    c = z.shape[0] // 2
    assert rel[c, c] == pytest.approx(k * 510.0, rel=1e-6)  # at the apex: max z - z at 510 m
    # on the flank, far from the apex, the window spans 2R along the fall line
    assert rel[c, c + 40] == pytest.approx(k * 2 * 510.0, rel=1e-6)


def test_v_trench_valley_depth_equals_its_depth():
    x, y = _xy(161)
    d, k = 200.0, 1.0  # 200 m deep, 45 degree walls: 400 m wide at the top, narrower than the 1980 m disk
    z = 1000.0 + np.minimum(d, k * np.abs(x))
    vd = T.valley_depth(z, 990.0, DX)
    c = z.shape[1] // 2
    assert vd[:, c] == pytest.approx(np.full(z.shape[0], d))
    assert np.allclose(vd[:, np.abs(x[0]) >= d / k], 0.0)  # the plain has no depth
    assert (vd >= 0).all()


def test_trench_wider_than_the_disk_is_not_filled():
    x, y = _xy(161)
    z = np.where(np.abs(x) < 1500.0, 0.0, 300.0)  # flat-floored trench 3 km wide
    vd = T.valley_depth(z, 990.0, DX)
    assert vd[:, z.shape[1] // 2].max() == pytest.approx(0.0)


def test_bedrock_slope_equals_surface_slope_off_ice():
    x, y = _xy()
    z = 2000.0 + 0.3 * x + 1e-4 * y**2
    ice = np.clip(150.0 - np.hypot(x - 300, y) / 4, 0, None)  # a 600 m ice cap
    s, b = T.slope_deg(z, DX), T.slope_deg(z - ice, DX)
    from scipy.ndimage import binary_dilation

    near = binary_dilation(ice > 0)  # the 3-cell stencil reaches one cell beyond the ice
    assert np.array_equal(s[~near], b[~near])
    assert not np.allclose(s[ice > 0], b[ice > 0])


def _ds(dom, res=1000.0):
    x, y, _ = T.grid(dom, res)
    X, Y = np.meshgrid(x, y)
    zz = (4000.0 - 0.05 * np.hypot(X - dom.summit_xy[0], Y - dom.summit_xy[1])).astype("float32")
    z = xr.DataArray(zz, dims=("y", "x"), coords={"y": y, "x": x})
    # source cell centres inside the grid, as for the 100 m model grid: the edges are extrapolated
    ice = xr.DataArray(np.zeros((3, 3)), dims=("y", "x"), coords={"y": y[[2, 5, -3]], "x": x[[2, 5, -3]]})
    cfg = {"grid": {"res_m": res}, "local_relief": {"radius_m": 3000}, "valley_depth": {"radius_m": 5000}}
    return T.build(dom, z, ice, cfg)


def test_build_and_compare():
    dom = load_domain()
    ds = _ds(dom)
    assert set(T.LAYERS) <= set(ds.data_vars)
    assert not any(np.isnan(ds[k].values).any() for k in ds.data_vars)
    assert ds["surface_slope"].attrs["gaia:source_keys"] == "usgs_3dep,han_terrain_2026"
    assert np.array_equal(ds["surface_slope"].values, ds["bedrock_slope"].values)
    sx, sy = dom.summit_xy
    ev = gpd.GeoDataFrame(
        {"cls": ["slide", "slide", "complex"], "located": ["mapped", "mapped", "seismic"]},
        geometry=[Point(sx, sy), Point(sx + 5000, sy), Point(0, 0)],
        crs=dom.crs,
    )
    fl = gpd.GeoDataFrame({"cls": [4]}, geometry=[box(sx, sy, sx + 3000, sy + 3000)], crs=dom.crs)
    th = {k: 1.0 for k in T.LAYERS}
    tab, off = T.compare(ds, ev, fl, th, [("slide", "Slide", "#000")], [(4, "Debris flows", "#000")])
    assert off == 1
    assert list(tab.group) == ["whole domain", "all events", "Slide", "Debris flows"]
    assert tab.set_index("group").loc["Debris flows", "n_cells"] == 9


def test_append_terrain_layers(tmp_path):
    from rainier3d.export.atlas import append_terrain_layers

    dom = load_domain()
    ds = _ds(dom)
    lon0, lat0, lon1, lat1 = dom.bbox_4326
    (tmp_path / "model").mkdir()
    (tmp_path / "manifest.json").write_text(
        json.dumps({"extent": {"overview": {"west": lon0, "east": lon1, "south": lat0, "north": lat1}}})
    )
    (tmp_path / "model" / "layers.json").write_text(json.dumps({"layers": [{"key": "geology"}]}))
    keys = append_terrain_layers(tmp_path, dom, ds)
    assert keys == list(T.LAYERS)
    meta = json.loads((tmp_path / "model" / "layers.json").read_text())
    assert [x["key"] for x in meta["layers"]] == ["geology", *T.LAYERS]
    for e in meta["layers"][1:]:
        assert e["group"] == "Terrain geometry" and e["sources"]
        assert (tmp_path / "model" / e["texture"]).exists()
        q = np.fromfile(tmp_path / "model" / e["values"]["file"], "<u2")
        assert q.size == e["values"]["width"] * e["values"]["height"] and (q != 65535).any()
    assert append_terrain_layers(tmp_path, dom, ds) == keys  # idempotent: entries replaced, not repeated
    assert len(json.loads((tmp_path / "model" / "layers.json").read_text())["layers"]) == 5
