"""S31 operators (rainier3d.alteration.packwood) on synthetic grids, and the viewer export (no network, no
survey data)."""

from __future__ import annotations

import json

import numpy as np
import pytest
import xarray as xr
from scipy.ndimage import gaussian_filter

from rainier3d.alteration import packwood as P
from rainier3d.config.domain import load_domain
from rainier3d.io.store import provenance

DX = 100.0


def _grid(a, x0=550000.0, y0=5150000.0):
    ny, nx = a.shape
    return xr.DataArray(
        a, dims=("y", "x"), coords={"y": y0 + DX * np.arange(ny), "x": x0 + DX * np.arange(nx)}
    )


def _smooth(shape, sigma, seed):
    return gaussian_filter(np.random.default_rng(seed).normal(size=shape), sigma)


def test_read_grid_puts_the_first_gxf_row_in_the_south(tmp_path):
    # SENSE 1: the first row of #GRID is the southern one; -1e32 is the null value
    rows = ["1 2 3", "4 -1e32 6"]
    head = {"POINTS": 3, "ROWS": 2, "PTSEPARATION": 100, "RWSEPARATION": 100, "XORIGIN": 554700,
            "YORIGIN": 5136200, "ROTATION": 0, "SENSE": 1, "DUMMY": -1e32}  # fmt: skip
    text = "".join(f"#{k}\n{v}\n" for k, v in head.items()) + "#GRID\n" + "\n".join(rows) + "\n"
    path = tmp_path / "g.gxf"
    path.write_text(text)
    g = P.read_grid(path)
    assert g.y.values.tolist() == [5136200.0, 5136300.0] and g.x.values[0] == 554700.0
    assert g.values[0].tolist() == [1.0, 2.0, 3.0]
    assert g.values[1, 0] == 4.0 and np.isnan(g.values[1, 1])


def test_harmonic_fill_is_exact_on_a_plane():
    Y, X = np.mgrid[0:30, 0:40].astype(float)
    a = 3.0 * X - 2.0 * Y + 7.0
    holed = a.copy()
    holed[8:20, 10:25] = np.nan
    assert np.allclose(P.harmonic_fill(holed), a)


def test_reduction_to_pole_at_the_pole_only_removes_the_mean():
    a = _smooth((60, 70), 4, 0) * 100
    holed = a.copy()
    holed[20:30, 25:40] = np.nan
    r = P.reduce_to_pole(_grid(holed), 90.0, 0.0, 0.33).values
    ok = np.isfinite(holed)
    assert np.isnan(r[~ok]).all()
    # vertical field and magnetisation: the identity, up to the level (the zero wavenumber)
    assert np.allclose(r[ok] - r[ok].mean(), holed[ok] - holed[ok].mean(), atol=1e-6 * np.abs(a).max())


def test_terrain_effect_matches_harmonica_and_its_tiles():
    import harmonica as hm

    ny, nx, R = 12, 14, 30
    x, y = 550000.0 + DX * np.arange(nx), 5150000.0 + DX * np.arange(ny)
    top = 1500.0 + 300.0 * _smooth((ny, nx), 2, 1) / _smooth((ny, nx), 2, 1).std()  # all above 0 m
    h = top + 200.0
    need = np.ones(top.shape, bool)
    need[0, 0] = False
    one = P.terrain_effect(top, x, y, h, need, reach_m=R * DX, tile=50)  # one tile: every prism
    # brute force: all prisms of the edge-padded grid
    t = np.pad(top, R, mode="edge")
    PX, PY = np.meshgrid(x[0] + DX * np.arange(-R, nx + R), y[0] + DX * np.arange(-R, ny + R))
    pr = np.column_stack([PX.ravel() - DX / 2, PX.ravel() + DX / 2, PY.ravel() - DX / 2, PY.ravel() + DX / 2,
                          np.zeros(t.size), t.ravel()])  # fmt: skip
    X, Y = np.meshgrid(x, y)
    n = len(pr)
    want = hm.prism_magnetic((X[need], Y[need], h[need]), pr, (np.zeros(n), np.zeros(n), np.ones(n)), "b_u")
    assert np.allclose(one[need], want) and np.isnan(one[0, 0])
    # tiles of 5 cells leave out the prisms more than the reach beyond them: here (a 1.5 km plateau 3 km
    # away) a few percent of G; an indexing error would change it by its whole size
    tiled = P.terrain_effect(top, x, y, h, need, reach_m=R * DX, tile=5)
    assert np.abs(tiled[need] - one[need]).max() < 0.1 * np.abs(one[need]).max()


def test_local_slope_recovers_the_magnetisation():
    G = 50.0 * _smooth((80, 90), 3, 2) / _smooth((80, 90), 3, 2).std()
    d = 2.5 * G + 40.0
    d[30:35, 40:45] = np.nan
    M = P.local_slope(d, G, DX, 500.0)
    ok = np.isfinite(M)
    assert ok.mean() > 0.9 and np.isnan(M[32, 42])
    assert np.allclose(M[ok], 2.5, atol=1e-6)


def test_blend_ramps_across_the_overlap():
    n = 61
    inner = np.full((n, n), np.nan)
    inner[10:51, 10:51] = 1.0  # the 1996 footprint
    inner[30, 30] = np.nan  # a cell with no data from either survey
    inner[15, 30] = np.nan  # a one-cell gap of the footprint in the overlap
    outer = np.full((n, n), 3.0)
    outer[20:41, 20:41] = np.nan  # the 2022 gap
    merged, w = P.blend(inner, outer)
    only_inner = np.isfinite(inner) & np.isnan(outer)
    assert (w[only_inner] == 1).all() and (merged[only_inner] == 1.0).all()
    assert (merged[:10] == 3.0).all() and (w[:10] == 0).all()
    row = merged[35, 41:51]  # from the gap edge to the footprint edge
    assert np.all(np.diff(row) > 0) and row[0] < 1.3 and row[-1] > 2.7  # 1 -> 3, no step at either edge
    assert np.isnan(merged[30, 30]) and merged[15, 30] == 3.0
    assert w[16, 30] > 0.5  # the one-cell gap is not taken for the edge of the footprint
    assert w[10, 30] < 0.1  # the edge of the footprint is


def test_append_magnetization_layers(tmp_path):
    from rainier3d.export.atlas import MAGNETIZATION_LAYERS, append_magnetization_layers

    dom = load_domain()
    X, Y = np.meshgrid(dom.x, dom.y)
    v = np.where(np.hypot(X - dom.summit_xy[0], Y - dom.summit_xy[1]) < 20000, 1.5, np.nan).astype("float32")
    keys = ["rystrom_2000", "finn_2001", "blakely_2024", "igrf13", "usgs_3dep"]
    ds = xr.Dataset(
        {
            k: provenance(xr.DataArray(v, dims=("y", "x"), coords={"y": dom.y, "x": dom.x}), keys, k, 100.0)
            for k in MAGNETIZATION_LAYERS
        },  # fmt: skip
        attrs={"window_sigma_m_1996": 500.0, "window_sigma_m_2022": 1000.0},
    )
    lon0, lat0, lon1, lat1 = dom.bbox_4326
    (tmp_path / "model").mkdir()
    (tmp_path / "manifest.json").write_text(
        json.dumps({"extent": {"overview": {"west": lon0, "east": lon1, "south": lat0, "north": lat1}}})
    )
    (tmp_path / "model" / "layers.json").write_text(
        json.dumps({"layers": [{"key": "apparent_magnetization"}]})
    )
    legend = {"vmin": -1, "vmax": 5, "cmap": "cmc.vik"}
    assert append_magnetization_layers(tmp_path, dom, ds, legend) == list(MAGNETIZATION_LAYERS)
    meta = json.loads((tmp_path / "model" / "layers.json").read_text())
    assert [x["key"] for x in meta["layers"]] == ["apparent_magnetization", *MAGNETIZATION_LAYERS]
    for e in meta["layers"][1:]:
        assert e["group"] == "Geology" and e["units"] == "A/m"
        assert "~80 m above ground, 500 m window" in e["note"] and "~700 m, 1 km window" in e["note"]
        assert [s["key"] for s in e["sources"]] == keys
        assert next(s for s in e["sources"] if s["key"] == "blakely_2024")["license"] == "public domain"
        assert (tmp_path / "model" / e["texture"]).exists()
        q = np.fromfile(tmp_path / "model" / e["values"]["file"], "<u2")
        assert q.size == e["values"]["width"] * e["values"]["height"] and (q != 65535).any()
        assert e["values"]["offset"] + e["values"]["scale"] * np.median(q[q != 65535]) == pytest.approx(
            1.5, abs=1e-3
        )
    append_magnetization_layers(tmp_path, dom, ds, legend)  # idempotent: entries replaced, not repeated
    assert len(json.loads((tmp_path / "model" / "layers.json").read_text())["layers"]) == 3
    # one layer only, as S11 --layers passes it: the other stays as it is
    one = list(MAGNETIZATION_LAYERS)[1]
    assert append_magnetization_layers(tmp_path, dom, ds[[one]], legend) == [one]
    assert len(json.loads((tmp_path / "model" / "layers.json").read_text())["layers"]) == 3
    with pytest.raises(KeyError, match="window_sigma_m"):  # S31 writes the windows; no silent 0 m
        append_magnetization_layers(tmp_path, dom, ds.drop_attrs(), legend)
