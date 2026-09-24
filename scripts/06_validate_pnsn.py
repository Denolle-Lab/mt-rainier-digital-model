"""S6: PNSN travel-time check of the fused model against the PNSN 1D model.

Writes outputs/pnsn_residuals.csv (per pick), outputs/pnsn_stations.csv (per station terms),
outputs/pnsn_report.txt (summary), and configs/validation_events.csv (the event set, so reruns
compare like with like).
"""

from __future__ import annotations

import argparse
import logging

import numpy as np

from rainier3d.config.domain import REPO, load_domain
from rainier3d.io.store import read_tree
from rainier3d.validate import pnsn

EVENTS = REPO / "configs" / "validation_events.csv"


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default=None)
    ap.add_argument("--solver", default="pykonal", choices=["pykonal", "fteikpy"])
    a = ap.parse_args()
    dom = load_domain(a.profile)
    vc = dom.cfg["validation"]

    picks, stations, ev = pnsn.prepare(dom, EVENTS)
    xs, ys, zs = pnsn.grid_axes(dom, vc["dx"], vc["z_top"], vc["z_bot"])
    tree = read_tree(dom.path("processed") / "model.zarr")
    zz = np.broadcast_to(zs[:, None, None], (zs.size, xs.size, ys.size))
    src = list(zip(stations.x, stations.y, stations.elev, strict=True))
    rec = list(zip(ev.x, ev.y, ev.z, strict=True))
    eidx = {e: i for i, e in enumerate(ev.event)}
    sidx = {(n, s): i for i, (n, s) in enumerate(zip(stations.net, stations.sta, strict=True))}
    for phase, var in (("P", "vp"), ("S", "vs")):
        models = {"1d": pnsn.pnsn_1d(zz, phase), "3d": pnsn.model_on_grid(tree, var, xs, ys, zs, phase)}
        for m, vel in models.items():
            tt = pnsn.travel_times(vel, xs, ys, zs, vc["dx"], src, rec, solver=a.solver)
            sel = picks.phase == phase
            picks.loc[sel, f"tt_{m}"] = [
                tt[sidx[(n, s)], eidx[e]]
                for n, s, e in zip(picks.net[sel], picks.sta[sel], picks.event[sel], strict=True)
            ]
        logging.info("%s travel times done", phase)

    picks = picks.dropna(subset=["tt_1d", "tt_3d"])
    out = dom.path("outputs")
    picks.to_csv(out / "pnsn_residuals.csv", index=False)
    summ, st = pnsn.summarize(picks)
    st.to_csv(out / "pnsn_stations.csv", index=False)
    corr = pnsn.station_correlation(st)
    pnsn.write_report(out / "pnsn_report.txt", summ, corr)
    logging.info("\n%s\n%s", (out / "pnsn_report.txt").read_text(), "")


if __name__ == "__main__":
    main()
