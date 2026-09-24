"""S7: export VTK files, QC sections, a PNG render and a standalone HTML 3D view.

--show opens the interactive PyVista window instead of rendering off screen.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import pandas as pd

from rainier3d.config.domain import load_domain
from rainier3d.export.vtk import write_all
from rainier3d.io.store import read_tree
from rainier3d.viz.scene import build_scene
from rainier3d.viz.sections import section_figure


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default=None)
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--drape", default="i432", help="overlay GeoTIFF name from S8 (i432, soil) or 'none'")
    ap.add_argument("--das", default=str(Path.home() / "Downloads/Paradise2NisquallyEntrace_Channels.csv"))
    a = ap.parse_args()
    dom = load_domain(a.profile)
    out = dom.path("outputs")
    tree = read_tree(dom.path("processed") / "model.zarr")

    for p in write_all(tree, out / "vtk"):
        logging.info("wrote %s", p)
    sx, sy = dom.summit_xy
    section_figure(tree, "x", sy, out / "section_EW_summit.png")
    section_figure(tree, "y", sx, out / "section_NS_summit.png")

    ev = None
    res = out / "pnsn_residuals.csv"
    if res.exists():
        from pyproj import Transformer

        ev = pd.read_csv(res).drop_duplicates("event")
        ev["x"], ev["y"] = Transformer.from_crs("EPSG:4326", dom.crs, always_xy=True).transform(
            ev.lon.values, ev.lat.values
        )
        ev["z"] = -ev.depth_km * 1e3

    # optional layers from S8 (atlas): the I-432 KMZ drape, operating sensors, the DAS fiber
    import json

    from rainier3d.config.domain import REPO
    from rainier3d.sensors.inventory import das_channels, families

    tif = dom.path("processed") / "overlays" / f"{a.drape}.tif"
    atlas = REPO / "web" / "atlas" / "data"
    sites = (
        json.loads((atlas / "sites.geojson").read_text())["features"]
        if (atlas / "sites.geojson").exists()
        else None
    )
    das = das_channels(a.das) if a.das and Path(a.das).exists() else None
    fam = {k: v["color"] for k, v in families()["families"].items()}
    pl = build_scene(
        tree,
        (sx, sy),
        ev,
        off_screen=not a.show,
        drape_tif=tif if tif.exists() and a.drape != "none" else None,
        crs=dom.crs,
        sites=sites,
        das=das,
        family_colors=fam,
    )
    if a.show:
        pl.show()
        return
    pl.screenshot(out / "rainier3d_view.png")
    try:
        pl.trame.export_html(out / "rainier3d_view.html")
        logging.info("wrote %s", out / "rainier3d_view.html")
    except Exception as e:  # export needs trame-vtk; the PNG is still written
        logging.warning("HTML export failed: %s", e)
    pl.close()


if __name__ == "__main__":
    main()
