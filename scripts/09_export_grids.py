"""S9: export the fused model for ray tracing -> outputs/grids/.

  rainier3d_fused_<dx>m.nc        CF netCDF4, UTM 10N, z = elevation (m); vp, vs, rho, qp, qs, air
  nll/rainier3d.{P,S}.mod.hdr/buf NonLinLoc SLOW_LEN grids (km, depth down, TRANSFORM NONE)
  rainier3d_emc.nc                EMC-style lon/lat/depth netCDF3 (km/s, g/cm3)

Usage: pixi run s9 [-- --dx 500 --dz 500]
"""

from __future__ import annotations

import argparse
import logging

import numpy as np

from rainier3d.config.domain import load_domain
from rainier3d.export import grids
from rainier3d.io.store import read_tree


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--dx", type=float, default=500.0, help="horizontal spacing (m)")
    ap.add_argument("--dz", type=float, default=500.0, help="vertical spacing (m); = dx for NonLinLoc")
    ap.add_argument("--no-emc", action="store_true")
    ap.add_argument(
        "--nll-air-velocity",
        type=float,
        default=0.0,
        help="m/s for NonLinLoc air above a 2-cell rock skin (default 0: air keeps rock velocity)",
    )
    a = ap.parse_args()
    dom = load_domain()
    out = dom.path("outputs") / "grids"
    tree = read_tree(dom.path("processed") / "model.zarr")

    g = grids.uniform(tree, dx=a.dx, dz=a.dz)
    nc = grids.write_netcdf(g, out / f"rainier3d_fused_{int(a.dx)}m.nc")
    logging.info(
        "%s: %s cells, vp %.0f-%.0f m/s, %.1f %% air",
        nc.name,
        g["vp"].shape,
        float(np.nanmin(g.vp)),
        float(np.nanmax(g.vp)),
        100 * float(g.air.mean()),
    )
    if np.isclose(a.dx, a.dz):
        av = a.nll_air_velocity or None
        for p in grids.write_nll(g, out / "nll" / "rainier3d", air_velocity=av):
            logging.info("wrote %s", p)
    if not a.no_emc:
        logging.info("wrote %s", grids.write_emc(tree, dom, out / "rainier3d_emc.nc"))


if __name__ == "__main__":
    main()
