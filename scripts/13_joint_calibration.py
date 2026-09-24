"""S13: fit the geology model, and a static bias of the regional model, to PNSN P and S arrivals
with 3D relocation -> configs/velocity_calibration.yaml (version 2).

Parameters (15):
  geology, applied in S4 to every rock unit (rainier3d.properties.assign):
      ln_v0     zero-pressure Vp       V0 * exp(ln_v0)
      ln_pstar  crack-closure pressure P* * exp(ln_pstar)
      ln_vs     rock Vs                Vs * exp(ln_vs)      (a Vp/Vs shift)
  static bias of the regional model (CVM v1.7 / CRESCENT), applied in S5 before fusion:
      log-factors on regional Vp and Vs at 2, 4, 7, 11, 16, 25 km below ground, fixed at 0 at 0 and 1 km,
      so the top kilometre is the geology model's alone.
With --no-geology the geology parameters are dropped and the 0 and 1 km knots are freed (the depth-factor
parameterisation of the first S13 run, configs/velocity_calibration_v1.yaml).

Forward model: S4 (assign) and S5 (fusion.build) run in memory for every trial model; travel times on the
S6 grid with slow air above the DEM plus ``--skin`` rock cells; every event is relocated below the ground in
every model.
Derivatives: finite differences through that forward model for the geology parameters; ray integrals for the
regional bias (checked against one finite difference). Hypocentres and origin times are removed per event by
parameter separation (rainier3d.validate.locate).
Regularisation: Gaussian priors on the geology parameters (SIGMA_GEO); second-difference smoothing (chosen on
the held-out half) and weak damping on the regional bias.
Validation: events alternate between a fitting and a held-out half in origin-time order; held-out events are
relocated in every iterate. The fit then continues on all events.

Usage: pixi run s13            (then pixi run s4, s5, s6 and s14)
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import time

import numpy as np
import xarray as xr
import yaml
from scipy.linalg import block_diag

from rainier3d.config.domain import REPO, load_domain
from rainier3d.fusion import build, regional
from rainier3d.io.store import read_tree
from rainier3d.petro.table import perturbations, petro_table, rock_unit_ids, unit_names
from rainier3d.properties.assign import assign
from rainier3d.validate import calibrate as C
from rainier3d.validate import locate as L
from rainier3d.validate import pnsn

OUT_YAML = REPO / "configs" / "velocity_calibration.yaml"
KNOTS = C.KNOTS_M  # 0, 1, 2, 4, 7, 11, 16, 25 km
GEO = ("ln_v0", "ln_pstar", "ln_vs")
SIGMA_GEO = np.array([0.3, 0.7, 0.1])  # prior sd: V0 x/÷1.35, P* x/÷2, Vs (Vp/Vs) +-10%
FD_H = 0.05
LAMS = [0.01, 0.1, 1.0, 10.0]


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--iterations", type=int, default=3, help="Gauss-Newton steps on the fitting half")
    ap.add_argument("--iterations-all", type=int, default=2, help="further steps on all events")
    ap.add_argument("--no-geology", action="store_true")
    ap.add_argument("--skin", type=int, default=1)
    ap.add_argument("--lam-d", type=float, default=0.01)
    a = ap.parse_args()
    t_start = time.time()
    dom = load_domain()
    vc, fc = dom.cfg["validation"], dom.cfg["fusion"]
    out_dir = dom.path("outputs") / "joint_calibration"
    out_dir.mkdir(parents=True, exist_ok=True)

    grid, picks, stations, sta_xyd, events = L.setup(dom, REPO / "configs" / "validation_events.csv")
    geo = read_tree(dom.path("processed") / "geomodel.zarr")
    table, pert = petro_table(), perturbations()
    q = pert["q"]
    cvm, cres = regional.load_cvm(dom), regional.load_crescent(dom)
    reg0 = {
        n: regional.regional_on_level(lev, geo[n].to_dataset()["depth"].values, cvm, cres)
        for n, lev in dom.levels.items()
    }
    surf = geo["surface"].to_dataset()
    ground = L.ground_on_grid(geo, grid)
    xs, ys, zs = grid.xs, grid.ys, grid.zs
    depth = C.depth_below_ground(geo, xs, ys, zs)
    taper = C.fusion_taper(depth, fc["geology_only_depth_m"], fc["taper_depth_m"])
    depth_xyd, taper_xyd = L.Grid.xyd(depth), L.Grid.xyd(taper)
    below = (depth > 1000) & (depth < 10000)

    use_geo = not a.no_geology
    free = np.arange(2, KNOTS.size) if use_geo else np.arange(KNOTS.size)  # free regional knots
    ng = len(GEO) if use_geo else 0
    nf = free.size
    npar = ng + 2 * nf

    def split(theta):
        g = dict(zip(GEO, theta[:ng], strict=False)) if use_geo else {}
        full = np.zeros((2, KNOTS.size))
        full[0, free], full[1, free] = theta[ng : ng + nf], theta[ng + nf :]
        return g, full

    def cal_of(theta):
        g, full = split(theta)
        bias = {"knots_m": KNOTS.tolist(), "vp": {"log_factor": full[0]}, "vs": {"log_factor": full[1]}}
        return g, {"regional_bias": bias, "vpvs_floor": 1.6}

    def velocities(theta, phases=("P", "S")):
        """Run S4 + S5 in memory and sample the fused model on the S6 grid, with topography."""
        g, cal = cal_of(theta)
        nodes = {"/surface": surf}
        for n, lev in dom.levels.items():
            gl = geo[n].to_dataset()
            p = assign(gl, table, pert, g)
            reg = build.apply_bias(reg0[n], gl["depth"].values, cal)
            nodes[f"/{n}"], _ = build.fuse_level(gl, p, reg, lev, fc, q, n, full=False)
        tree = xr.DataTree.from_dict(nodes)
        out = {}
        for ph in phases:
            v = pnsn.model_on_grid(tree, "vp" if ph == "P" else "vs", xs, ys, zs, ph)
            out[ph] = L.with_topography(v, grid, ground, a.skin)
        return out

    def T_of(vz):
        return {ph: L.fields(L.Grid.xyd(v), grid, sta_xyd) for ph, v in vz.items()}

    def sample_T(T, pk, cat):
        """Travel time of every pick at the current hypocentres, by pick row (NaN for other phases)."""
        t = np.full(len(pk), np.nan)
        src = cat.loc[pk.event, ["x", "y", "d"]].values.astype(float)
        for i, (ph, s, row) in enumerate(zip(pk.phase, pk.si, pk.row, strict=True)):
            if ph in T:
                t[row] = grid.sample(T[ph][s], src[i][None])[0]
        return t

    order = sorted(events.index)  # ComCat ids sort by origin time
    fit_half = {e for i, e in enumerate(order) if i % 2 == 0}
    held = [e for e in order if e not in fit_half]
    logging.info(
        "%d events (%d fitting, %d held out); %d parameters", len(events), len(fit_half), len(held), npar
    )

    D = C.second_difference(KNOTS.size)
    E = np.eye(KNOTS.size)[:, free]
    DD1 = E.T @ D.T @ D @ E  # smoothing over all knots, with the fixed ones held at 0
    extras = {}

    def regularisation(N, lam):
        sc = np.trace(N[ng:, ng:]) / (2 * nf)
        Lg = np.diag(1 / SIGMA_GEO**2) if use_geo else np.zeros((0, 0))
        Lr = sc * (lam * block_diag(DD1, DD1) + a.lam_d * np.eye(2 * nf))
        return block_diag(Lg, Lr)

    def step(system, evs, theta, lam):
        A = np.vstack([system[e][0] for e in evs if e in system])
        r = np.concatenate([system[e][1] for e in evs if e in system])
        N = A.T @ A
        Lm = regularisation(N, lam)
        return theta + np.linalg.solve(N + Lm, A.T @ r - Lm @ theta), N, Lm

    def jacobian(theta, T, vz, cat, pk, Kgeo=None):
        """(n_picks, npar) dT/dtheta: geology by finite differences (or ``Kgeo``), regional bias by rays."""
        vel = {ph: L.Grid.xyd(v) for ph, v in vz.items()}
        Kd, rel, n_failed = L.kernels_all(T, grid, pk, cat, sta_xyd, vel, taper_xyd, depth_xyd, KNOTS)
        K = np.zeros((len(pk), npar))
        K[:, ng : ng + nf] = Kd[:, : KNOTS.size][:, free]
        K[:, ng + nf :] = Kd[:, KNOTS.size :][:, free]
        if use_geo and Kgeo is not None:
            K[:, :ng] = Kgeo
        elif use_geo:
            t0 = sample_T(T, pk, cat)
            for k in range(ng):
                th = theta.copy()
                th[k] += FD_H
                phases = ("S",) if GEO[k] == "ln_vs" else ("P", "S")
                t1 = sample_T(T_of(velocities(th, phases)), pk, cat)
                K[:, k] = np.nan_to_num((t1 - t0) / FD_H)
                logging.info("geology derivative %s done", GEO[k])
        return K, rel, n_failed

    def fd_check(theta, K, T, pk, cat):
        """Ray derivative of the regional Vs bias at 4 km against a finite difference through S4 + S5."""
        k = ng + nf + int(np.flatnonzero(free == 3)[0])
        th = theta.copy()
        th[k] += FD_H
        t0 = sample_T(T, pk, cat)
        t1 = sample_T(T_of(velocities(th, ("S",))), pk, cat)
        rows = pk.row.values[(pk.phase == "S").values]
        fd, ray = (t1[rows] - t0[rows]) / FD_H, K[rows, k]
        ok = np.abs(fd) > 1e-3
        res = {
            "parameter": "regional Vs bias at 4000 m",
            "n_picks": int(ok.sum()),
            "slope_ray_on_fd": float(np.polyfit(fd[ok], ray[ok], 1)[0]),
            "corr": float(np.corrcoef(fd[ok], ray[ok])[0, 1]),
        }
        logging.info("regional finite-difference check: %s", res)
        return res

    def run(theta, fit, n_iter, lam, tag, reuse_geo=False):
        hist, Kgeo, NL = [], None, None
        for it in range(n_iter + 1):
            t0 = time.time()
            vz = velocities(theta)
            T = T_of(vz)
            cat, pk = L.locate_all(T, grid, picks, events, ground=ground)
            rr = vz["P"][below] / vz["S"][below]
            rec = {
                "run": tag,
                "iteration": it,
                "theta": theta.round(5).tolist(),
                "fit": L.residual_stats(pk[pk.event.isin(fit)]),
                "held_out": L.residual_stats(pk[pk.event.isin(held)]),
                "all": L.residual_stats(pk),
                "vpvs_1_10km": {"median": float(np.median(rr)), "p05": float(np.percentile(rr, 5))},
                "above_ground_gt_50m": int((cat.above_ground_m > 50).sum()),
            }
            hist.append(rec)
            logging.info(
                "%s it %d: RMS P %.4f S %.4f (held-out P %.4f S %.4f) Vp/Vs %.3f geology %s [%.0f s]",
                tag, it, rec["all"]["P"]["rms_s"], rec["all"]["S"]["rms_s"], rec["held_out"]["P"]["rms_s"],
                rec["held_out"]["S"]["rms_s"], rec["vpvs_1_10km"]["median"], np.round(theta[:ng], 4),
                time.time() - t0,
            )  # fmt: skip
            if it == n_iter:
                return theta, lam, hist, cat, pk, NL
            K, rel, n_failed = jacobian(theta, T, vz, cat, pk, Kgeo if reuse_geo else None)
            Kgeo = K[:, :ng].copy()
            rec["ray_vs_field_rel_diff_median"] = float(np.nanmedian(rel))
            rec["rays_closed_straight"] = n_failed
            (out_dir / "history_checkpoint.json").write_text(json.dumps(hist, indent=1))
            system = L.separated_system(pk, cat, T, grid, K, 0)
            if "fd_check_regional" not in extras:
                extras["fd_check_regional"] = fd_check(theta, K, T, pk, cat)
            if lam is None:
                scan = []
                for ls in LAMS:
                    th1, _, _ = step(system, fit, theta, ls)
                    scan.append(
                        {"lam_s": ls, "held_out_linear_nrms": L.linear_score(system, held, th1 - theta)}
                    )
                    logging.info(
                        "lam_s %g: held-out linearised nRMS %.4f", ls, scan[-1]["held_out_linear_nrms"]
                    )
                lam = min(scan, key=lambda s: s["held_out_linear_nrms"])["lam_s"]
                extras["lam_scan"] = scan
            theta, N, Lm = step(system, fit, theta, lam)
            NL = (N, Lm)
        raise AssertionError

    theta0 = np.zeros(npar)
    th_fit, lam, h_fit, _, _, _ = run(theta0, fit_half, a.iterations, None, "fitting-half")
    th_all, _, h_all, cat, pk, (N, Lm) = run(th_fit, set(order), a.iterations_all, lam, "all-events", True)

    # posterior sd (linearised at the last step, scaled by the mean reduced chi-square of the two phases)
    chi2 = float(np.mean([h_all[-1]["all"][p]["rms_s"] ** 2 / L.SIGMA[p] ** 2 for p in ("P", "S")]))
    post = np.sqrt(np.diag(np.linalg.inv(N + Lm)) * chi2)

    cat = cat.join(events[["x", "y", "d"]].add_suffix("_catalog"))
    cat.to_csv(out_dir / "catalog.csv")
    pk.to_csv(out_dir / "picks.csv", index=False)
    (out_dir / "history.json").write_text(json.dumps(h_fit + h_all, indent=1))

    g, full = split(th_all)
    names = unit_names()
    geology = {}
    if use_geo:
        geology = {k: round(float(v), 5) for k, v in g.items()}
        geology |= {k.replace("ln_", "factor_"): round(float(np.exp(v)), 4) for k, v in g.items()}
        geology |= {f"sd_{k}": round(float(s), 4) for k, s in zip(GEO, post[:ng], strict=True)}
        geology |= {"prior_sd": dict(zip(GEO, SIGMA_GEO.tolist(), strict=True))}
        geology |= {"units": [names[i] for i in rock_unit_ids()]}
    rec = {
        "version": 2,
        "description": "S13: geology multipliers (S4, rock units) and a static bias of the regional model"
        " (S5, before fusion), fitted to PNSN P and S arrivals with 3D relocation.",
        "geology": geology,
        "regional_bias": {
            "knots_m": KNOTS.tolist(),
            "vp": {"log_factor": full[0].round(5).tolist(), "factor": np.exp(full[0]).round(4).tolist()},
            "vs": {"log_factor": full[1].round(5).tolist(), "factor": np.exp(full[1]).round(4).tolist()},
            "sd_log_factor": {
                "free_knots_m": KNOTS[free].tolist(),
                "vp": post[ng : ng + nf].round(4).tolist(),
                "vs": post[ng + nf :].round(4).tolist(),
            },
        },
        "vpvs_floor": 1.6,
        "vpvs_floor_source": "christensen_1996",
        "source_keys": [
            "comcat_uw",
            "pavlis_booker_1980",
            "kissling_1994",
            "lomax_2000",
            "thurber_1983",
            "white_2020",
            "huber_1964",
        ],
        "data": {
            "picks": "PNSN analyst P and S picks (ComCat), configs/validation_events.csv",
            "n_events": int(len(events)),
            "n_p": int((picks.phase == "P").sum()),
            "n_s": int((picks.phase == "S").sum()),
            "n_stations": int(picks.si.nunique()),
            "pick_sigma_s": L.SIGMA,
        },
        "method": {
            "forward": "S4 + S5 in memory (properties.assign, fusion.build) on the S6 grid "
            f"(dx {vc['dx']} m); pykonal PointSourceSolver by reciprocity; air above DEM + {a.skin} cell(s) "
            f"at {L.AIR_V} m/s",
            "location": "L1 grid search below the DEM, then Huber Gauss-Newton with a ground penalty",
            "derivatives": f"geology: finite differences (h = {FD_H}) through S4 + S5; regional bias: rays",
            "separation": "Pavlis & Booker (1980), per event",
            "lam_s_rel": lam,
            "lam_d_rel": a.lam_d,
            "iterations_fitting_half": a.iterations,
            "iterations_all": a.iterations_all,
            "geology_derivatives": "recomputed every fitting-half iteration, reused in the all-events run",
            "split": "events alternating in origin-time order",
        },
        "held_out": {"before": h_fit[0]["held_out"], "after": h_fit[-1]["held_out"]},
        "all_events": {"before": h_fit[0]["all"], "after": h_all[-1]["all"]},
        "vpvs_1_10km": {"before": h_fit[0]["vpvs_1_10km"], "after": h_all[-1]["vpvs_1_10km"]},
        "above_ground_gt_50m": h_all[-1]["above_ground_gt_50m"],
        **extras,
        "runtime_min": round((time.time() - t_start) / 60, 1),
        "date": dt.date.today().isoformat(),
    }
    OUT_YAML.write_text(yaml.safe_dump(rec, sort_keys=False))
    logging.info("wrote %s (%.1f min)", OUT_YAML, rec["runtime_min"])


if __name__ == "__main__":
    main()
