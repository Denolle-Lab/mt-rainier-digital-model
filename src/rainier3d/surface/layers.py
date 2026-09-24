"""Environmental 2D layers on the surface grid: soil, water table, streams, canopy, land cover.

Every raster is warped straight from its source (a cloud-optimised GeoTIFF read through /vsicurl, or a
cached download) onto the domain surface grid, so only the window over the domain is read. Continuous
layers are block-averaged; categorical layers use the modal class. Each layer carries provenance from
``configs/sources.yaml``.
"""

from __future__ import annotations

import logging

import numpy as np
import rasterio
import xarray as xr
from affine import Affine
from rasterio.enums import Resampling
from rasterio.vrt import WarpedVRT

from rainier3d.config.domain import Domain
from rainier3d.io.store import provenance

log = logging.getLogger(__name__)

SOLUS = "/vsicurl/https://storage.googleapis.com/solus100pub/{name}"


def warp(dom: Domain, src: str, resampling: Resampling = Resampling.average, band: int = 1) -> np.ndarray:
    """Read ``src`` (path or GDAL URL) warped onto the surface grid; rows run south to north like dom.y."""
    r = dom.surface_res_m
    x0, y0, x1, y1 = dom.bounds
    nx, ny = int((x1 - x0) / r), int((y1 - y0) / r)
    with (
        rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", GDAL_HTTP_MULTIRANGE="YES"),
        rasterio.open(src) as ds,
    ):
        nod = ds.nodata
        with WarpedVRT(
            ds,
            crs=dom.crs,
            transform=Affine(r, 0, x0, 0, -r, y1),
            width=nx,
            height=ny,
            resampling=resampling,
            src_nodata=nod,
            nodata=np.nan if ds.dtypes[0].startswith("float") else nod,
        ) as vrt:
            a = vrt.read(band, masked=True)
    a = a.astype("float32").filled(np.nan) if np.ma.isMaskedArray(a) else a.astype("float32")
    return a[::-1]


def _da(dom: Domain, a: np.ndarray, name: str, attrs: dict, keys: list[str], measurement: str, res: float):
    da = xr.DataArray(a, dims=("y", "x"), coords={"y": dom.y, "x": dom.x}, name=name, attrs=attrs)
    return provenance(da, keys, measurement, res)


def soil_thickness(dom: Domain) -> xr.DataArray:
    """SOLUS100 depth to any lithic contact (cm -> m). 201 cm reads as 'at least 2 m' (prediction cap)."""
    a = warp(dom, SOLUS.format(name="anylithicdpt_cm_p.tif"))
    a = np.where(a < 0, np.nan, a / 100.0).astype("float32")
    return _da(
        dom,
        a,
        "soil_thickness",
        {
            "units": "m",
            "long_name": "soil thickness (depth to lithic contact), SOLUS100 prediction",
            "cap_m": 2.01,
        },
        ["solus100"],
        "soil_thickness",
        100,
    )


def water_table_depth(dom: Domain, src: str, name: str, key: str) -> xr.DataArray:
    """Water-table depth (m below ground, positive down), block-averaged onto the surface grid."""
    a = warp(dom, src)
    a = np.where((a < 0) | (a > 5000), np.nan if name.endswith("fan") else 0.0, a).astype("float32")
    ln = {
        "ma2026_wtd": "water-table depth below ground, Ma et al. 2026 random-forest mean",
        "fan2017_wtd": "water-table depth below ground, Fan et al. 2017 annual mean",
    }[key]
    res = {"ma2026_wtd": 24, "fan2017_wtd": 925}[key]
    return _da(dom, a, name, {"units": "m", "long_name": ln}, [key], name, res)


def canopy_height(dom: Domain, src: str) -> xr.DataArray:
    a = warp(dom, src)
    a = np.where((a < 0) | (a > 120), np.nan, a).astype("float32")
    return _da(
        dom,
        a,
        "canopy_height",
        {"units": "m", "long_name": "mean canopy height in the cell"},
        ["eth_canopy_2020"],
        "canopy_height",
        10,
    )


def land_cover(dom: Domain, src: str) -> xr.DataArray:
    a = warp(dom, src, Resampling.mode)
    a = np.nan_to_num(a, nan=0).astype("uint8")
    return _da(
        dom,
        a,
        "land_cover",
        {"long_name": "NLCD land-cover class (modal in cell)", "flag_meanings": "see NLCD legend"},
        ["nlcd_2021"],
        "land_cover",
        30,
    )


def fetch_flowlines(dom: Domain):
    """NHDPlus v2.1 (medium resolution, 1:100k) network flowlines with stream order and drainage area."""
    import geopandas as gpd

    cache = dom.path("raw") / "hydrology" / "nhdplus_flowlines.gpkg"
    if cache.exists():
        return gpd.read_file(cache)
    import pynhd

    g = pynhd.WaterData("nhdflowline_network").bybox(dom.bbox_4326)
    g = g[["comid", "gnis_name", "streamorde", "totdasqkm", "ftype", "lengthkm", "geometry"]]
    cache.parent.mkdir(parents=True, exist_ok=True)
    g.to_file(cache)
    return g


def stream_order(dom: Domain, flowlines, key: str = "nhdplus_v21") -> xr.DataArray:
    """Highest Strahler order of any flowline crossing the cell (0 = no mapped stream)."""
    from rasterio.features import rasterize

    r = dom.surface_res_m
    x0, y0, x1, y1 = dom.bounds
    g = flowlines.to_crs(dom.crs).sort_values("streamorde")
    shape = (int((y1 - y0) / r), int((x1 - x0) / r))
    a = rasterize(
        ((geom, int(o)) for geom, o in zip(g.geometry, g.streamorde, strict=True) if o and o > 0),
        out_shape=shape,
        transform=Affine(r, 0, x0, 0, -r, y1),
        fill=0,
        all_touched=True,
        merge_alg=rasterio.enums.MergeAlg.replace,
        dtype="uint8",
    )[::-1]
    return _da(
        dom,
        a,
        "stream_order",
        {"long_name": "Strahler stream order of NHDPlus flowlines in the cell, 0 = none"},
        [key],
        "stream_order",
        r,
    )


HR_STAGED = (
    "https://prd-tnm.s3.amazonaws.com/StagedProducts/Hydrography/NHDPlusHR/Beta/GDB/NHDPLUS_H_{}_HU4_GDB.zip"
)
HR_HU4 = (
    "1711",
    "1708",
    "1703",
)  # Puget Sound, Lower Columbia-Cowlitz, Yakima: the basins the domain touches


def fetch_flowlines_hr(dom: Domain):
    """NHDPlus High Resolution (1:24k) flowlines in the domain, from the USGS staged HU4 geodatabases (the
    query service stalls on requests this size), joined to Strahler order and drainage area (VAA) and to EROM
    mean annual flow (QAMA, cfs)."""
    import geopandas as gpd
    import pandas as pd
    import pyogrio
    import requests

    cache = dom.path("raw") / "hydrology" / "nhdplus_hr_flowlines.gpkg"
    if cache.exists():
        return gpd.read_file(cache)
    parts = []
    for h in HR_HU4:
        z = cache.parent / f"NHDPLUS_H_{h}_HU4_GDB.zip"
        if not z.exists():
            with requests.get(HR_STAGED.format(h), stream=True, timeout=600) as r:
                r.raise_for_status()
                z.write_bytes(r.content)
        src = f"zip://{z}"
        fl = pyogrio.read_dataframe(
            src,
            layer="NHDFlowline",
            bbox=dom.bbox_4326,
            columns=["NHDPlusID", "GNIS_Name", "FType", "LengthKM"],
        )
        if fl.empty:
            continue
        ids = set(fl.NHDPlusID)
        vaa = pyogrio.read_dataframe(
            src,
            layer="NHDPlusFlowlineVAA",
            read_geometry=False,
            columns=["NHDPlusID", "StreamOrde", "TotDASqKm"],
        )
        erom = pyogrio.read_dataframe(
            src, layer="NHDPlusEROMMA", read_geometry=False, columns=["NHDPlusID", "QAMA"]
        )
        fl = fl.merge(vaa[vaa.NHDPlusID.isin(ids)], on="NHDPlusID", how="left")
        fl = fl.merge(erom[erom.NHDPlusID.isin(ids)], on="NHDPlusID", how="left")
        parts.append(fl.to_crs(4326))
        log.info("NHDPlus HR HU4 %s: %d flowlines in the domain", h, len(fl))
    g = gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), crs=4326).drop_duplicates("NHDPlusID")
    g = g.rename(
        columns={
            "NHDPlusID": "nhdplusid",
            "GNIS_Name": "gnis_name",
            "FType": "ftype",
            "LengthKM": "lengthkm",
            "StreamOrde": "streamorde",
            "TotDASqKm": "totdasqkm",
            "QAMA": "qama",
        }
    )
    g["geometry"] = g.geometry.force_2d()
    g.to_file(cache)
    return g


# ---- fetchers: each caches a clip over the domain in data/raw/<source>/ and returns its path ----

MA_URL = (
    "https://zenodo.org/api/records/18504963/files/"
    "wtd_mean_estimate_RF_additional_inputs_dummy_drop0LP_1s_CONUS2_m_v_20240813.tif/content"
)
FAN_URL = "http://thredds-gfnl.usc.es/thredds/dodsC/GLOBALWTDFTP/annualmeans/NAMERICA_WTD_annualmean.nc"
ETH_URL = (
    "https://libdrive.ethz.ch/index.php/s/cO8or7iOe5dT2Rt/download?path=%2F3deg_cogs"
    "&files=ETH_GlobalCanopyHeight_10m_2020_N45W123_Map.tif"
)
NLCD_WCS = "https://www.mrlc.gov/geoserver/mrlc_download/wcs"


def _vsicurl(url: str) -> str:
    from urllib.parse import quote

    return f"/vsicurl?url={quote(url, safe='')}&use_head=no&list_dir=no"


def _clip_to_cache(dom: Domain, src: str, cache, pad_m: float = 2000) -> str:
    """Copy the window of ``src`` covering the domain (plus pad) to a local GeoTIFF, in the source CRS."""
    from rasterio.warp import transform_bounds
    from rasterio.windows import from_bounds

    if cache.exists():
        return str(cache)
    x0, y0, x1, y1 = dom.bounds
    with rasterio.Env(GDAL_HTTP_MAX_RETRY="5", GDAL_HTTP_RETRY_DELAY="5"), rasterio.open(src) as ds:
        b = transform_bounds(dom.crs, ds.crs, x0 - pad_m, y0 - pad_m, x1 + pad_m, y1 + pad_m, densify_pts=21)
        w = from_bounds(*b, transform=ds.transform).round_offsets().round_lengths()
        a = ds.read(1, window=w)
        prof = ds.profile | {
            "driver": "GTiff",
            "width": a.shape[1],
            "height": a.shape[0],
            "transform": ds.window_transform(w),
            "compress": "deflate",
            "tiled": True,
            "blockxsize": 512,
            "blockysize": 512,
            "BIGTIFF": "NO",
        }
    cache.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(cache, "w", **prof) as out:
        out.write(a, 1)
    log.info("cached %s window %dx%d -> %s", src[:60], a.shape[1], a.shape[0], cache)
    return str(cache)


def fetch_ma_wtd(dom: Domain) -> str:
    """Ma et al. 2026 water-table depth, mean, ~24 m CONUS2 grid (Zenodo 10.5281/zenodo.18504963).
    The file is stored in full-width strips, so this reads ~3,600 CONUS-wide rows once."""
    return _clip_to_cache(dom, _vsicurl(MA_URL), dom.path("raw") / "hydrology" / "ma2026_wtd_mean_clip.tif")


def fetch_fan_wtd(dom: Domain) -> str:
    """Fan et al. 2017 global water-table depth, annual mean, 30 arcsec, via OPeNDAP; stored positive down."""
    cache = dom.path("raw") / "hydrology" / "fan2017_wtd_clip.tif"
    if cache.exists():
        return str(cache)
    lon0, lat0, lon1, lat1 = dom.bbox_4326
    ds = xr.open_dataset(FAN_URL)
    da = (
        ds["WTD"]
        .isel(time=0)
        .sel(lat=slice(lat0 - 0.05, lat1 + 0.05), lon=slice(lon0 - 0.05, lon1 + 0.05))
        .load()
    )
    da = (-da).astype("float32").rename({"lon": "x", "lat": "y"}).sortby("y", ascending=False)
    da = da.rio.write_crs("EPSG:4326")
    cache.parent.mkdir(parents=True, exist_ok=True)
    da.rio.to_raster(cache)
    return str(cache)


def fetch_eth_canopy(dom: Domain) -> str:
    """Lang et al. 2023 ETH global canopy height 2020, 10 m COG tile N45W123 (covers the domain)."""
    return _clip_to_cache(dom, _vsicurl(ETH_URL), dom.path("raw") / "ecology" / "eth_canopy_height_clip.tif")


def fetch_nlcd(dom: Domain, year: int = 2021) -> str:
    """NLCD land cover through the MRLC WCS, subset in native EPSG:5070 so the 30 m grid is not resampled."""
    import requests
    from rasterio.warp import transform_bounds

    cache = dom.path("raw") / "ecology" / f"nlcd_{year}_clip.tif"
    if cache.exists():
        return str(cache)
    x0, y0, x1, y1 = transform_bounds(dom.crs, "EPSG:5070", *dom.bounds, densify_pts=21)
    snap = lambda v, f: f(v / 30) * 30  # noqa: E731
    p = [
        ("service", "WCS"),
        ("version", "2.0.1"),
        ("request", "GetCoverage"),
        ("coverageId", f"mrlc_download__NLCD_{year}_Land_Cover_L48"),
        ("subset", f"X({snap(x0 - 1000, np.floor):.0f},{snap(x1 + 1000, np.ceil):.0f})"),
        ("subset", f"Y({snap(y0 - 1000, np.floor):.0f},{snap(y1 + 1000, np.ceil):.0f})"),
        ("format", "image/geotiff"),
    ]
    r = requests.get(NLCD_WCS, params=p, timeout=300)
    r.raise_for_status()
    if not r.content.startswith((b"II*", b"MM\x00*")):
        raise RuntimeError(f"NLCD WCS did not return a GeoTIFF: {r.content[:200]!r}")
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_bytes(r.content)
    return str(cache)
