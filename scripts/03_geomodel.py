"""S3: rule-based 3D geology -> data/processed/geomodel.zarr (DataTree: /surface, /L1, /L2, /L3)."""

from __future__ import annotations

import argparse
import logging

import numpy as np
import xarray as xr

from rainier3d.config.domain import load_domain
from rainier3d.geomodel import rules
from rainier3d.io.store import read, write
from rainier3d.petro.table import unit_names, units_config


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default=None)
    a = ap.parse_args()
    dom = load_domain(a.profile)
    surf = read(dom.path("processed") / "surface.zarr")
    surf2, levels = rules.build(dom, surf, units_config())
    tree = xr.DataTree.from_dict({"/surface": surf2, **{f"/{k}": v for k, v in levels.items()}})
    tree.attrs = {
        "crs": dom.crs,
        "vertical_datum": dom.vertical_datum,
        "units": str(unit_names()),
        "method": "M1 rule-based geology (rainier3d.geomodel.rules)",
    }
    write(tree, dom.path("processed") / "geomodel.zarr")

    base = surf2["edifice_base"]
    logging.info(
        "edifice footprint %.0f km2, base %.0f-%.0f m",
        float(surf2["footprint"].sum()) * dom.surface_res_m**2 / 1e6,
        float(base.min()),
        float(base.max()),
    )
    names = unit_names()
    for k, ds in levels.items():
        u, n = np.unique(ds["unit"].values, return_counts=True)
        logging.info(
            "%s %s: %s",
            k,
            ds["unit"].shape,
            ", ".join(f"{names[int(i)]} {c / n.sum():.1%}" for i, c in zip(u, n, strict=True)),
        )


if __name__ == "__main__":
    main()
