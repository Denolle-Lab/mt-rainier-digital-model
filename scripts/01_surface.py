"""S1: surface stack -> data/processed/surface.zarr (elevation, surface_unit, ice_thickness).

M1 covers DEM, geology and a placeholder ice thickness. Canopy, soil, hydrology and surface
alteration layers are M2.
"""

from __future__ import annotations

import argparse
import logging

import xarray as xr

from rainier3d.config.domain import load_domain
from rainier3d.io.store import write
from rainier3d.petro.table import units_config
from rainier3d.surface import dem as sdem
from rainier3d.surface import geology, glaciers


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default=None)
    a = ap.parse_args()
    dom = load_domain(a.profile)

    elev = sdem.dem_on_grid(dom, sdem.fetch_3dep(dom))

    gdf = geology.fetch_map_units(dom)
    cw = geology.build_crosswalk(list(gdf["MAP_UNIT_100K"]), geology.fetch_dmu_names())
    geology.write_crosswalk(cw)
    unit = geology.rasterize_units(dom, gdf, cw)

    g = units_config()["geometry"]["ice"]
    gdir = dom.path("raw") / "glaciers"
    layers = {"elevation": elev, "surface_unit": unit}
    if g["source"] == "iceboost_v2":
        ice, err = glaciers.iceboost_thickness(dom, gdir / "iceboost_v2", gdir / "rgi62_domain.csv")
        layers["ice_thickness_error"] = err
        gt = gdir / "glathida_T.csv"
        if gt.exists():
            import csv

            import pandas as pd

            rows = [
                r
                for r in csv.DictReader(gt.open())
                if r["LAT"] and 46.75 < float(r["LAT"]) < 46.95 and -121.95 < float(r["LON"]) < -121.6
            ]
            chk = pd.DataFrame(glaciers.glathida_check(gdir / "iceboost_v2", gdir / "rgi62_domain.csv", rows))
            chk.to_csv(dom.path("outputs") / "glacier_thickness_check.csv", index=False)
            logging.info("IceBoost v2 vs GlaThiDa (1981 GPR):\n%s", chk.to_string(index=False))
    else:
        ice = glaciers.perfect_plasticity_thickness(
            elev,
            unit == 1,
            dom.surface_res_m,
            g["tau_pa"],
            g["rho_kgm3"],
            g["slope_smoothing_m"],
            g["min_slope_deg"],
            g["max_thickness_m"],
        )
    layers["ice_thickness"] = ice

    ds = xr.Dataset(layers)
    ds.attrs = {"crs": dom.crs, "vertical_datum": dom.vertical_datum, "domain": dom.name}
    out = write(ds, dom.path("processed") / "surface.zarr")
    logging.info(
        "wrote %s: elevation %.0f-%.0f m, %d map symbols, ice volume %.2f km3",
        out,
        float(elev.min()),
        float(elev.max()),
        len(cw),
        float(ice.sum()) * dom.surface_res_m**2 / 1e9,
    )


if __name__ == "__main__":
    main()
