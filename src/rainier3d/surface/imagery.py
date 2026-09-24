"""Sentinel-2 L2A composite over the domain: true colour for display, NDVI and NDSI for the surface stack.

Same recipe as gaia-hazlab/seis-hydro-2-sed workflows/28_fetch_basemaps.py: scenes with <= 25 % cloud in a
clear-sky window, scene classification (SCL) keeps vegetation, soil, water, unclassified and snow (4, 5, 6,
7, 11), per-pixel median over time. Microsoft Planetary Computer first, Element84 Earth Search as fallback.
The window defaults to late summer 2025, when seasonal snow is at its minimum, so NDSI > 0.4 outlines ice
and perennial snow.

Output: data/raw/imagery/s2_<window>.tif on the domain UTM grid at ``res`` m, bands B02 B03 B04 B08 B11
as surface reflectance x 10000 (uint16, 0 = no clear observation).
"""

from __future__ import annotations

import logging

import numpy as np
import rasterio
from affine import Affine

from rainier3d.config.domain import Domain

log = logging.getLogger(__name__)

PC_STAC = "https://planetarycomputer.microsoft.com/api/stac/v1"
ES_STAC = "https://earth-search.aws.element84.com/v1"
BANDS = {
    "pc": ["B02", "B03", "B04", "B08", "B11", "SCL"],
    "es": ["blue", "green", "red", "nir", "swir16", "scl"],
}
KEEP_SCL = [4, 5, 6, 7, 11]
MAX_CLOUD = 25
WINDOW = "2025-08-01/2025-09-30"


def _composite(
    dom: Domain, endpoint: str, window: str, res: float, max_scenes: int
) -> tuple[np.ndarray, int]:
    from odc.stac import load as odc_load
    from pystac_client import Client

    kw = {}
    if endpoint == "pc":
        import planetary_computer as pc

        kw["modifier"] = pc.sign_inplace
    cat = Client.open(PC_STAC if endpoint == "pc" else ES_STAC, **kw)
    items = [
        it
        for it in cat.search(collections=["sentinel-2-l2a"], bbox=dom.bbox_4326, datetime=window).items()
        if it.properties.get("eo:cloud_cover", 100) <= MAX_CLOUD
    ]
    if not items:
        raise RuntimeError(f"no Sentinel-2 scenes <= {MAX_CLOUD}% cloud in {window}")
    # the least-cloudy scenes per MGRS tile, so no tile of the domain is left without observations
    by_tile: dict[str, list] = {}
    for it in sorted(items, key=lambda it: it.properties.get("eo:cloud_cover", 100)):
        by_tile.setdefault(it.properties.get("s2:mgrs_tile", it.id.split("_")[5]), []).append(it)
    items = [it for group in by_tile.values() for it in group[:max_scenes]]
    x0, y0, x1, y1 = dom.bounds
    bands = BANDS[endpoint]
    ds = odc_load(
        items,
        bands=bands,
        crs=dom.crs,
        resolution=res,
        x=(x0, x1),
        y=(y0, y1),
        chunks={"x": 2048, "y": 2048},
        groupby="solar_day",
        resampling={"*": "average", bands[-1]: "nearest"},
    )
    keep = ds[bands[-1]].isin(KEEP_SCL)
    # processing baseline >= 04.00 (all scenes since January 2022) stores reflectance x 10000 + 1000;
    # neither STAC endpoint removes the offset, and band ratios (NDVI, NDSI) are wrong without it
    baselines = {it.properties.get("s2:processing_baseline", "00.00") for it in items}
    if len({b >= "04.00" for b in baselines}) > 1:
        raise RuntimeError(f"window mixes processing baselines {sorted(baselines)}; offsets differ")
    offset = 1000.0 if min(baselines) >= "04.00" else 0.0
    out = []
    for b in bands[:-1]:
        v = (ds[b].where(keep & (ds[b] > 0)).astype("float32") - offset).median("time", skipna=True)
        v = v.where(v > 0).compute().values
        out.append(v)
    a = np.stack(out)  # rows north -> south (odc returns descending y)
    return np.nan_to_num(a, nan=0).clip(0, 65535).astype("uint16"), len(
        {i.properties["datetime"][:10] for i in items}
    )


def fetch_s2_composite(dom: Domain, window: str = WINDOW, res: float = 20.0, max_scenes: int = 6) -> str:
    cache = dom.path("raw") / "imagery" / f"s2_{window.replace('/', '_')}_{int(res)}m.tif"
    if cache.exists():
        return str(cache)
    last = None
    for endpoint in ("pc", "es"):
        try:
            log.info("Sentinel-2 %s composite from %s", window, endpoint)
            a, n = _composite(dom, endpoint, window, res, max_scenes)
            break
        except Exception as e:  # noqa: BLE001  (the fallback endpoint gets its turn)
            log.warning("Sentinel-2 via %s failed: %s", endpoint, e)
            last = e
    else:
        raise RuntimeError(f"Sentinel-2 composite failed on both endpoints: {last}")
    x0, _, _, y1 = dom.bounds
    cache.parent.mkdir(parents=True, exist_ok=True)
    prof = {
        "driver": "GTiff",
        "dtype": "uint16",
        "count": 5,
        "width": a.shape[2],
        "height": a.shape[1],
        "crs": dom.crs,
        "transform": Affine(res, 0, x0, 0, -res, y1),
        "nodata": 0,
        "compress": "deflate",
        "predictor": 2,
        "tiled": True,
        "blockxsize": 512,
        "blockysize": 512,
    }
    with rasterio.open(cache, "w", **prof) as dst:
        dst.write(a)
        dst.descriptions = ("B02", "B03", "B04", "B08", "B11")
        dst.update_tags(
            window=window,
            scenes=str(n),
            endpoint=endpoint,
            scl_keep=str(KEEP_SCL),
            max_cloud=str(MAX_CLOUD),
            scale="reflectance x 10000",
        )
    log.info("Sentinel-2 composite from %d scenes -> %s", n, cache)
    return str(cache)


def true_colour(src: str, lo_pct: float = 2.0, hi_pct: float = 98.0) -> np.ndarray:
    """RGB uint8 (rows north->south) with the per-band percentile stretch of seis-hydro-2-sed."""
    with rasterio.open(src) as ds:
        rgb = ds.read([3, 2, 1]).astype("float32")
    out = np.zeros(rgb.shape, "uint8")
    for k in range(3):
        b = rgb[k]
        ok = b > 0
        lo, hi = np.percentile(b[ok], [lo_pct, hi_pct])
        out[k] = (np.clip((b - lo) / max(hi - lo, 1), 0, 1) * 255 * ok).astype("uint8")
    return np.moveaxis(out, 0, -1)


def indices_on_grid(dom: Domain, src: str) -> dict[str, np.ndarray]:
    """NDVI (B08, B04) and NDSI (B03, B11) from the composite, averaged onto the surface grid (rows S->N)."""
    from rainier3d.surface.layers import warp

    b = {k: warp(dom, src, band=i) for k, i in (("B03", 2), ("B04", 3), ("B08", 4), ("B11", 5))}
    for v in b.values():
        v[v <= 0] = np.nan
    with np.errstate(invalid="ignore", divide="ignore"):
        return {
            "ndvi": (b["B08"] - b["B04"]) / (b["B08"] + b["B04"]),
            "ndsi": (b["B03"] - b["B11"]) / (b["B03"] + b["B11"]),
        }
