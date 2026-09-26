"""S29: events on the domain grid; gauge and virtual-discharge parsing; MRMS resampling (no network)."""

import numpy as np
import pandas as pd
import pytest
import rasterio
from affine import Affine

from rainier3d.config.domain import load_domain
from rainier3d.hydromet import events as E


def test_hours_are_frame_ends():
    h = E.hours({"start": "2025-12-05T00:00:00Z", "end": "2025-12-05T03:00:00Z"})
    assert [t.hour for t in h] == [1, 2, 3]


def test_rain_grid_follows_the_domain():
    dom = load_domain()
    t, nx, ny = E.rain_grid(dom, 1000)
    x0, y0, x1, y1 = dom.bounds
    assert (nx, ny) == ((x1 - x0) / 1000, (y1 - y0) / 1000)
    assert (t.c, t.f) == (x0, y1)
    with pytest.raises(ValueError):
        E.rain_grid(dom, 3000)  # 70 km is not a whole number of 3 km cells


def test_mrms_on_domain_averages_and_masks(tmp_path):
    """A synthetic 0.01 deg raster: 2 mm everywhere, -3 (no coverage) in the western half."""
    dom = load_domain()
    lon0, lat0, lon1, lat1 = dom.bbox_4326
    w, h = int((lon1 - lon0 + 0.2) / 0.01), int((lat1 - lat0 + 0.2) / 0.01)
    a = np.full((h, w), 2.0, "float32")
    a[:, : w // 2] = -3.0
    p = tmp_path / "t.tif"
    with rasterio.open(
        p,
        "w",
        driver="GTiff",
        width=w,
        height=h,
        count=1,
        dtype="float32",
        crs="EPSG:4326",
        transform=Affine(0.01, 0, lon0 - 0.1, 0, -0.01, lat1 + 0.1),
    ) as d:
        d.write(a, 1)
    out = E.mrms_on_domain(p, dom, 1000)
    assert out.shape == (75, 70)
    ok = np.isfinite(out)
    assert np.allclose(out[ok], 2.0)
    assert 0.2 < ok.mean() < 0.8  # the no-coverage half is NaN, not 0


def _nwis(site, lat, lon, values):
    return {
        "sourceInfo": {
            "siteCode": [{"value": site}],
            "siteName": f"RIVER {site}",
            "geoLocation": {"geogLocation": {"latitude": lat, "longitude": lon}},
        },
        "variable": {"noDataValue": -999999.0},
        "values": [{"value": [{"value": str(v), "dateTime": t} for t, v in values]}],
    }


def test_gauges_parse_convert_and_drop_nodata():
    doc = {
        "value": {
            "timeSeries": [
                _nwis(
                    "1",
                    46.9,
                    -122.0,
                    [("2025-12-09T00:00:00.000-08:00", 1000), ("2025-12-09T00:15:00.000-08:00", -999999)],
                ),
                _nwis("2", 46.8, -121.9, [("2025-12-09T00:15:00.000-08:00", 100)]),
            ]
        }
    }
    ds = E.gauges(doc)
    assert list(ds.site.values) == ["1", "2"]
    assert ds.discharge.sel(site="1").max() == pytest.approx(1000 * E.CFS_TO_M3S, rel=1e-6)
    assert pd.Timestamp(ds.time.values[0]) == pd.Timestamp("2025-12-09 08:00")  # UTC, naive
    assert ds.discharge.sel(site="1").count() == 1


def test_virtual_discharge_keeps_good_ratings_in_the_window():
    files = {
        "virtual_q": {
            "CC.GOOD": {
                "time": ["2025-12-04T00:00:00+00:00", "2025-12-06T00:00:00+00:00"],
                "q_seis": [1.0, 2.0],
            },
            "CC.BAD": {"time": ["2025-12-06T00:00:00+00:00"], "q_seis": [5.0]},
        },
        "virtual_q_fit": [{"station": "CC.GOOD", "nse_logQ": 0.9}, {"station": "CC.BAD", "nse_logQ": -3.0}],
        "cc_stations": [
            {"sta": "GOOD", "lat": 46.9, "lon": -122.0, "site": "Good"},
            {"sta": "BAD", "lat": 46.9, "lon": -122.0},
        ],
        "uw_stations": [],
    }
    ds = E.virtual_discharge(files, 0.7, "2025-12-05T00:00:00Z", "2025-12-14T00:00:00Z")
    assert list(ds.site.values) == ["CC.GOOD"]
    assert ds.discharge.values.tolist() == [[2.0]]
    assert float(ds.nse_logq[0]) == 0.9
