"""S2: environmental surface layers -> data/processed/surface_layers.zarr (to /surface in S5).

  soil_thickness            SOLUS100 depth to lithic contact (m, capped at 2.01)
  water_table_depth         Ma et al. 2026 water-table depth, mean (m below ground), from ~24 m
  water_table_depth_fan     Fan et al. 2017 water-table depth, annual mean (m below ground), from 30 arcsec
  stream_order              Strahler order of NHDPlus flowlines in the cell (HR if cached, else v2.1)
  canopy_height             ETH global canopy height 2020, Lang et al. 2023 (m), from 10 m
  land_cover                NLCD 2021 class, modal in cell
  ndvi, ndsi                Sentinel-2 L2A late-summer 2025 median composite, from 20 m

Sources are clipped once to data/raw/<source>/ by the fetchers in rainier3d.surface.layers; a source that
cannot be reached is skipped with a warning, never filled.
"""

from __future__ import annotations

import argparse
import logging

import numpy as np
import xarray as xr

from rainier3d.config.domain import load_domain
from rainier3d.io.store import write
from rainier3d.surface import imagery
from rainier3d.surface import layers as L

log = logging.getLogger("s2")


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default=None)
    ap.add_argument("--hr", action="store_true", help="use NHDPlus HR flowlines (downloads ~870 MB once)")
    ap.add_argument(
        "--ma", action="store_true", help="download the Ma et al. 2026 clip if not cached (slow, ~1 GB)"
    )
    a = ap.parse_args()
    dom = load_domain(a.profile)
    out = {}

    out["soil_thickness"] = L.soil_thickness(dom)

    for name, fetch, key in (
        ("water_table_depth", lambda d: L.fetch_ma_wtd(d, download=a.ma), "ma2026_wtd"),
        ("water_table_depth_fan", L.fetch_fan_wtd, "fan2017_wtd"),
    ):
        try:
            out[name] = L.water_table_depth(dom, fetch(dom), name, key)
        except Exception as e:  # a source outage skips the layer; it is never filled
            log.warning("%s skipped: %s", name, e)

    hr_cache = dom.path("raw") / "hydrology" / "nhdplus_hr_flowlines.gpkg"
    fl = L.fetch_flowlines_hr(dom) if (a.hr or hr_cache.exists()) else L.fetch_flowlines(dom)
    out["stream_order"] = L.stream_order(
        dom, fl, "nhdplus_hr" if "nhdplusid" in fl.columns else "nhdplus_v21"
    )

    for fetch, fn in ((L.fetch_eth_canopy, L.canopy_height), (L.fetch_nlcd, L.land_cover)):
        try:
            da = fn(dom, fetch(dom))
            out[da.name] = da
        except Exception as e:
            log.warning("%s skipped: %s", fn.__name__, e)

    try:
        s2 = imagery.fetch_s2_composite(dom)
        for k, a_ in imagery.indices_on_grid(dom, s2).items():
            ln = {
                "ndvi": "NDVI, Sentinel-2 late-summer 2025 median",
                "ndsi": "NDSI, Sentinel-2 late-summer 2025 median",
            }[k]
            out[k] = L._da(
                dom, a_.astype("float32"), k, {"units": "1", "long_name": ln}, ["sentinel2_l2a"], k, 20
            )
    except Exception as e:
        log.warning("Sentinel-2 indices skipped: %s", e)

    ds = xr.Dataset(out)
    ds.attrs = {"crs": dom.crs, "vertical_datum": dom.vertical_datum, "domain": dom.name}
    p = write(ds, dom.path("processed") / "surface_layers.zarr")
    for k, v in ds.data_vars.items():
        a_ = v.values.astype(float)
        ok = np.isfinite(a_)
        log.info(
            "%-26s %5.1f %% valid  p5/p50/p95 = %s",
            k,
            100 * ok.mean(),
            np.round(np.percentile(a_[ok], [5, 50, 95]), 2) if ok.any() else "-",
        )
    log.info("wrote %s", p)


if __name__ == "__main__":
    main()
