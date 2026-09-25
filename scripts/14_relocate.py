"""S14: relocate the PNSN validation events in a velocity model and score it by the residuals left.

A fair comparison of models: each one gets its own hypocentres and origin times, so no model is favoured by
catalogue locations made with another. Writes outputs/relocation/<name>/{catalog.csv, picks.csv, stats.json}.

Usage: pixi run s14 -- --model 1d --name pnsn1d
       pixi run s14 -- --model data/processed/model.zarr --name fused
"""

from __future__ import annotations

import argparse
import json
import logging
import time

import numpy as np

from rainier3d.config.domain import REPO, load_domain
from rainier3d.io.store import read_tree
from rainier3d.validate import locate as L
from rainier3d.validate import pnsn


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, help="'1d' or a model.zarr path")
    ap.add_argument("--name", required=True)
    ap.add_argument(
        "--skin", type=int, default=1, help="rock cells above the DEM; -1: rock-filled air, no ground bound"
    )
    a = ap.parse_args()
    dom = load_domain()
    grid, picks, stations, sta_xyd, events = L.setup(dom, REPO / "configs" / "validation_events.csv")
    zz = np.broadcast_to(grid.zs[:, None, None], (grid.zs.size, grid.xs.size, grid.ys.size))
    tree = None if a.model == "1d" else read_tree(REPO / a.model)
    ground = L.ground_on_grid(read_tree(dom.path("processed") / "model.zarr"), grid)
    t = time.time()
    T = {}
    for ph, var in (("P", "vp"), ("S", "vs")):
        v = (
            pnsn.pnsn_1d(zz, ph)
            if tree is None
            else pnsn.model_on_grid(tree, var, grid.xs, grid.ys, grid.zs, ph)
        )
        v = L.with_topography(v, grid, ground, a.skin)
        T[ph] = L.fields(L.Grid.xyd(v), grid, sta_xyd)
    logging.info("fields: %.0f s", time.time() - t)
    cat, pk = L.locate_all(T, grid, picks, events, ground=None if a.skin < 0 else ground)
    out = dom.path("outputs") / "relocation" / a.name
    out.mkdir(parents=True, exist_ok=True)
    cat = cat.join(events[["x", "y", "d"]].add_suffix("_catalog"))
    cat.to_csv(out / "catalog.csv")
    pk.to_csv(out / "picks.csv", index=False)
    stats = {
        "model": a.model,
        "skin_cells": a.skin,
        "above_ground_gt_50m": int((cat.above_ground_m > 50).sum()) if a.skin >= 0 else None,
        "residuals": L.residual_stats(pk),
        "n_events": int(len(cat)),
        "shift_from_catalog_m": {
            "horizontal_median": float(np.median(np.hypot(cat.x - cat.x_catalog, cat.y - cat.y_catalog))),
            "depth_mean": float((cat.d - cat.d_catalog).mean()),
            "depth_median": float((cat.d - cat.d_catalog).median()),
        },
        "formal_sd_median_m": {k: float(cat[k].median()) for k in ("sx", "sy", "sd")},
    }
    (out / "stats.json").write_text(json.dumps(stats, indent=1))
    logging.info("\n%s", json.dumps(stats, indent=1))


if __name__ == "__main__":
    main()
