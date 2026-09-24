import numpy as np
import pytest

from rainier.geotiff import read_tiff, write_tiff


def test_round_trip_stripped():
    a = np.arange(12, dtype=np.float32).reshape(3, 4)
    assert np.array_equal(read_tiff(write_tiff(a)), a)


def test_round_trip_tiled_with_partial_edge_tiles():
    a = np.random.default_rng(1).random((300, 520), dtype=np.float32)
    assert np.array_equal(read_tiff(write_tiff(a, tile=256)), a)


def test_compressed_tiff_is_rejected():
    b = bytearray(write_tiff(np.zeros((2, 2), np.float32)))
    b = bytes(b).replace(b"\x03\x01\x03\x00\x01\x00\x00\x00\x01\x00", b"\x03\x01\x03\x00\x01\x00\x00\x00\x05\x00")   # Compression=1 → 5 (LZW)
    with pytest.raises(ValueError, match="compress"):
        read_tiff(b)
