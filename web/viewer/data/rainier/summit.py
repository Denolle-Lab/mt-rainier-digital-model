"""Summit patch: 1 m 3DEP lidar and matching imagery, cut into a four-level tile pyramid.

Tiles are TILE cells square with a shared edge ((TILE+1)² samples), Uint16 decimeters, row 0 north.
The site's summitLod.js reads summit/index.json in exactly this shape.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import numpy as np

from . import extent as E
from . import fetch
from .geotiff import read_tiff
from .terrain import dem_url, fill_nodata, img_url

PIECE = 2048                 # elevation request size; 4096 is refused by the service
CELLS = E.SUMMIT_CELLS       # (east-west, north-south) cells at the finest level
LEVELS = (8, 4, 2, 1)        # cells of the finest grid per cell of each level
TILE = 256
CHUNK = (3072, 2048)         # imagery request size per level (≤ 4096, the service limit)
MAX_SEAM_M = 2.0


def patch_box() -> E.Box:
    p = E.SUMMIT_PIXEL
    return E.Box(E.LON0 - CELLS[0] / 2 * p, E.LAT0 - CELLS[1] / 2 * p, E.LON0 + CELLS[0] / 2 * p, E.LAT0 + CELLS[1] / 2 * p)


def sub_box(b: E.Box, col: int, row: int, w: int, h: int, cell: float) -> E.Box:
    """Box of a w × h block at (col, row) cells from the north-west corner."""
    return E.Box(b.west + col * cell, b.north - (row + h) * cell, b.west + (col + w) * cell, b.north - row * cell)


def seam_steps(dem: np.ndarray, piece: int) -> list[float]:
    rows, cols = dem.shape
    steps = [float(np.abs(dem[r] - dem[r - 1]).mean()) for r in range(piece, rows, piece)]
    steps += [float(np.abs(dem[:, c] - dem[:, c - 1]).mean()) for c in range(piece, cols, piece)]
    return steps


def pyramid(dem: np.ndarray, out_dir, tile: int = TILE, factors=LEVELS) -> list[dict]:
    out_dir = Path(out_dir)
    levels = []
    for level, f in enumerate(factors):
        lz, lx = dem.shape[0] // f, dem.shape[1] // f
        g = dem[:lz * f, :lx * f].reshape(lz, f, lx, f).mean(axis=(1, 3)) if f > 1 else dem
        g = np.pad(g, ((0, 1), (0, 1)), mode="edge")
        q = np.clip(np.round(g * 10), 0, 65535).astype("<u2")
        (out_dir / str(level)).mkdir(parents=True, exist_ok=True)
        tz, tx = lz // tile, lx // tile
        for ty in range(tz):
            for tx_ in range(tx):
                q[ty * tile:ty * tile + tile + 1, tx_ * tile:tx_ * tile + tile + 1].tofile(out_dir / str(level) / f"{ty}_{tx_}.bin")
        levels.append({"level": level, "factor": f, "tiles_x": tx, "tiles_z": tz, "cells_x": lx, "cells_z": lz})
    return levels


def build_summit(out_dir, cache_dir, get=fetch.get) -> dict:
    out = Path(out_dir) / "summit"
    cache = Path(cache_dir) / "summit"
    box, p = patch_box(), E.SUMMIT_PIXEL
    nx, nz = CELLS
    dem = np.zeros((nz, nx), np.float32)
    for r in range(nz // PIECE):
        for c in range(nx // PIECE):
            url = dem_url(sub_box(box, c * PIECE, r * PIECE, PIECE, PIECE, p), (PIECE, PIECE))
            dem[r * PIECE:(r + 1) * PIECE, c * PIECE:(c + 1) * PIECE] = read_tiff(get(url, cache / f"dem_{r}_{c}.tif"))
    dem = fill_nodata(dem)
    steps = seam_steps(dem, PIECE)
    if steps and max(steps) > MAX_SEAM_M:
        raise ValueError(f"summit seam: mean step {max(steps):.1f} m across a piece boundary (limit {MAX_SEAM_M} m)")
    if out.exists():
        shutil.rmtree(out)
    levels = pyramid(dem, out, TILE, LEVELS)
    (out / "img").mkdir(parents=True)
    index_levels = []
    for lv in levels:
        f, lx, lz = lv["factor"], lv["cells_x"], lv["cells_z"]
        cw, ch = min(lx, CHUNK[0]), min(lz, CHUNK[1])
        for r in range(lz // ch):
            for c in range(lx // cw):
                name = f"img{lv['level']}_{r}_{c}.jpg"
                url = img_url(sub_box(box, c * cw, r * ch, cw, ch, p * f), (cw, ch))
                (out / "img" / name).write_bytes(get(url, cache / name))
        index_levels.append({"level": lv["level"], "cell_x_km": f * p * E.KX, "cell_z_km": f * p * E.KZ,
                             "tiles_x": lv["tiles_x"], "tiles_z": lv["tiles_z"], "chunk_w": cw, "chunk_h": ch})
    index = {
        "patch": {"west_km": E.to_x(box.west), "north_km": E.to_z(box.north), "width_km": nx * p * E.KX, "height_km": nz * p * E.KZ},
        "tile": TILE,
        "levels": index_levels,
        "maxSeamStepM": max(steps) if steps else 0.0,
        "source": "USGS 3DEP 1 m lidar and USGS The National Map imagery (public domain)",
    }
    (out / "index.json").write_text(json.dumps(index, indent=1))
    return index
