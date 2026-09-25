"""S4: geology -> Vp, Vs, rho, Qp, Qs -> data/processed/properties_geology.zarr (/L1, /L2, /L3).

The rock-unit multipliers fitted by S13 (``geology`` block of configs/velocity_calibration.yaml) are applied
unless --no-calibration is given (to build the base model of S13).
"""

from __future__ import annotations

import argparse
import logging

import numpy as np
import xarray as xr
import yaml

from rainier3d.config.domain import REPO, load_domain
from rainier3d.io.store import read_tree, write
from rainier3d.petro.table import perturbations, petro_table
from rainier3d.properties.assign import assign


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default=None)
    ap.add_argument("--no-calibration", action="store_true", help="ignore the S13 geology calibration")
    a = ap.parse_args()
    dom = load_domain(a.profile)
    geo = read_tree(dom.path("processed") / "geomodel.zarr")
    table, pert = petro_table(), perturbations()
    cal_path = REPO / "configs" / "velocity_calibration.yaml"
    cal = yaml.safe_load(cal_path.read_text()) if cal_path.exists() and not a.no_calibration else {}
    geo_cal = cal.get("geology")
    out = {f"/{k}": assign(geo[k].to_dataset(), table, pert, geo_cal) for k in dom.levels}
    tree = xr.DataTree.from_dict(out)
    tree.attrs = {
        "crs": dom.crs,
        "vertical_datum": dom.vertical_datum,
        "method": "M1 geology model: crack closure + Brocher 2005 + placeholder perturbations",
        "geology_calibration": f"configs/velocity_calibration.yaml ({cal['date']})" if geo_cal else "none",
    }
    write(tree, dom.path("processed") / "properties_geology.zarr")
    for k, ds in out.items():
        logging.info(
            "%s vp %.0f-%.0f  vs %.0f-%.0f  rho %.0f-%.0f  vp/vs %.2f-%.2f",
            k,
            *(float(f(ds[v])) for v in ("vp", "vs", "rho") for f in (np.nanmin, np.nanmax)),
            float(np.nanmin(ds.vp / ds.vs)),
            float(np.nanmax(ds.vp / ds.vs)),
        )


if __name__ == "__main__":
    main()
