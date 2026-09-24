import json

import numpy as np
import pytest

from rainier import extent as E
from rainier import summit
from rainier.geotiff import write_tiff


def _tile(out, level, ty, tx, n=9):
    return np.fromfile(out / str(level) / f"{ty}_{tx}.bin", "<u2").reshape(n, n)


@pytest.fixture
def dem():
    rng = np.random.default_rng(3)
    return (2000 + rng.random((64, 96)) * 100).astype(np.float32)


def test_level_tiles_hold_block_means_in_decimeters(dem, tmp_path):
    levels = summit.pyramid(dem, tmp_path, tile=8, factors=(4, 2, 1))
    assert [(l["tiles_x"], l["tiles_z"]) for l in levels] == [(3, 2), (6, 4), (12, 8)]
    t = _tile(tmp_path, 0, 0, 0)
    assert t[0, 0] == round(float(dem[:4, :4].mean()) * 10)
    assert t[1, 2] == round(float(dem[4:8, 8:12].mean()) * 10)


def test_adjacent_tiles_share_their_edge(dem, tmp_path):
    summit.pyramid(dem, tmp_path, tile=8, factors=(4, 2, 1))
    assert np.array_equal(_tile(tmp_path, 1, 0, 0)[:, 8], _tile(tmp_path, 1, 0, 1)[:, 0])
    assert np.array_equal(_tile(tmp_path, 1, 0, 0)[8, :], _tile(tmp_path, 1, 1, 0)[0, :])


def test_last_row_and_column_are_edge_padded(dem, tmp_path):
    summit.pyramid(dem, tmp_path, tile=8, factors=(4, 2, 1))
    last = _tile(tmp_path, 2, 7, 11)
    assert np.array_equal(last[:, 8], last[:, 7]) and np.array_equal(last[8, :], last[7, :])


def test_seam_steps_find_an_offset_piece(dem):
    shifted = dem.copy()
    shifted[:, 48:] += 200
    steps = summit.seam_steps(shifted, 48)
    assert max(steps) == pytest.approx(200, abs=40) and min(steps) < 60


def test_build_summit_refuses_a_bad_seam(tmp_path, monkeypatch):
    monkeypatch.setattr(summit, "PIECE", 8)
    monkeypatch.setattr(summit, "CELLS", (16, 16))
    monkeypatch.setattr(summit, "LEVELS", (2, 1))
    def get(url, path):
        if "exportImage" in url:
            r, c = map(int, path.stem.split("_")[1:])
            return write_tiff(np.full((8, 8), 2000 + (300 if (r, c) == (1, 1) else 0), np.float32))
        return b"\xff\xd8"
    with pytest.raises(ValueError, match="summit seam"):
        summit.build_summit(tmp_path / "out", tmp_path / "cache", get=get)


def test_index_matches_the_real_patch(tmp_path, monkeypatch):
    monkeypatch.setattr(summit, "PIECE", 8)
    monkeypatch.setattr(summit, "CELLS", (24, 16))
    monkeypatch.setattr(summit, "LEVELS", (2, 1))
    monkeypatch.setattr(summit, "TILE", 4)
    get = lambda url, path: write_tiff(np.full((8, 8), 3000, np.float32)) if "exportImage" in url else b"\xff\xd8"
    idx = summit.build_summit(tmp_path / "out", tmp_path / "cache", get=get)
    assert json.loads((tmp_path / "out" / "summit" / "index.json").read_text()) == idx
    assert idx["tile"] == 4 and [l["level"] for l in idx["levels"]] == [0, 1]
    finest = idx["levels"][-1]
    assert finest["cell_x_km"] == pytest.approx(E.SUMMIT_PIXEL * E.KX) and finest["cell_z_km"] == pytest.approx(E.SUMMIT_PIXEL * E.KZ)
    assert (tmp_path / "out" / "summit" / "img" / "img1_0_0.jpg").exists()


def test_real_constants_give_sub_meter_cells():
    assert E.SUMMIT_PIXEL * E.KX * 1000 == pytest.approx(0.685, abs=0.001)
    assert E.SUMMIT_PIXEL * E.KZ * 1000 == pytest.approx(1.000, abs=0.001)
