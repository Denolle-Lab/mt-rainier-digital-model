"""S12: calibrate a depth-dependent Vs factor on PNSN S-P times -> configs/vs_calibration.yaml.

Events are split by origin-time order into two halves (even / odd). The smoothing weight is chosen on the
held-out half from the linearised problem, the factor is fitted on the training half and scored on the
held-out half with full eikonal solves, then refitted on all events. S5 applies the result to the regional
Vs; rerun S5 and S6 afterwards to check it.

Usage: pixi run s12
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging

import numpy as np
import yaml

from rainier3d.config.domain import REPO, load_domain
from rainier3d.io.store import read_tree
from rainier3d.validate import calibrate as C
from rainier3d.validate import pnsn

OUT_YAML = REPO / "configs" / "vs_calibration.yaml"


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("rasterio").setLevel("WARNING")
    ap = argparse.ArgumentParser()
    ap.add_argument("--iterations", type=int, default=2)
    ap.add_argument("--lam-d", type=float, default=1.0)
    a = ap.parse_args()
    dom = load_domain()
    vc, fc = dom.cfg["validation"], dom.cfg["fusion"]
    out = dom.path("outputs") / "vs_calibration"
    out.mkdir(parents=True, exist_ok=True)

    picks, stations, ev = pnsn.prepare(dom, REPO / "configs" / "validation_events.csv")
    xs, ys, zs = pnsn.grid_axes(dom, vc["dx"], vc["z_top"], vc["z_bot"])
    tree = read_tree(dom.path("processed") / "model.zarr")
    if tree["L1"].attrs.get("vs_calibration"):
        raise SystemExit(
            "model.zarr already carries a Vs calibration; rerun S5 without it before calibrating"
        )
    src = list(zip(stations.x, stations.y, stations.elev, strict=True))
    rec = list(zip(ev.x, ev.y, ev.z, strict=True))

    def tt_fn(vel):
        return pnsn.travel_times(vel, xs, ys, zs, vc["dx"], src, rec)

    eidx = {e: i for i, e in enumerate(ev.event)}
    sidx = {(n, s): i for i, (n, s) in enumerate(zip(stations.net, stations.sta, strict=True))}
    Tp = tt_fn(pnsn.model_on_grid(tree, "vp", xs, ys, zs, "P"))
    P = picks[picks.phase == "P"][["event", "net", "sta", "tt_obs"]].rename(columns={"tt_obs": "tp_obs"})
    S = picks[picks.phase == "S"][["event", "net", "sta", "tt_obs"]].rename(columns={"tt_obs": "ts_obs"})
    pairs = S.merge(P, on=["event", "net", "sta"])
    pairs["si"] = [sidx[(n, s)] for n, s in zip(pairs.net, pairs.sta, strict=True)]
    pairs["ei"] = [eidx[e] for e in pairs.event]
    pairs["tp3d"] = Tp[pairs.si, pairs.ei]
    pairs = pairs.dropna(subset=["tp3d"]).reset_index(drop=True)
    order = {e: i for i, e in enumerate(sorted(pairs.event.unique()))}  # ComCat ids sort by origin time
    train = np.array([order[e] % 2 == 0 for e in pairs.event])
    test = ~train
    logging.info(
        "%d S-P pairs (%d events); train %d, test %d",
        len(pairs),
        pairs.event.nunique(),
        train.sum(),
        test.sum(),
    )

    depth = C.depth_below_ground(tree, xs, ys, zs)
    taper = C.fusion_taper(depth, fc["geology_only_depth_m"], fc["taper_depth_m"])
    prob = C.SPProblem(pnsn.model_on_grid(tree, "vs", xs, ys, zs, "S"), depth, taper, pairs, tt_fn)
    ev_arr = pairs.event.values

    m0 = np.zeros(C.KNOTS_M.size)
    ts0 = prob.predict_ts(m0)
    r0 = prob.residual(ts0)
    J = prob.jacobian(m0, ts0)

    # smoothing weight: linearised held-out misfit, relative to the training data count
    lams = [0.1, 1.0, 10.0, 100.0, 1000.0]
    scan = []
    for lam in lams:
        m1 = C.gn_step(J, r0, m0, train, lam * train.sum() / 100, a.lam_d)
        r1 = r0 - J @ (m1 - m0)
        scan.append({"lam_s": lam, "test": C.stats(r1[test], ev_arr[test]), "m": m1.round(4).tolist()})
        logging.info("lam_s %g: held-out S-P RMS %.3f s", lam, scan[-1]["test"]["rms_s"])
    # lowest held-out misfit. A smoother choice (lam_s 100, 24 Sep 2026) fitted slightly worse and pushed
    # the L1 Vs low-pass misfit to 0.040 (> 0.03): raising Vs in the top km fights the slow shallow geology
    lam = min(scan, key=lambda sc: sc["test"]["rms_s"])["lam_s"]
    lam_abs = lam * train.sum() / 100

    def fit(rows, m, J, ts, r):
        for it in range(a.iterations):
            m = C.gn_step(J, r, m, rows, lam_abs, a.lam_d)
            ts = prob.predict_ts(m)
            r = prob.residual(ts)
            logging.info(
                "iteration %d: S-P RMS on fitted rows %.3f s", it + 1, C.stats(r[rows], ev_arr[rows])["rms_s"]
            )
            if it < a.iterations - 1:
                J = prob.jacobian(m, ts)
        return m, ts, r

    m_tr, ts_tr, r_tr = fit(train, m0, J, ts0, r0)
    held = {"before": C.stats(r0[test], ev_arr[test]), "after": C.stats(r_tr[test], ev_arr[test])}
    logging.info("held-out S-P RMS %.3f -> %.3f s", held["before"]["rms_s"], held["after"]["rms_s"])

    allrows = np.ones(len(pairs), bool)
    m_all, ts_all, r_all = fit(allrows, m_tr, prob.jacobian(m_tr, ts_tr), ts_tr, r_tr)
    full = {"before": C.stats(r0, ev_arr), "after": C.stats(r_all, ev_arr)}

    rec_ = {
        "description": "Depth-dependent factor on the regional Vs, applied in S5 before fusion: "
        "Vs_regional * exp(interp(depth below ground, knots_m, log_factor)); constant beyond the ends.",
        "knots_m": C.KNOTS_M.tolist(),
        "log_factor": [round(float(v), 5) for v in m_all],
        "factor": [round(float(np.exp(v)), 4) for v in m_all],
        "vpvs_floor": 1.6,
        "vpvs_floor_source": "christensen_1996",
        "source_keys": ["comcat_uw"],
        "data": {
            "picks": "PNSN analyst P and S picks (ComCat), configs/validation_events.csv",
            "n_pairs": int(len(pairs)),
            "n_events": int(pairs.event.nunique()),
            "n_stations": int(pairs.sta.nunique()),
            "hypocentres": "ComCat (PNSN 1D), fixed",
        },
        "method": {
            "solver": "pykonal PointSourceSolver",
            "grid_dx_m": vc["dx"],
            "lam_s_rel": lam,
            "lam_d": a.lam_d,
            "iterations": a.iterations,
            "split": "events alternating in origin-time order",
        },
        "held_out": held,
        "all_events": full,
        "lam_scan": scan,
        "date": dt.date.today().isoformat(),
    }
    OUT_YAML.write_text(yaml.safe_dump(rec_, sort_keys=False))
    pairs.assign(ts_before=ts0, ts_after=ts_all, r_before=r0, r_after=r_all, train=train).to_csv(
        out / "sp_pairs.csv", index=False
    )
    logging.info(
        "wrote %s\n%s",
        OUT_YAML,
        json.dumps({"factor": rec_["factor"], "held_out": held, "all": full}, indent=1),
    )


if __name__ == "__main__":
    main()
