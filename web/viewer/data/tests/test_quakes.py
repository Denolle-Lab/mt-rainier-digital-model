import json

import numpy as np
import pytest

from rainier import extent as E
from rainier import quakes

CSV = """time,latitude,longitude,depth,mag,magType,nst,gap,dmin,rms,net,id,updated,place,type,horizontalError,depthError,magError,magNst,status,locationSource,magSource
1990-05-01T00:00:00.000Z,46.8528,-121.7604,2.5,1.2,md,,,,,uw,uw1,,x,earthquake,,,,,reviewed,uw,uw
1991-05-01T00:00:00.000Z,46.9,-121.9,-5,0.4,md,,,,,uw,uw2,,x,earthquake,,,,,reviewed,uw,uw
1992-05-01T00:00:00.000Z,46.8,-121.8,,1.0,md,,,,,uw,uw3,,x,earthquake,,,,,reviewed,uw,uw
2020-05-01T00:00:00.000Z,46.7,-121.7,10,,md,,,,,uw,uw4,,x,earthquake,,,,,reviewed,uw,uw
2021-05-01T00:00:00.000Z,46.75,-121.65,14,3.1,ml,,,,,uw,uw5,,x,earthquake,,,,,reviewed,uw,uw
"""


def test_parse_skips_rows_without_depth_or_magnitude():
    rows = quakes.parse_catalog(CSV)
    assert len(rows) == 3
    assert rows[0][:4] == (-121.7604, 46.8528, 2.5, 1.2)


def test_records_are_local_km_with_y_minus_depth_and_above_ground_is_counted(tmp_path):
    ground = lambda x, z: 1.5   # km
    meta = quakes.build_quakes(tmp_path, tmp_path / "cache", ground, get=lambda url, path: CSV.encode())
    rec = np.fromfile(tmp_path / "quakes.bin", "<f4").reshape(-1, 4)
    assert rec.shape == (3, 4)
    assert rec[0].tolist() == pytest.approx([0, -2.5, 0, 1.2], abs=1e-5)
    assert rec[1][0] == pytest.approx(E.to_x(-121.9), abs=1e-4) and rec[1][1] == pytest.approx(5.0)
    assert meta["count"] == 3 and meta["aboveGround"] == 1 and meta["drawn"] == 2
    assert meta["from"] == "1990-05-01" and meta["to"] == "2021-05-01"
    assert meta["magMin"] == 0.4 and meta["magMax"] == 3.1
    assert json.loads((tmp_path / "quakes.json").read_text()) == meta


def test_too_few_events_fail_validation():
    assert quakes.check_quakes({"count": 999}) and not quakes.check_quakes({"count": 15000})
