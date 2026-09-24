"""The map area, the local projection, and the square-pixel rule for ArcGIS export requests.

Local coordinates are equirectangular kilometers around the summit: x east, z south, y up.
"""
from __future__ import annotations

import math
from typing import NamedTuple

LON0, LAT0 = -121.7604, 46.8528
KX = 111.32 * math.cos(math.radians(LAT0))   # km per degree of longitude at LAT0
KZ = 111.13                                    # km per degree of latitude


class Box(NamedTuple):
    west: float
    south: float
    east: float
    north: float


def to_x(lon: float) -> float:
    return (lon - LON0) * KX


def to_z(lat: float) -> float:
    return -(lat - LAT0) * KZ


def square_size(box: Box, width: int) -> tuple[int, int]:
    """Image size whose pixels are square in degrees. ArcGIS export endpoints silently widen the
    requested area when they are not, which misplaces every piece of a mosaic."""
    h = width * (box.north - box.south) / (box.east - box.west)
    if abs(h - round(h)) > 1e-6 * h:
        raise ValueError(f"{box} at width {width} gives {h:.4f} px rows; pixels would not be square")
    return width, round(h)


# 60 × 60 km around the summit, 1800 × 1215 elevation samples (≈35 m east-west, ≈49 m north-south)
OVERVIEW_SIZE = (1800, 1215)
OVERVIEW = Box(-122.16, 46.58, -121.36, 46.58 + 1215 * 0.8 / 1800)
OVERVIEW_IMAGE_WIDTH = 4080   # 4080 × 2754 is exactly square in degrees; 4096 would give 2764.8 rows

# Summit patch: 9e-6° pixels (≈0.69 m east-west, 1.0 m north-south), 12288 × 8192 cells
SUMMIT_PIXEL = 9e-6
SUMMIT_CELLS = (12288, 8192)
SUMMIT = Box(LON0 - SUMMIT_CELLS[0] / 2 * SUMMIT_PIXEL, LAT0 - SUMMIT_CELLS[1] / 2 * SUMMIT_PIXEL,
             LON0 + SUMMIT_CELLS[0] / 2 * SUMMIT_PIXEL, LAT0 + SUMMIT_CELLS[1] / 2 * SUMMIT_PIXEL)
