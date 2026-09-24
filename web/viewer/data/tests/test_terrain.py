import json

import numpy as np
import pytest

from rainier import extent as E
from rainier import fetch, terrain
from rainier.geotiff import write_tiff


def test_get_returns_cached_bytes_without_opening(tmp_path):
    p = tmp_path / "a.bin"
    p.write_bytes(b"cached")
    def opener(*a, **k):
        raise AssertionError("network used")
    assert fetch.get("http://x", p, opener=opener) == b"cached"


class _Resp:
    def __init__(self, body): self.body = body
    def read(self): return self.body
    def __enter__(self): return self
    def __exit__(self, *a): return False


def test_get_rejects_html_error_pages(tmp_path):
    with pytest.raises(fetch.FetchError):
        fetch.get("http://x", tmp_path / "b.bin", opener=lambda *a, **k: _Resp(b"<html>Error exporting image</html>"))
    assert not (tmp_path / "b.bin").exists()


def test_get_caches_a_good_response(tmp_path):
    body = fetch.get("http://x", tmp_path / "c" / "d.bin", opener=lambda *a, **k: _Resp(b"\x00\x01"))
    assert body == b"\x00\x01" and (tmp_path / "c" / "d.bin").read_bytes() == b"\x00\x01"


def test_build_overview_writes_heights_image_and_meta(tmp_path):
    urls = []
    def get(url, path):
        urls.append(url)
        if "exportImage" in url:
            a = np.full((1215, 1800), 1500, np.float32)
            a[0, 0] = -3.4e38                      # NODATA fills with the grid minimum
            return write_tiff(a, tile=512)
        return b"\xff\xd8jpeg"
    meta = terrain.build_overview(tmp_path / "out", tmp_path / "cache", get=get)
    h = np.fromfile(tmp_path / "out" / "terrain" / "overview.bin", "<i2")
    assert h.size == 1800 * 1215 and (h == 1500).all()
    assert (tmp_path / "out" / "terrain" / "overview.jpg").read_bytes() == b"\xff\xd8jpeg"
    assert meta["cols"] == 1800 and meta["rows"] == 1215
    assert meta["dx"] == pytest.approx(0.8 * E.KX / 1800) and meta["x0"] == pytest.approx(E.to_x(-122.16))
    assert meta["z0"] == pytest.approx(E.to_z(E.OVERVIEW.north))
    assert json.loads((tmp_path / "out" / "terrain" / "terrain.json").read_text()) == meta
    assert any("size=1800,1215" in u for u in urls) and any("size=4080,2754" in u for u in urls)


def test_get_does_not_cache_a_body_that_fails_validation(tmp_path):
    with pytest.raises(fetch.FetchError):
        fetch.get("http://x", tmp_path / "q.csv", opener=lambda *a, **k: _Resp(b"time,latitude\n"), validate=lambda b: b.count(b"\n") > 10)
    assert not (tmp_path / "q.csv").exists()
