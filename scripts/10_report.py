"""S10: report figures from the built model -> docs/report/figures/ (committed).

The figures need the model and outputs (S1-S9 and S17-S19 must have run). The calibration and validation
figures (fig10-fig13) are written by S16 and S21, and the alteration maps by S22. The text is
docs/report/rainier3d.md; S23 (pixi run -e paper report) builds the HTML page and the ESSD PDF from it
without model data.
"""

from __future__ import annotations

import json
import logging

import xarray as xr
import yaml

from rainier3d.config.domain import REPO, load_domain
from rainier3d.report import figures as F
from rainier3d.sensors.inventory import das_channels
from rainier3d.validate.pnsn import pnsn_1d

DOCS = REPO / "docs" / "report"
FIG = DOCS / "figures"
DAS = "~/Downloads/Paradise2NisquallyEntrace_Channels.csv"


def figures(dom):
    from pathlib import Path

    FIG.mkdir(parents=True, exist_ok=True)
    tree = F.open_tree(dom.path("processed") / "model.zarr")
    atlas = REPO / "web" / "atlas" / "data"
    sites = json.loads((atlas / "sites.geojson").read_text())
    events = json.loads((atlas / "events.geojson").read_text())
    das = das_channels(Path(DAS).expanduser())
    sx, sy = dom.summit_xy
    x0, y0, x1, y1 = dom.bounds
    a = ((x0, sy), (x1, sy))
    b = ((sx, y0), (sx, y1))
    out = dom.path("outputs")
    made = [
        F.fig_map(tree, dom, sites, events, das, FIG / "fig1_map.png", a, b),
        F.fig_fusion(tree, dom, FIG / "fig3_fusion.png", sy),
        F.fig_sections(tree, dom, events, FIG / "fig4_section_AA.png", "x", sy, "A–A′"),
        F.fig_sections(
            tree, dom, events, FIG / "fig5_section_BB.png", "y", sx, "B–B′", variables=("vs", "vpvs", "unit")
        ),
        F.fig_profiles(
            tree,
            dom,
            FIG / "fig6_profiles.png",
            [("Summit", -121.7603, 46.8523), ("Longmire", -121.81, 46.75), ("WRSZ", -121.97, 46.86)],
            pnsn_1d,
        ),
        F.fig_pnsn(out / "pnsn_residuals.csv", out / "pnsn_stations.csv", FIG / "fig7_pnsn.png"),
        F.fig_glaciers(out / "glacier_thickness_check.csv", FIG / "fig2_glaciers.png"),
        F.fig_surface_layers(tree, dom, FIG / "fig8_surface_layers.png"),
    ]
    canopy = dom.path("processed") / "surface_canopy.zarr"
    if canopy.exists():
        made.append(
            F.fig_canopy(xr.open_zarr(canopy, consolidated=False), tree, dom, FIG / "fig14_canopy.png")
        )
    load = dom.path("processed") / "edifice_load.zarr"
    if load.exists():
        gcfg = yaml.safe_load((REPO / "configs" / "gnss.yaml").read_text())
        ltree = xr.open_datatree(load, engine="zarr", consolidated=False)
        grid = dom.path("processed") / "gnss" / "strain_grid.nc"
        made.append(
            F.fig_strain(
                grid, out / "gnss" / "velocities.csv", ltree, tree, dom, gcfg, FIG / "fig15_strain.png"
            )
        )
    for p in made:
        logging.info("figure %s", p.relative_to(REPO))


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    figures(load_domain())


if __name__ == "__main__":
    main()
