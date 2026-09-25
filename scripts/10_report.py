"""S10: build the model report -> docs/report/rainier3d_subsurface_model.html (single self-contained file).

Figures are regenerated from the current model and outputs (S1-S9 must have run); the text lives in
docs/report/subsurface_model.md; references come from docs/report/references_resolved.json.
Use --figures-only / --html-only to redo one half. Figures 10-13 (calibration and validation) are
written by S16 and S21.
"""

from __future__ import annotations

import argparse
import json
import logging

from rainier3d.config.domain import REPO, load_domain
from rainier3d.report import figures as F
from rainier3d.report.render import render
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
    for p in made:
        logging.info("figure %s", p.relative_to(REPO))


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--figures-only", action="store_true")
    ap.add_argument("--html-only", action="store_true")
    a = ap.parse_args()
    dom = load_domain()
    if not a.html_only:
        figures(dom)
    if not a.figures_only:
        p = render(
            DOCS / "subsurface_model.md",
            DOCS / "rainier3d_subsurface_model.html",
            DOCS / "references_resolved.json",
            title="rainier3d: a geology-driven 3D velocity model of Mount Rainier",
            description="How the rainier3d M1 subsurface model (Vp, Vs, density, Q) of Mount Rainier "
            "and the West Rainier Seismic Zone was built, checked against PNSN travel times, "
            "and how to extract it.",
        )
        logging.info("wrote %s (%.1f MB)", p.relative_to(REPO), p.stat().st_size / 1e6)


if __name__ == "__main__":
    main()
