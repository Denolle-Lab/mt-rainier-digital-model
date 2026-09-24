import math

import pytest

from rainier import extent as E


def test_projection_origin_and_scale():
    assert E.to_x(E.LON0) == 0 and E.to_z(E.LAT0) == 0
    assert E.to_x(E.LON0 + 1) == pytest.approx(111.32 * math.cos(math.radians(E.LAT0)))
    assert E.to_z(E.LAT0 + 1) == pytest.approx(-111.13)   # north is −z


def test_overview_request_has_square_degree_pixels():
    w, h = E.square_size(E.OVERVIEW, 1800)
    assert (w, h) == (1800, 1215)
    assert (E.OVERVIEW.east - E.OVERVIEW.west) / w == pytest.approx((E.OVERVIEW.north - E.OVERVIEW.south) / h, rel=1e-9)


def test_square_size_rejects_a_box_that_cannot_be_square():
    with pytest.raises(ValueError):
        E.square_size(E.Box(0, 0, 1, 0.7777), 1000)   # 777.7 px tall is not a whole number of pixels


def test_summit_patch_is_centered_and_sized():
    b = E.SUMMIT
    assert (b.west + b.east) / 2 == pytest.approx(E.LON0) and (b.south + b.north) / 2 == pytest.approx(E.LAT0)
    assert (b.east - b.west) / E.SUMMIT_PIXEL == pytest.approx(12288)
    assert (b.north - b.south) / E.SUMMIT_PIXEL == pytest.approx(8192)
