"""S2: environmental surface layers -> data/processed/surface_layers.zarr (to /surface in S5).

  soil_thickness            SOLUS100 depth to lithic contact (m, capped at 2.01)
  water_table_depth         Ma et al. 2026 water-table depth, mean (m below ground), from ~24 m
  water_table_depth_fan     Fan et al. 2017 water-table depth, annual mean (m below ground), from 30 arcsec
  stream_order              Strahler order of NHDPlus flowlines in the cell (HR if cached, else v2.1)
  canopy_height             ETH global canopy height 2020, Lang et al. 2023 (m), from 10 m
  land_cover                NLCD 2021 class, modal in cell
  ndvi, ndsi                Sentinel-2 L2A late-summer 2025 median composite, from 20 m
  clay/sand/silt/bulk_density/rock_fragments/organic_carbon_0_100cm
                            SOLUS100 depth-weighted means over 0-1 m (configs/soil.yaml)
  soil_texture_class        USDA texture class of those clay, sand and silt means
  depth_to_restriction      SOLUS100 depth to any restrictive layer (m)
  log10_ksat_0_100cm, theta_s_0_100cm
                            POLARIS harmonic-mean ksat and mean porosity over 0-1 m
  depth_to_bedrock          Shangguan et al. 2017 (SoilGrids250m 2017), m
  vs30                      USGS global hybrid Vs30 (m/s)

The depth profiles (SOLUS at 0-1.5 m, POLARIS layers to 2 m) go to data/processed/soil_profile.zarr (/soil in
S5).

Sources are clipped once to data/raw/<source>/ by the fetchers in rainier3d.surface.layers; a source that
cannot be reached is skipped with a warning, never filled.
"""

from __future__ import annotations

import argparse
import logging

import numpy as np
import xarray as xr

from rainier3d.config.domain import load_domain
from rainier3d.io.store import read, write
from rainier3d.surface import imagery
from rainier3d.surface import layers as L
from rainier3d.surface import soil as SL

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

    cfg = SL.config()
    surf = dom.path("processed") / "surface.zarr"  # S1: ice thickness for the glacier mask
    ice = (read(surf)["ice_thickness"].values > 0) if (cfg["mask_glaciers"] and surf.exists()) else None
    ice = None if ice is None else xr.DataArray(ice, dims=("y", "x"), coords={"y": dom.y, "x": dom.x})
    n0 = len(out)
    profiles = []
    for name, prof_fn, summ_fn in (
        ("SOLUS100", SL.solus_profile, SL.solus_summaries),
        ("POLARIS", SL.polaris_profile, SL.polaris_summaries),
    ):
        try:
            prof = prof_fn(dom, cfg)
            out.update(summ_fn(dom, prof, cfg))
            profiles.append(prof)
        except Exception as e:  # a source outage skips the layer; it is never filled
            log.warning("%s profile skipped: %s", name, e)
    for fn in (SL.depth_to_restriction, SL.depth_to_bedrock, SL.vs30):
        try:
            da = fn(dom, cfg)
            out[da.name] = da
        except Exception as e:
            log.warning("%s skipped: %s", fn.__name__, e)
    if ice is not None:  # soil and regolith layers added above; vs30 is kept on the ice
        for k in list(out)[n0:]:
            if k != "vs30":
                out[k] = SL.mask_ice(out[k], ice)
        profiles = [p.map(lambda v: SL.mask_ice(v, ice), keep_attrs=True) for p in profiles]
    if profiles:
        sp = xr.merge(profiles, combine_attrs="drop_conflicts")
        sp.attrs = {"crs": dom.crs, "vertical_datum": dom.vertical_datum, "domain": dom.name}
        log.info("wrote %s", write(sp, dom.path("processed") / "soil_profile.zarr"))

    if {"soil_texture_class", "vs30", "depth_to_bedrock", "theta_s_0_100cm"} <= set(out):
        import json

        summ = SL.summary(out, cfg, None if ice is None else ice.values)
        p_sum = dom.path("outputs") / "soil_layers_summary.json"
        p_sum.parent.mkdir(parents=True, exist_ok=True)
        p_sum.write_text(json.dumps(summ, indent=1))
        log.info("soil checks %s -> %s", summ["checks"], p_sum)

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
