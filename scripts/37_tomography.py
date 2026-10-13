"""S37: local-earthquake tomography for ln Vp and ln Vs on the fused model -> data/processed/model_let.zarr.

Data: PNSN analyst P and S picks (ComCat) of the S13 validation events (data/raw/pnsn) and of the catalogue
caches named in ``tomography.pick_caches`` (data/raw/pnsn/<name>), merged, one pick per event, station and
phase; stations inside the domain (the extent of the S6 grid).
Model: V = V_model * exp(m), m on the node grid of ``tomography`` in configs/domain.yaml
(rainier3d.validate.tomo).
Iterations: fields, relocation of every event below the ground, rays, kernels, separated system, one
regularised step fitted on the fitting events; the held-out events (alternate 10 km squares of epicentres by
default, so they sit away from the fitting events) are relocated in every model and score it. The smoothing
weight is chosen on them at the first iteration (linearised score); the damping is fixed. A step is kept only
if the relocated held-out misfit (mean of (residual / sigma)^2 over P and S picks) falls by more than
``stop_rel_tol``; otherwise half the step is tried, and if that fails too the last kept model is final.
Checks: the ray kernel of one node against a finite difference through the eikonal fields; a checkerboard test
with the kernels of the last iteration (recovery as the correlation of the input and recovered patterns where
the derivative weight sum is above ``dws_min_m``).

Writes outputs/tomography/ (history.json, summary.json, nodes.nc, figures) and data/processed/model_let.zarr:
model.zarr with vp, vs (and rho by Nafe-Drake) multiplied by exp(m) on L1-L3, and the node fields under /let.

Usage: pixi run python scripts/37_tomography.py [--iterations 3]
"""

from __future__ import annotations

import argparse
import json
import logging
import time

import numpy as np
import pandas as pd
import xarray as xr
from pyproj import Transformer

from rainier3d.config.domain import REPO, load_domain
from rainier3d.io.store import read_tree, write
from rainier3d.petro.relations import nafe_drake_rho_from_vp
from rainier3d.validate import locate as L
from rainier3d.validate import pnsn
from rainier3d.validate import tomo as TM


def load_picks(dom, caches, min_picks: int = 6, min_p: int = 4):
    """Picks of the S13 validation events and of the catalogue caches ``caches`` (folders of data/raw/pnsn
    written by rainier3d.catalog.fetch) on one station index: (picks, sta_xyd, events with prior x, y, d)."""
    _, p1, st1, _, ev1 = L.setup(dom, REPO / "configs" / "validation_events.csv", min_picks, min_p)
    tf = Transformer.from_crs("EPSG:4326", dom.crs, always_xy=True)
    x0, y0, x1, y1 = dom.bounds
    cols = ["event", "net", "sta", "phase", "tt_obs"]
    picks, stations, events = [p1[cols]], [st1[["net", "sta", "x", "y", "elev"]]], [ev1[["x", "y", "d"]]]
    for name in caches:
        cache = dom.path("raw") / "pnsn" / name
        p2, st2 = pd.read_csv(cache / "picks.csv"), pd.read_csv(cache / "stations.csv")
        st2 = st2[(st2.x > x0) & (st2.x < x1) & (st2.y > y0) & (st2.y < y1)]
        ev2 = p2.drop_duplicates("event")[["event", "lon", "lat", "depth_km"]].dropna().copy()
        ev2["x"], ev2["y"] = tf.transform(ev2.lon.values, ev2.lat.values)
        ev2["d"] = ev2.depth_km * 1e3  # km below sea level, as in S6 and S13
        ev2 = ev2[(ev2.x > x0) & (ev2.x < x1) & (ev2.y > y0) & (ev2.y < y1)].set_index("event")
        p2 = p2[p2.event.isin(ev2.index)].merge(st2[["net", "sta"]], on=["net", "sta"])
        picks.append(p2[cols])
        stations.append(st2[["net", "sta", "x", "y", "elev"]])
        events.append(ev2[["x", "y", "d"]])
    stations = pd.concat(stations).drop_duplicates(["net", "sta"]).reset_index(drop=True)
    sidx = {(n, s): i for i, (n, s) in enumerate(zip(stations.net, stations.sta, strict=True))}
    picks = pd.concat(picks).drop_duplicates(["event", "net", "sta", "phase"])
    picks["si"] = [sidx[(n, s)] for n, s in zip(picks.net, picks.sta, strict=True)]
    n = picks.groupby("event").phase.agg(n="size", n_p=lambda s: (s == "P").sum())
    keep = n[(n.n >= min_picks) & (n.n_p >= min_p)].index
    picks = picks[picks.event.isin(keep)].sort_values(["event", "phase", "si"]).reset_index(drop=True)
    picks["row"] = np.arange(len(picks))
    events = pd.concat(events)
    events = events[~events.index.duplicated()].loc[sorted(keep)]
    sta_xyd = np.column_stack([stations.x, stations.y, -stations.elev])
    return picks, sta_xyd, events


def split_events(events: pd.DataFrame, how: str, block_m: float, n_picks: pd.Series) -> tuple[set, list]:
    """Fitting and held-out events. ``blocks``: epicentres binned in block_m squares, whole squares held out,
    so held-out events sit away from the fitting events; squares go, largest first, to the half with fewer
    picks (``n_picks`` per event), which balances the halves. ``alternate``: every other event in id
    (origin-time) order."""
    order = sorted(events.index)
    if how == "alternate":
        fit = {e for i, e in enumerate(order) if i % 2 == 0}
    else:
        key = list(zip(*(np.floor(events[c] / block_m).astype(int) for c in ("x", "y")), strict=True))
        blocks = pd.Series(n_picks.reindex(events.index).values, index=pd.Index(key, tupleize_cols=False))
        size = blocks.groupby(level=0).sum().sort_values(ascending=False)
        total, fit_blocks = [0, 0], set()
        for b, n in size.items():
            k = int(total[1] < total[0])  # 0: fitting, 1: held out
            total[k] += n
            if k == 0:
                fit_blocks.add(b)
        fit = {e for e, b in zip(events.index, key, strict=True) if b in fit_blocks}
    return fit, [e for e in order if e not in fit]


def misfit(stats: dict) -> float:
    """Held-out misfit: mean over picks of (residual / pick sigma)^2, both phases (from residual_stats)."""
    num = sum(stats[p]["n"] * (stats[p]["rms_s"] / L.SIGMA[p]) ** 2 for p in stats)
    return float(num / max(sum(stats[p]["n"] for p in stats), 1))


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--iterations", type=int, default=None)
    ap.add_argument("--model", default=None, help="starting model (default data/processed/model.zarr)")
    a = ap.parse_args()
    t_start = time.time()
    dom = load_domain()
    tc, vc = dom.cfg["tomography"], dom.cfg["validation"]
    n_iter = a.iterations or tc["iterations"]
    out_dir = dom.path("outputs") / "tomography"
    out_dir.mkdir(parents=True, exist_ok=True)
    model_path = a.model or dom.path("processed") / "model.zarr"
    tree = read_tree(model_path)

    xs, ys, zs = pnsn.grid_axes(dom, vc["dx"], vc["z_top"], vc["z_bot"])
    grid = L.Grid(xs, ys, zs, vc["dx"])
    ground = L.ground_on_grid(tree, grid)
    v0 = {ph: L.Grid.xyd(pnsn.model_on_grid(tree, v, xs, ys, zs, ph)) for ph, v in (("P", "vp"), ("S", "vs"))}
    is_air = L.Grid.xyd(
        np.broadcast_to(zs[:, None, None] > ground[None] + tc["skin"] * grid.dx, (zs.size,) + ground.shape)
    )

    picks, sta_xyd, events = load_picks(dom, tc["pick_caches"])
    x0, y0, x1, y1 = dom.bounds
    nodes = TM.Nodes(
        np.arange(x0, x1 + 1, tc["node_dx_m"]), np.arange(y0, y1 + 1, tc["node_dx_m"]), tc["node_depths_m"]
    )
    L2 = TM.Nodes.second_differences(nodes)
    import scipy.sparse as sp

    Lreg = sp.block_diag([L2, L2], format="csr")
    fit, held = split_events(events, tc["held_out"], tc["held_out_block_m"], picks.groupby("event").size())
    logging.info(
        "%d events (%d fitting, %d held out by %s), %d P and %d S picks, %d stations; %d x 2 nodes",
        len(events), len(fit), len(held), tc["held_out"], (picks.phase == "P").sum(),
        (picks.phase == "S").sum(), picks.si.nunique(), nodes.n,
    )  # fmt: skip

    def velocities(m):
        out = {}
        for j, ph in enumerate(("P", "S")):
            v = v0[ph] * np.exp(nodes.on_grid(m[j * nodes.n : (j + 1) * nodes.n], grid))
            out[ph] = np.where(is_air, L.AIR_V, v)
        return out

    def forward(m, label):
        """Fields, relocation and residual statistics of model m."""
        t0 = time.time()
        vel = velocities(m)
        T = {ph: L.fields(v, grid, sta_xyd) for ph, v in vel.items()}
        cat, pk = L.locate_all(T, grid, picks, events, ground=ground)
        rec = {
            "model": label,
            "fit": L.residual_stats(pk[pk.event.isin(fit)]),
            "held_out": L.residual_stats(pk[pk.event.isin(held)]),
            "m_rms": {ph: float(np.sqrt(np.mean(m[j * nodes.n : (j + 1) * nodes.n] ** 2))) for j, ph in
                      enumerate(("P", "S"))},
            "above_ground_gt_50m": int((cat.above_ground_m > 50).sum()),
        }  # fmt: skip
        rec["held_out_misfit"] = misfit(rec["held_out"])
        logging.info(
            "%s: fit RMS P %.4f S %.4f, held-out P %.4f S %.4f (misfit %.4f), rms(m) P %.4f S %.4f [%.0f s]",
            label, rec["fit"]["P"]["rms_s"], rec["fit"]["S"]["rms_s"], rec["held_out"]["P"]["rms_s"],
            rec["held_out"]["S"]["rms_s"], rec["held_out_misfit"], rec["m_rms"]["P"], rec["m_rms"]["S"],
            time.time() - t0,
        )  # fmt: skip
        return rec, (vel, T, cat, pk.sort_values("row"))

    def system(state, m):
        vel, T, cat, pk = state
        K, dws, n_failed = TM.kernels(T, grid, pk, cat, sta_xyd, vel, nodes)
        A, r, ev_rows = TM.separated(pk, cat, T, grid, K)
        return K, dws, n_failed, A, r, np.isin(ev_rows, list(fit))

    # Gauss-Newton with a stopping rule: a step is kept when the relocated held-out misfit falls by more than
    # ``stop_rel_tol``; otherwise half the step is tried, and if that fails too the last kept model is final
    m = np.zeros(2 * nodes.n)
    rec, state = forward(m, "start")
    hist, extras, lam_s, stop = [rec | {"accepted": True}], {}, None, "iterations"
    for it in range(1, n_iter + 1):
        K, dws, n_failed, A, r, in_fit = system(state, m)
        hist[-1]["rays_closed_straight"] = n_failed
        if "fd_check" not in extras:
            extras["fd_check"] = fd_check(
                K, dws, state[1], grid, state[3], state[2], sta_xyd, nodes, m, velocities
            )
        Af, rf = A[in_fit], r[in_fit]
        if lam_s is None:
            scan = []
            for ls in tc["lam_s"]:
                dm = TM.regularised_step(Af, rf, m, Lreg, ls, tc["lam_d"])
                scan.append({"lam_s": ls, "held_out_linear_nrms": TM.score(A, r, ~in_fit, dm)})
                logging.info("lam_s %g: held-out linearised nRMS %.4f", ls, scan[-1]["held_out_linear_nrms"])
            extras["lam_scan"] = scan
            extras["held_out_linear_nrms_no_change"] = TM.score(A, r, ~in_fit, np.zeros_like(m))
            lam_s = min(scan, key=lambda s: s["held_out_linear_nrms"])["lam_s"]
        dm = TM.regularised_step(Af, rf, m, Lreg, lam_s, tc["lam_d"])
        best = hist[-1]["held_out_misfit"]
        for frac in (1.0, 0.5):
            rec, st = forward(m + frac * dm, f"it {it} step x{frac:g}")
            ok = rec["held_out_misfit"] < best * (1 - tc["stop_rel_tol"])
            hist.append(rec | {"accepted": ok, "step": frac})
            (out_dir / "history.json").write_text(json.dumps(hist, indent=1))
            if ok:
                m, state = m + frac * dm, st
                break
        else:
            tol = tc["stop_rel_tol"]
            stop = f"iteration {it}: held-out misfit did not fall by {tol:.1%} (full or half step)"
            logging.info("stop: %s", stop)
            break
    kept = [h for h in hist if h["accepted"]]
    extras["stop"] = stop

    # checkerboard with the kernels of the final model
    _, dws, _, A, r, in_fit = system(state, m)
    cb = {}
    rng = np.random.default_rng(0)
    for cell in tc["checkerboard_cells_m"]:
        m_true = TM.checkerboard(nodes, cell, tc["checkerboard_amp"])
        Af = A[in_fit]
        r_syn = Af @ m_true + rng.normal(0, 1, Af.shape[0])  # rows are in units of the pick sigma
        m_rec = TM.regularised_step(Af, r_syn, np.zeros_like(m), Lreg, lam_s, tc["lam_d"])
        cb[str(int(cell))] = recovery(m_true, m_rec, dws, nodes, tc["dws_min_m"])
        logging.info("checkerboard %d m: %s", cell, cb[str(int(cell))])

    summary = {
        "data": {"n_events": len(events), "n_fit": len(fit), "n_held_out": len(held),
                 "n_p": int((picks.phase == "P").sum()), "n_s": int((picks.phase == "S").sum()),
                 "n_stations": int(picks.si.nunique())},
        "nodes": {"dx_m": tc["node_dx_m"], "depths_m": list(tc["node_depths_m"]), "n_per_phase": nodes.n},
        "lam_s": lam_s, "lam_d": tc["lam_d"],
        "held_out_split": {"how": tc["held_out"], "block_m": tc["held_out_block_m"]},
        "held_out": {"before": kept[0]["held_out"], "after": kept[-1]["held_out"]},
        "held_out_misfit": {"before": kept[0]["held_out_misfit"], "after": kept[-1]["held_out_misfit"]},
        "fit": {"before": kept[0]["fit"], "after": kept[-1]["fit"]},
        "steps_kept": len(kept) - 1,
        "checkerboard": cb, **extras,
        "runtime_min": round((time.time() - t_start) / 60, 1),
        "starting_model": str(model_path),
    }  # fmt: skip
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=1, default=float))

    node_ds = xr.Dataset(
        {
            "dlnvp": (("x", "y", "d"), m[: nodes.n].reshape(nodes.shape)),
            "dlnvs": (("x", "y", "d"), m[nodes.n :].reshape(nodes.shape)),
            "dws_p": (("x", "y", "d"), dws[: nodes.n].reshape(nodes.shape)),
            "dws_s": (("x", "y", "d"), dws[nodes.n :].reshape(nodes.shape)),
        },
        coords={"x": nodes.axes[0], "y": nodes.axes[1], "d": nodes.axes[2]},
        attrs={"long_name": "ln V perturbation of the fused model (S37)", "d": "m below sea level"},
    )
    node_ds.to_netcdf(out_dir / "nodes.nc")
    write_model(tree, node_ds, nodes, m, dom.path("processed") / "model_let.zarr", summary)
    figures(node_ds, cb, nodes, tc, out_dir)
    logging.info("wrote %s and model_let.zarr (%.1f min)", out_dir, summary["runtime_min"])


def fd_check(K, dws, T, grid, pk, cat, sta_xyd, nodes, m, velocities, h: float = 0.05):
    """Ray derivative of the best-sampled S node against a finite difference through the fields."""
    k = nodes.n + int(np.argmax(dws[nodes.n :]))
    rows = np.flatnonzero(np.abs(K[:, k].toarray().ravel()) > 1e-4)
    sub = pk.set_index("row").loc[rows]
    stas = np.unique(sub.si.values)
    m1 = m.copy()
    m1[k] += h
    v1 = velocities(m1)["S"]
    T1 = L.fields(v1, grid, sta_xyd[stas])
    loc = {s: i for i, s in enumerate(stas)}
    src = cat.loc[sub.event, ["x", "y", "d"]].values.astype(float)
    t0 = np.array([grid.sample(T["S"][s], q[None])[0] for s, q in zip(sub.si, src, strict=True)])
    t1 = np.array([grid.sample(T1[loc[s]], q[None])[0] for s, q in zip(sub.si, src, strict=True)])
    fd, ray = (t1 - t0) / h, K[rows, k].toarray().ravel()
    out = {
        "node": int(k - nodes.n),
        "n_picks": int(rows.size),
        "slope_ray_on_fd": float(np.polyfit(fd, ray, 1)[0]),
        "corr": float(np.corrcoef(fd, ray)[0, 1]),
    }
    logging.info("finite-difference check of the S kernel: %s", out)
    return out


def recovery(m_true, m_rec, dws, nodes, dws_min):
    """Correlation and amplitude ratio of the recovered checkerboard, per phase and node depth, where the
    derivative weight sum exceeds dws_min."""
    out = {}
    for j, ph in enumerate(("P", "S")):
        sl = slice(j * nodes.n, (j + 1) * nodes.n)
        t, rcv, w = (a[sl].reshape(nodes.shape) for a in (m_true, m_rec, dws))
        rows = []
        for kd, d in enumerate(nodes.axes[2]):
            ok = w[:, :, kd] > dws_min
            if ok.sum() < 10:
                rows.append({"d_m": float(d), "n": int(ok.sum())})
                continue
            a, b = t[:, :, kd][ok], rcv[:, :, kd][ok]
            c = round(float(np.corrcoef(a, b)[0, 1]), 3)
            rows.append({"d_m": float(d), "n": int(ok.sum()), "corr": c,
                         "amp_ratio": round(float(np.sum(a * b) / np.sum(a * a)), 3)})  # fmt: skip
        out[ph] = rows
    return out


def write_model(tree, node_ds, nodes, m, path, summary):
    """model.zarr with vp, vs times exp(m) on every level (m at the cell centres, d = -z), rho by Nafe-Drake;
    the node fields under /let."""
    out = {}
    for name in tree.children:
        ds = tree[name].to_dataset()
        if name in ("L1", "L2", "L3"):
            zz, yy, xx = np.meshgrid(ds.z.values, ds.y.values, ds.x.values, indexing="ij")
            p = np.column_stack([xx.ravel(), yy.ravel(), -zz.ravel()])
            k, w = nodes.weights(p)
            for j, v in enumerate(("vp", "vs")):
                f = (m[j * nodes.n : (j + 1) * nodes.n][k] * w).sum(1).reshape(zz.shape)
                old = ds[v].values
                ds[v] = (("z", "y", "x"), (old * np.exp(f)).astype(np.float32), ds[v].attrs)
                ds[f"dln{v}_let"] = (
                    ("z", "y", "x"),
                    np.where(np.isfinite(old), f, np.nan).astype(np.float32),
                )
                if v == "vp":
                    ratio = nafe_drake_rho_from_vp(ds["vp"].values / 1e3) / nafe_drake_rho_from_vp(old / 1e3)
                    ds["rho"] = (
                        ("z", "y", "x"),
                        (ds["rho"].values * ratio).astype(np.float32),
                        ds["rho"].attrs,
                    )
        out[f"/{name}"] = ds
    out["/let"] = node_ds
    t = xr.DataTree.from_dict(out)
    t.attrs = {**tree.attrs, "let": "S37 local-earthquake tomography (scripts/37_tomography.py)",
               "let_lam_s": summary["lam_s"], "let_lam_d": summary["lam_d"]}  # fmt: skip
    write(t, path)


def figures(node_ds, cb, nodes, tc, out_dir):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ds_show = [d for d in nodes.axes[2] if d >= 0][:6]
    fig, ax = plt.subplots(3, len(ds_show), figsize=(3.2 * len(ds_show), 9.5), squeeze=False)
    for c, d in enumerate(ds_show):
        sl = node_ds.sel(d=d)
        panels = (
            ("dlnvp", "dln Vp", "RdBu", 0.08),
            ("dlnvs", "dln Vs", "RdBu", 0.08),
            ("dws_s", "DWS S (m)", "viridis", None),
        )
        for r, (v, lab, cm, lim) in enumerate(panels):
            a = sl[v].values.T
            im = ax[r, c].pcolormesh(nodes.axes[0] / 1e3, nodes.axes[1] / 1e3, a, cmap=cm, shading="nearest",
                                     vmin=-lim if lim else None, vmax=lim)  # fmt: skip
            if lim:
                hide = sl["dws_s" if v == "dlnvs" else "dws_p"].values.T < tc["dws_min_m"]
                ax[r, c].contourf(nodes.axes[0] / 1e3, nodes.axes[1] / 1e3, hide, levels=[0.5, 1.5],
                                  colors="w", alpha=0.6)  # fmt: skip
            ax[r, c].set_title(f"{lab}, {d / 1e3:.0f} km bsl", fontsize=9)
            ax[r, c].set_aspect("equal")
            plt.colorbar(im, ax=ax[r, c], shrink=0.7)
    plt.tight_layout()
    plt.savefig(out_dir / "fig_let_slices.png", dpi=90)
    plt.close(fig)


if __name__ == "__main__":
    main()
