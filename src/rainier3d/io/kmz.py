"""KMZ ground overlays -> georeferenced rasters (EPSG:4326 GeoTIFF + PNG + bounds).

Handles the two KMZ kinds in use:
  - a single GroundOverlay (e.g. USGS I-432, Fiske et al. 1963, one scanned JPEG with a LatLonBox);
  - a Google Earth "super-overlay" (a quadtree of GroundOverlay tiles in many KML files). Only the
    deepest level is kept; its tiles sit on a regular lon/lat grid and are pasted, not resampled.
Rotated LatLonBoxes are not supported (raises).
"""

from __future__ import annotations

import io
import json
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None  # scanned map sheets exceed PIL's default decompression-bomb limit


@dataclass
class Overlay:
    name: str
    href: str
    north: float
    south: float
    east: float
    west: float


def _tag(text: str, tag: str) -> str | None:
    m = re.search(rf"<{tag}>\s*([^<]+?)\s*</{tag}>", text)
    return m.group(1) if m else None


def ground_overlays(kmz: Path) -> list[Overlay]:
    out = []
    with zipfile.ZipFile(kmz) as z:
        for f in z.namelist():
            if not f.endswith(".kml"):
                continue
            text = z.read(f).decode("utf-8", "replace")
            for block in re.findall(r"<GroundOverlay>.*?</GroundOverlay>", text, flags=re.S):
                rot = _tag(block, "rotation")
                if rot and abs(float(rot)) > 1e-6:
                    raise NotImplementedError(f"rotated GroundOverlay in {f}")
                icon = re.search(r"<Icon>.*?<href>\s*([^<]+?)\s*</href>", block, flags=re.S)
                box = {k: _tag(block, k) for k in ("north", "south", "east", "west")}
                if icon and all(box.values()):
                    out.append(
                        Overlay(
                            _tag(block, "name") or f, icon.group(1), **{k: float(v) for k, v in box.items()}
                        )
                    )
    if not out:
        raise ValueError(f"no GroundOverlay found in {kmz}")
    return out


def mosaic(kmz: Path) -> tuple[np.ndarray, tuple[float, float, float, float]]:
    """RGBA array and (west, south, east, north) of the finest-level overlays."""
    ovs = ground_overlays(kmz)
    size = np.array([o.east - o.west for o in ovs])
    leaf = [o for o, s in zip(ovs, size, strict=True) if np.isclose(s, size.min(), rtol=1e-6)]
    with zipfile.ZipFile(kmz) as z:
        if len(leaf) == 1:
            o = leaf[0]
            img = np.asarray(Image.open(io.BytesIO(z.read(o.href))).convert("RGBA"))
            return img, (o.west, o.south, o.east, o.north)
        tw, th = leaf[0].east - leaf[0].west, leaf[0].north - leaf[0].south
        w0, n0 = min(o.west for o in leaf), max(o.north for o in leaf)
        e0, s0 = max(o.east for o in leaf), min(o.south for o in leaf)
        first = Image.open(io.BytesIO(z.read(leaf[0].href)))
        px, py = first.size
        nx, ny = int(round((e0 - w0) / tw)), int(round((n0 - s0) / th))
        canvas = np.zeros((ny * py, nx * px, 4), dtype=np.uint8)
        for o in leaf:
            i, j = int(round((n0 - o.north) / th)), int(round((o.west - w0) / tw))
            tile = np.asarray(Image.open(io.BytesIO(z.read(o.href))).convert("RGBA"))
            canvas[i * py : (i + 1) * py, j * px : (j + 1) * px] = tile
        return canvas, (w0, s0, e0, n0)


def to_geotiff(img: np.ndarray, bounds: tuple, path: Path) -> Path:
    import rasterio
    from rasterio.transform import from_bounds

    h, w = img.shape[:2]
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=w,
        height=h,
        count=4,
        dtype="uint8",
        crs="EPSG:4326",
        transform=from_bounds(*bounds, w, h),
        compress="deflate",
        tiled=True,
    ) as dst:
        dst.write(np.moveaxis(img, -1, 0))
    return path


def to_web(img: np.ndarray, bounds: tuple, stem: Path, max_px: int = 4096, jpeg: bool = False) -> dict:
    """Downscaled JPEG/WebP for the browser, plus MapLibre image-source corner coordinates."""
    im = Image.fromarray(img)
    s = min(1.0, max_px / max(im.size))
    if s < 1:
        im = im.resize((int(im.width * s), int(im.height * s)), Image.LANCZOS)
    stem.parent.mkdir(parents=True, exist_ok=True)
    # JPEG for opaque scans; WebP (keeps alpha, a fraction of PNG size) otherwise
    path = stem.with_suffix(".jpg" if jpeg else ".webp")
    (im.convert("RGB").save(path, quality=85) if jpeg else im.save(path, quality=85, method=6))
    w, s_, e, n = bounds
    meta = {"url": path.name, "coordinates": [[w, n], [e, n], [e, s_], [w, s_]], "bounds": [w, s_, e, n]}
    stem.with_suffix(".json").write_text(json.dumps(meta))
    return meta
