"""Overview terrain: USGS 3DEP elevation and USGS National Map imagery for the 60 × 60 km map area."""
from __future__ import annotations

import json
import urllib.parse
from pathlib import Path

import numpy as np

from . import extent as E
from . import fetch
from .geotiff import read_tiff

DEM_URL = "https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer/exportImage"
IMG_URL = "https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryOnly/MapServer/export"


def bbox(b: E.Box) -> str:
    return f"{b.west},{b.south},{b.east},{b.north}"


def dem_url(b: E.Box, size: tuple[int, int]) -> str:
    q = {"bbox": bbox(b), "bboxSR": 4326, "imageSR": 4326, "size": f"{size[0]},{size[1]}", "format": "tiff",
         "pixelType": "F32", "interpolation": "RSP_BilinearInterpolation", "f": "image"}
    return f"{DEM_URL}?{urllib.parse.urlencode(q, safe=',')}"


def img_url(b: E.Box, size: tuple[int, int]) -> str:
    q = {"bbox": bbox(b), "bboxSR": 4326, "imageSR": 4326, "size": f"{size[0]},{size[1]}", "format": "jpg", "f": "image"}
    return f"{IMG_URL}?{urllib.parse.urlencode(q, safe=',')}"


def fill_nodata(a: np.ndarray) -> np.ndarray:
    bad = ~np.isfinite(a) | (a < -100)
    if bad.any():
        a = a.copy()
        a[bad] = a[~bad].min()
    return a


def build_overview(out_dir, cache_dir, get=fetch.get) -> dict:
    out = Path(out_dir) / "terrain"
    out.mkdir(parents=True, exist_ok=True)
    cache = Path(cache_dir) / "overview"
    size = E.square_size(E.OVERVIEW, E.OVERVIEW_SIZE[0])
    dem = fill_nodata(read_tiff(get(dem_url(E.OVERVIEW, size), cache / "dem.tif")))
    np.round(dem).astype("<i2").tofile(out / "overview.bin")
    img_size = E.square_size(E.OVERVIEW, E.OVERVIEW_IMAGE_WIDTH)
    (out / "overview.jpg").write_bytes(get(img_url(E.OVERVIEW, img_size), cache / "img.jpg"))
    b, (cols, rows) = E.OVERVIEW, size
    meta = {
        "cols": cols, "rows": rows,
        "x0": E.to_x(b.west), "z0": E.to_z(b.north),
        "dx": (b.east - b.west) / cols * E.KX, "dz": (b.north - b.south) / rows * E.KZ,
        "min": float(dem.min()), "max": float(dem.max()),
        "image": {"width": img_size[0], "height": img_size[1]},
        "source": "USGS 3DEP elevation and USGS The National Map imagery (public domain)",
    }
    (out / "terrain.json").write_text(json.dumps(meta, indent=1))
    return meta
