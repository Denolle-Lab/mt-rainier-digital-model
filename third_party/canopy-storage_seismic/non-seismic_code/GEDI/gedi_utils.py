"""
Shared helper functions used across the GEDI download, gridding, and
visualization scripts. Keeping these in one place means every product
(L2B, L3, L4B) crops, reprojects, and displays rasters the exact same
way instead of each script reinventing it slightly differently.
"""

import os
import numpy as np
import rasterio
from rasterio.mask import mask as rio_mask
from rasterio.warp import transform_bounds
from rasterio.vrt import WarpedVRT
from rasterio.enums import Resampling
import rasterio.plot


def crop_to_bbox(src_path, dst_path, bbox_lonlat):
    """
    Crop a GeoTIFF to a bounding box given in lon/lat (EPSG:4326),
    regardless of the raster's native CRS. The bbox is reprojected
    into the raster's own CRS before cropping, so this works whether
    the source is in EASE-Grid meters, geographic degrees, or anything
    else.

    Returns a dict with diagnostic info (native CRS, cropped shape,
    valid pixel count) so the caller can print a sanity check.
    """
    from shapely.geometry import box  # only needed here; keeps this
                                        # module's other functions free
                                        # of the shapely dependency

    with rasterio.open(src_path) as src:
        minx, miny, maxx, maxy = transform_bounds("EPSG:4326", src.crs, *bbox_lonlat)
        roi_geom = [box(minx, miny, maxx, maxy)]

        out_image, out_transform = rio_mask(src, roi_geom, crop=True)
        out_meta = src.meta.copy()
        out_meta.update({
            "height": out_image.shape[1],
            "width": out_image.shape[2],
            "transform": out_transform,
        })
        with rasterio.open(dst_path, "w", **out_meta) as dst:
            dst.write(out_image)

        n_valid = None
        if src.nodata is not None:
            n_valid = int((out_image[0] != src.nodata).sum())

        return {
            "native_crs": str(src.crs),
            "shape": out_image.shape[1:],
            "n_valid": n_valid,
        }


def read_band_reprojected(path, display_crs="EPSG:4326", resampling=Resampling.nearest):
    """
    Read band 1 of a raster, reprojected on the fly to display_crs.
    Returns (data, extent) ready for matplotlib's imshow(extent=...).
    NaN-fills nodata so masking/plotting downstream is straightforward.
    """
    with rasterio.open(path) as src:
        with WarpedVRT(src, crs=display_crs, resampling=resampling) as vrt:
            data = vrt.read(1).astype(float)
            nodata = vrt.nodata
            if nodata is not None and not np.isnan(nodata):
                data[data == nodata] = np.nan
            extent = rasterio.plot.plotting_extent(vrt)
    return data, extent


def compute_se(stddev, count, min_count=2):
    """
    Standard error of the mean = stddev / sqrt(count).
    Undefined (NaN) below min_count, since a std dev needs >= 2 points
    to mean anything.

    NOTE on what this is NOT: this is a simple sampling-only SE. It is
    not GEDI L4B's actual hybrid/GHMB model-based uncertainty, which
    additionally accounts for model error in the underlying footprint
    estimates -- that requires a calibrated field-to-GEDI model we
    don't have outside of NASA's own L4A/L4B pipeline. Treat this as a
    rough guide, not a rigorous uncertainty estimate.
    """
    stddev = np.asarray(stddev, dtype=float)
    count = np.asarray(count, dtype=float)
    with np.errstate(invalid="ignore", divide="ignore"):
        se = np.where(count >= min_count, stddev / np.sqrt(count), np.nan)
    return se


def strip_product_prefix(filename, prefixes):
    """
    Remove a known product prefix (e.g. 'L4B_') from a filename stem,
    returning the remaining variable name. Tries longer prefixes first
    so e.g. 'L2B_PAI_' is matched before a shorter accidental overlap.
    """
    stem = os.path.splitext(os.path.basename(filename))[0]
    for prefix in sorted(prefixes, key=len, reverse=True):
        if stem.startswith(prefix):
            return stem[len(prefix):]
    return stem


def compute_grid_shape(n):
    """
    Pick a (rows, cols) layout for n subplots that avoids wasted empty
    slots for small, common panel counts: a single row for n<=3
    (matches how 3-panel figures already looked good), otherwise as
    close to square as possible (e.g. n=4 -> 2x2, not 2x3).
    """
    import math
    if n <= 3:
        return 1, n
    cols = math.ceil(math.sqrt(n))
    rows = math.ceil(n / cols)
    return rows, cols