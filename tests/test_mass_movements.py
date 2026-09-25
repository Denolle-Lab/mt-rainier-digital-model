"""Mass-movement catalogue (S24): event classes, crown points, and the viewer export on a synthetic bundle."""

import json

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import Point, box

from rainier3d.surface.mass_movements import EVENT_CLASSES, FLOW_CLASSES, _event_class, crown_points


def test_event_classes():
    assert _event_class("rock fall, rock and ice avalanche") == "rock_avalanche"
    assert _event_class("ice avalanche") == "snow_ice_avalanche"
    assert _event_class("snow avalanche") == "snow_ice_avalanche"
    assert _event_class("outburst flood, debris flow") == "debris_flow"
    assert _event_class("Debris slide and avalanches") == "slide"
    assert _event_class("Slide-Rotational") == "slide"
    assert _event_class("Block fall or topple") == "rock_avalanche"
    assert _event_class("Unknown") == "complex"
    assert _event_class(float("nan")) == "complex"
    assert {k for k, _, _ in EVENT_CLASSES} >= {
        "rock_avalanche",
        "snow_ice_avalanche",
        "debris_flow",
        "slide",
    }


def test_crown_is_the_highest_boundary_point(tmp_path):
    # a DEM rising to the north (EPSG:32610, 10 m cells): the crown of a square is on its north edge
    n = 100
    z = np.repeat(np.arange(n, 0, -1, dtype="float32")[:, None], n, axis=1) * 10.0
    dem = tmp_path / "dem.tif"
    with rasterio.open(
        dem,
        "w",
        driver="GTiff",
        width=n,
        height=n,
        count=1,
        dtype="float32",
        crs="EPSG:32610",
        transform=from_origin(590000, 5190000, 10, 10),
    ) as r:
        r.write(z, 1)
    sq = gpd.GeoSeries([box(590200, 5189200, 590400, 5189600)], crs="EPSG:32610")
    p = crown_points(sq, dem).iloc[0]
    assert np.isclose(p.y, 5189600)


def test_append_mass_movements_writes_layer_and_points(tmp_path):
    from rainier3d.export.atlas import append_mass_movements

    atlas = tmp_path / "atlas"
    (atlas / "model").mkdir(parents=True)
    (atlas / "terrain").mkdir()
    ov = {"west": -122.16, "south": 46.58, "east": -121.36, "north": 47.12}
    (atlas / "manifest.json").write_text(json.dumps({"extent": {"overview": ov}}))
    # a terrain grid whose frame puts LON0, LAT0 at the summit (as the viewer builder does)
    kx, kz = 111.32 * np.cos(np.radians(46.8528)), 111.13
    x0, z0 = (ov["west"] + 121.7604) * kx, -(ov["north"] - 46.8528) * kz
    cols, rows = 1800, 1215
    (atlas / "terrain" / "terrain.json").write_text(
        json.dumps(
            {
                "cols": cols,
                "rows": rows,
                "x0": x0,
                "z0": z0,
                "dx": (ov["east"] - ov["west"]) * kx / cols,
                "dz": (ov["north"] - ov["south"]) * kz / rows,
            }
        )
    )
    (atlas / "model" / "layers.json").write_text(json.dumps({"layers": [{"key": "mass_flows", "old": 1}]}))
    flows = gpd.GeoDataFrame(
        {"cls": [1, 4], "name": ["Osceola Mudflow", "debris flow"]},
        geometry=[box(-121.8, 46.9, -121.7, 47.0), box(-121.75, 46.8, -121.74, 46.81)],
        crs=4326,
    ).to_crs(32610)
    events = gpd.GeoDataFrame(
        {
            "cls": ["rock_avalanche"],
            "name": ["Nisqually 1"],
            "date": ["2011-06-24"],
            "located": ["seismic"],
            "source": ["allstadt_2017_esec"],
            "volume_m3": [np.nan],
        },
        geometry=[Point(-121.7604, 46.8528)],
        crs=4326,
    ).to_crs(32610)
    r = append_mass_movements(atlas, flows, events)
    assert r == {
        "flows": 2,
        "events": 1,
        "counts": {k: int(k == "rock_avalanche") for k, _, _ in EVENT_CLASSES},
    }
    layers = json.loads((atlas / "model" / "layers.json").read_text())["layers"]
    assert [x["key"] for x in layers] == ["mass_flows"] and "old" not in layers[0]  # replaced, not duplicated
    assert [c["value"] for c in layers[0]["legend"]["classes"]] == [1, 4]
    assert {c["value"] for c in layers[0]["legend"]["classes"]} <= {k for k, _, _ in FLOW_CLASSES}
    v = layers[0]["values"]
    q = np.fromfile(atlas / "model" / v["file"], "<u2").reshape(v["height"], v["width"])
    assert set(np.unique(q)) == {1, 4, 65535}
    doc = json.loads((atlas / "model" / "mass_events.json").read_text())
    e = doc["events"][0]
    assert abs(e["x"]) < 1e-3 and abs(e["z"]) < 1e-3  # the summit is the scene origin
    assert e["volume_m3"] is None  # NaN becomes null in JSON
    assert doc["sources"]["allstadt_2017_esec"]["link"].startswith("https://doi.org/")


def test_failed_window_falls_back_to_30m_and_is_flagged(tmp_path, monkeypatch):
    import rainier3d.surface.mass_movements as M
    from rainier3d.config.domain import load_domain

    n = 100
    z = np.repeat(np.arange(n, 0, -1, dtype="float32")[:, None], n, axis=1) * 10.0
    dem = tmp_path / "dem30.tif"
    with rasterio.open(
        dem,
        "w",
        driver="GTiff",
        width=n,
        height=n,
        count=1,
        dtype="float32",
        crs="EPSG:32610",
        transform=from_origin(590000, 5190000, 10, 10),
    ) as r:
        r.write(z, 1)
    polys = gpd.GeoSeries([box(590200, 5189200, 590400, 5189600)], crs="EPSG:32610")
    src = gpd.GeoDataFrame(
        {"dem_res": ["1m"]}, geometry=[box(589000, 5188000, 592000, 5191000)], crs="EPSG:32610"
    )
    monkeypatch.setattr(M, "fetch_crown_dems", lambda dom, p, keys: [None])
    pts, res = M._crowns(load_domain(), polys, ["deposit_1"], dem, src)
    assert np.isclose(pts.iloc[0].y, 5189600)
    assert res == ["3DEP 30 m (window failed)"]
    monkeypatch.setattr(M, "fetch_crown_dems", lambda dom, p, keys: [dem])  # a window that worked
    pts, res = M._crowns(load_domain(), polys, ["deposit_1"], dem, src)
    assert res == ["3DEP 1m"]
