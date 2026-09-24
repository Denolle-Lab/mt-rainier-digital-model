"""Minimal GeoTIFF support: uncompressed, single-band float32, striped or tiled — what the 3DEP export returns."""
from __future__ import annotations

import struct

import numpy as np

_SIZES = {1: 1, 2: 1, 3: 2, 4: 4, 11: 4, 12: 8, 16: 8}
_FMT = {3: "H", 4: "I", 11: "f", 12: "d"}


def _tags(b: bytes) -> dict[int, list]:
    if b[:2] != b"II":
        raise ValueError("only little-endian TIFF is supported")
    off = struct.unpack_from("<I", b, 4)[0]
    n = struct.unpack_from("<H", b, off)[0]
    tags = {}
    for i in range(n):
        tag, typ, count, val = struct.unpack_from("<HHII", b, off + 2 + i * 12)
        size = _SIZES[typ] * count
        fmt = _FMT.get(typ)
        if size > 4:
            tags[tag] = list(struct.unpack_from(f"<{count}{fmt}", b, val)) if fmt else None
        elif typ == 3:
            tags[tag] = list(struct.unpack_from(f"<{count}H", b, off + 2 + i * 12 + 8))
        else:
            tags[tag] = [val]
    return tags


def read_tiff(b: bytes) -> np.ndarray:
    """Return the first band as float32, row 0 at the north edge."""
    t = _tags(b)
    if t.get(259, [1])[0] != 1:
        raise ValueError("compressed TIFF is not supported")
    if t.get(258, [32])[0] != 32 or t.get(339, [3])[0] != 3:
        raise ValueError("only 32-bit float TIFF is supported")
    w, h = t[256][0], t[257][0]
    if 322 in t:
        tw, tl = t[322][0], t[323][0]
        nx = -(-w // tw)
        out = np.zeros((-(-h // tl) * tl, nx * tw), np.float32)
        for k, (o, c) in enumerate(zip(t[324], t[325])):
            r, col = divmod(k, nx)
            out[r * tl:(r + 1) * tl, col * tw:(col + 1) * tw] = np.frombuffer(b, "<f4", tw * tl, o).reshape(tl, tw)
        return out[:h, :w]
    data = b"".join(b[o:o + c] for o, c in zip(t[273], t[279]))
    return np.frombuffer(data, "<f4", w * h).reshape(h, w).copy()


def write_tiff(a: np.ndarray, tile: int | None = None) -> bytes:
    """Test helper: a minimal little-endian float32 TIFF, striped (one strip) or tiled."""
    a = np.asarray(a, "<f4")
    h, w = a.shape
    if tile:
        ny, nx = -(-h // tile), -(-w // tile)
        padded = np.zeros((ny * tile, nx * tile), "<f4")
        padded[:h, :w] = a
        blocks = [padded[r * tile:(r + 1) * tile, c * tile:(c + 1) * tile].tobytes() for r in range(ny) for c in range(nx)]
    else:
        blocks = [a.tobytes()]
    data_off = 8
    offsets, pos = [], data_off
    for blk in blocks:
        offsets.append(pos)
        pos += len(blk)
    entries = [(256, 4, 1, w), (257, 4, 1, h), (258, 3, 1, 32), (259, 3, 1, 1), (262, 3, 1, 1), (277, 3, 1, 1)]
    arrays = []
    if tile:
        entries += [(322, 4, 1, tile), (323, 4, 1, tile)]
        arrays += [(324, offsets), (325, [len(x) for x in blocks])]
    else:
        entries += [(278, 4, 1, h)]
        arrays += [(273, offsets), (279, [len(x) for x in blocks])]
    entries.append((339, 3, 1, 3))
    extra, extra_pos = b"", pos
    for tag, vals in arrays:
        if len(vals) == 1:
            entries.append((tag, 4, 1, vals[0]))
        else:
            entries.append((tag, 4, len(vals), extra_pos + len(extra)))
            extra += struct.pack(f"<{len(vals)}I", *vals)
    entries.sort()
    ifd_off = extra_pos + len(extra)
    ifd = struct.pack("<H", len(entries)) + b"".join(struct.pack("<HHII", *e) for e in entries) + struct.pack("<I", 0)
    return b"II" + struct.pack("<HI", 42, ifd_off) + b"".join(blocks) + extra + ifd
