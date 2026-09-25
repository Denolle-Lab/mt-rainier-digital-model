"""S24: mass movements and faults -> outputs/mass_movements/, the paper figure, and the viewer layers.

Fetches (cached under data/raw/<source>/, see rainier3d.surface.mass_movements):
  wgs_landslides/        Washington landslide inventory: lidar-protocol deposits, recent slides, compilation
  allstadt2017/          seismically recorded mass movements (Allstadt et al. 2017), Events.csv
  usgs_rainier_hazards/  lahar inundation zones of Hoblitt et al. (1998), OFR 2007-1220 shapefiles
  geology/               DNR 1:100k faults and Quaternary faults (the lahar deposits are S1's Qvl map units)

Writes:
  outputs/mass_movements/flows.gpkg     lahar deposits and debris flows (polygons, class 1-4)
  outputs/mass_movements/events.gpkg    every other event as a point (crown, mapped point or seismic location)
  outputs/mass_movements/events.csv     the same, lon/lat, for the report and the viewer
  outputs/mass_movements/faults.gpkg, lahar_zones.gpkg, summary.csv
  docs/paper/figures/fig16_mass_movements.png
  <atlas>/model/mass_flows.png, mass_flows.u16.bin, mass_events.json and a layers.json entry, if the viewer
  bundle exists (S11 also appends them when it rebuilds the bundle)

Usage: pixi run s24 [-- --atlas web/viewer/site/public/atlas]
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import pandas as pd

from rainier3d.config.domain import REPO, load_domain
from rainier3d.io.store import read_tree
from rainier3d.surface import mass_movements as M
from rainier3d.surface.geology import fetch_map_units

FIG = REPO / "docs" / "paper" / "figures" / "fig16_mass_movements.png"


def summary(flows, events, faults, zones) -> pd.DataFrame:
    rows = []
    for (cls, name), g in flows.groupby(["cls", "name"]):
        rows.append(
            (
                "flow",
                name,
                "wgs_landslide_inventory" if cls == 4 else "dnr_gems_100k",
                len(g),
                round(g.area.sum() / 1e6, 1),
            )
        )
    for (src, loc, cls), g in events.groupby(["source", "located", "cls"]):
        rows.append((f"event ({loc})", cls, src, len(g), None))
    for key, g in faults.items():
        rows.append(
            (
                "fault",
                key,
                "dnr_gems_100k" if key == "gems" else "dnr_quaternary_faults",
                len(g),
                round(g.length.sum() / 1e3, 1),
            )
        )
    for z, g in zones.groupby("zone"):
        rows.append(("hazard zone", z, "schilling_2008", len(g), round(g.area.sum() / 1e6, 1)))
    return pd.DataFrame(rows, columns=["part", "class", "source", "count", "km2_or_km"])


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--atlas", default=str(REPO / "web" / "viewer" / "site" / "public" / "atlas"))
    ap.add_argument("--no-figure", action="store_true")
    a = ap.parse_args()
    dom = load_domain()
    flows, events = M.build_catalogue(
        dom, fetch_map_units(dom), dom.path("raw") / "dem" / "3dep_30m_rainier-v0.tif"
    )
    faults = {k: g.clip(dom.bounds) for k, g in M.fetch_faults(dom).items()}
    zones = M.fetch_lahar_zones(dom).clip(dom.bounds)

    out = dom.path("outputs") / "mass_movements"
    out.mkdir(parents=True, exist_ok=True)
    flows.to_file(out / "flows.gpkg")
    events.to_file(out / "events.gpkg")
    ll = events.to_crs(4326)
    ll.assign(lon=ll.geometry.x.round(6), lat=ll.geometry.y.round(6)).drop(columns="geometry").to_csv(
        out / "events.csv", index=False
    )
    pd.concat([g.assign(kind=k) for k, g in faults.items()]).to_file(out / "faults.gpkg")
    zones.to_file(out / "lahar_zones.gpkg")
    tab = summary(flows, events, faults, zones)
    tab.to_csv(out / "summary.csv", index=False)
    logging.info("mass movements:\n%s", tab.to_string(index=False))

    if not a.no_figure:
        from rainier3d.report.figures import fig_mass_movements

        tree = read_tree(dom.path("processed") / "model.zarr")
        logging.info(
            "figure %s", fig_mass_movements(tree, flows, events, faults, zones, FIG).relative_to(REPO)
        )

    atlas = Path(a.atlas).expanduser()
    if (atlas / "model" / "layers.json").exists():
        from rainier3d.export.atlas import append_mass_movements

        r = append_mass_movements(atlas, flows, events)
        logging.info(
            "viewer: %d flow polygons, %d event points -> %s", r["flows"], r["events"], atlas / "model"
        )
    else:
        logging.info("no viewer bundle at %s: run pixi run viewer-data and s11 first", atlas)


if __name__ == "__main__":
    main()
