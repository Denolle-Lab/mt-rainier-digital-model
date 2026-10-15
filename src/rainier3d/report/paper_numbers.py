"""Numbers of the paper computed from the pipeline outputs -> outputs/paper/numbers.json (S10).

Every model-derived number of docs/paper/rainier3d_paper.md and its supplement is computed here from a
pipeline product, with what it measures and where it comes from, so a rebuild updates them in one place. Each
group reads only finished outputs and is skipped (with a note) when they are missing:

- calibration: configs/velocity_calibration.yaml and outputs/joint_calibration/history.json (S13);
- validation: outputs/pnsn_*.csv (S6); relocation: outputs/relocation/<model>/stats.json (S14);
- imush: outputs/model_comparison/ulberg2020_by_depth.csv (S21);
- model: data/processed/model.zarr, properties_geology.zarr and geomodel.zarr (S3-S5), with fusion_report.csv;
- catalog: outputs/catalog/summary.json and catalog_relocated.csv (S26);
- tomography: outputs/tomography/summary.json, history.json and picks_*.csv (S37);
- applications: data/processed/edifice_load.zarr (S18), outputs/gnss/strain_3d_summary.json (S18 volume),
  outputs/cz/*.json (S33-S35).
"""

from __future__ import annotations

import json
import logging
import math

import numpy as np
import pandas as pd
import yaml

from rainier3d.config.domain import REPO, load_domain

OUT = REPO / "outputs" / "paper" / "numbers.json"
NUM: dict = {}


def put(key, value, what, source):
    """Record one number (or a small list or dict of numbers), rounded for reading but not for the paper."""
    NUM[key] = {"value": _clean(value), "what": what, "source": source}


def _clean(v):
    if isinstance(v, dict):
        return {k: _clean(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_clean(x) for x in v]
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (float, np.floating)):
        return None if not math.isfinite(float(v)) else float(f"{float(v):.6g}")
    return v


# ----------------------------------------------------------------------------------------------------- S13
def calibration():
    cal = yaml.safe_load((REPO / "configs/velocity_calibration.yaml").read_text())
    hist = json.loads((REPO / "outputs/joint_calibration/history.json").read_text())
    src = "configs/velocity_calibration.yaml (S13)"
    g = cal["geology"]
    for k in ("v0", "pstar", "vs"):
        put(f"cal.factor_{k}", g[f"factor_{k}"], f"geology multiplier on {k}", src)
        put(f"cal.ln_{k}", g[f"ln_{k}"], f"geology log-multiplier on {k}", src)
        put(
            f"cal.sd_ln_{k}",
            g[f"sd_ln_{k}"],
            f"posterior s.d. of ln {k}, scaled by the reduced chi-square",
            src,
        )
    d = cal["data"]
    put("cal.data", {k: d[k] for k in ("n_events", "n_p", "n_s", "n_stations")}, "calibration picks", src)
    rb = cal["regional_bias"]
    knots = [k / 1000 for k in rb["knots_m"]]
    for ph in ("vp", "vs"):
        put(
            f"cal.regional_{ph}",
            dict(zip([f"{k:g}" for k in knots[2:]], rb[ph]["factor"][2:], strict=True)),
            f"factor on regional {ph} at the free knots (km below ground)",
            src,
        )
    sd = np.r_[rb["sd_log_factor"]["vp"], rb["sd_log_factor"]["vs"]]
    put(
        "cal.regional_sd_range",
        [sd.min(), sd.max()],
        "range of the formal s.d. of the regional log-factors",
        src,
    )
    put(
        "cal.lam_scan",
        {f"{e['lam_s']:g}": e["held_out_linear_nrms"] for e in cal["lam_scan"]},
        "held-out linearised nRMS by smoothing weight",
        src,
    )
    put("cal.lam_s", cal["method"]["lam_s_rel"], "adopted smoothing weight", src)
    put(
        "cal.fd_check",
        {
            "corr": cal["fd_check_regional"]["corr"],
            "slope": cal["fd_check_regional"]["slope_ray_on_fd"],
            "n_picks": cal["fd_check_regional"]["n_picks"],
        },
        "ray against finite-difference derivative, regional Vs knot at 4 km",
        src,
    )
    put(
        "cal.iterations",
        {
            "fitting_half": cal["method"]["iterations_fitting_half"],
            "all_events": cal["method"]["iterations_all"],
        },
        "Gauss-Newton iterations",
        src,
    )
    put("cal.runtime_min", cal["runtime_min"], "S13 run time", src)
    sig = {"P": 0.14, "S": 0.23}
    chi = {p: hist[-1]["all"][p]["rms_s"] ** 2 / sig[p] ** 2 for p in ("P", "S")}
    put(
        "cal.chi2",
        {"P": chi["P"], "S": chi["S"], "mean": np.mean(list(chi.values()))},
        "reduced chi-square of the final all-events iterate",
        "outputs/joint_calibration/history.json",
    )
    rows = []
    for e in hist:
        rows.append(
            {
                "run": e["run"],
                "it": e["iteration"],
                "P_fit": e["fit"]["P"]["rms_s"],
                "P_held": e["held_out"]["P"]["rms_s"],
                "S_fit": e["fit"]["S"]["rms_s"],
                "S_held": e["held_out"]["S"]["rms_s"],
                "ln_v0": e["theta"][0],
                "ln_pstar": e["theta"][1],
                "ln_vs": e["theta"][2],
                "vpvs_1_10km": e["vpvs_1_10km"]["median"],
            }
        )
    put(
        "cal.history",
        rows,
        "RMS after relocation and geology parameters per iterate",
        "outputs/joint_calibration/history.json",
    )
    lp = [r["ln_pstar"] for r in rows[1:]]
    put(
        "cal.ln_pstar_range",
        [min(lp), max(lp)],
        "range of ln P* over the iterates after the first",
        "history.json",
    )
    put(
        "cal.held_out",
        {
            "before": {p: cal["held_out"]["before"][p]["rms_s"] for p in "PS"},
            "after_fitting_half": {p: cal["held_out"]["after"][p]["rms_s"] for p in "PS"},
            "final": {p: hist[-1]["held_out"][p]["rms_s"] for p in "PS"},
            "n_final": {p: hist[-1]["held_out"][p]["n"] for p in "PS"},
        },
        "held-out RMS (s)",
        src,
    )
    fit_end = [e for e in hist if e["run"] == "fitting-half"][-1]
    put(
        "cal.fit_end",
        {p: fit_end["fit"][p]["rms_s"] for p in "PS"},
        "fitting-half RMS at its last iterate",
        src,
    )
    put("cal.all_final", {p: hist[-1]["all"][p]["rms_s"] for p in "PS"}, "all-events RMS, final", src)
    put("cal.above_ground_gt_50m", cal["above_ground_gt_50m"], "events > 50 m above ground, final", src)
    c = pd.read_csv(REPO / "outputs/joint_calibration/catalog.csv")
    bg = -c.above_ground_m  # depth below the ground
    put(
        "cal.deep_events",
        {
            "bsl_gt_11km": int((c.d > 11000).sum()),
            "bsl_gt_16km": int((c.d > 16000).sum()),
            "bg_gt_11km": int((bg > 11000).sum()),
            "bg_gt_16km": int((bg > 16000).sum()),
        },
        "relocated calibration events deeper than 11 and 16 km, below sea level and below the ground",
        "outputs/joint_calibration/catalog.csv (S13)",
    )
    # calibrated zero-pressure Vp of three units, with the cap 0.98 Vinf of eq:crack
    pt = pd.read_csv(REPO / "configs/petrophysics.csv").set_index("unit")
    v0 = {}
    for u in ("rainier_andesite", "ohanapecosh", "miocene_intrusive"):
        raw = pt.loc[u, "vp0_kms"] * g["factor_v0"]
        v0[u] = {
            "scaled": raw,
            "cap": 0.98 * pt.loc[u, "vpinf_kms"],
            "used": min(raw, 0.98 * pt.loc[u, "vpinf_kms"]),
        }
    put(
        "cal.v0_units_kms",
        v0,
        "calibrated zero-pressure Vp (km/s): table V0 x factor, capped at 0.98 Vinf",
        "configs/petrophysics.csv, configs/velocity_calibration.yaml",
    )
    f = np.log(np.r_[rb["vp"]["factor"]]), np.log(np.r_[rb["vs"]["factor"]])
    put("cal.regional_max_abs_ln_vp", np.abs(f[0]).max(), "largest |ln factor| on regional Vp", src)


# ------------------------------------------------------------------------------------------------------ S6
def validation():
    res = pd.read_csv(REPO / "outputs/pnsn_residuals.csv")
    sta = pd.read_csv(REPO / "outputs/pnsn_stations.csv")
    res["d"] = res.tt_3d - res.tt_1d
    out = {}
    for ph in ("P", "S"):
        s = sta[(sta.phase == ph) & (sta.n >= 5)]
        r = res[res.phase == ph]
        out[ph] = {
            "station_mean_delay_s": s.delay_3d_1d.mean(),
            "n_stations": len(s),
            "per_pick_delay_s": r.d.mean(),
            "corr_res1d_delay": np.corrcoef(s.res_1d, s.delay_3d_1d)[0, 1],
        }
    put(
        "s6.delays",
        out,
        "3D minus 1D predicted delay at ComCat hypocentres; stations with >= 5 picks",
        "outputs/pnsn_residuals.csv, outputs/pnsn_stations.csv (S6)",
    )
    rep = pd.read_csv(REPO / "outputs/pnsn_report.txt", sep=r"\s+", nrows=2)
    put(
        "s6.report", rep.set_index("phase").to_dict("index"), "S6 residual summary", "outputs/pnsn_report.txt"
    )


# ----------------------------------------------------------------------------------------------------- S14
def relocation():
    out = {}
    for d in sorted((REPO / "outputs/relocation").iterdir()):
        f = d / "stats.json"
        if f.exists():
            s = json.loads(f.read_text())
            out[d.name] = {"date": pd.Timestamp(f.stat().st_mtime, unit="s").date().isoformat(), **s}
    # held-out half of S13 (sorted ComCat ids, every second one) scored in each S14 relocation
    from rainier3d.validate import locate as L

    ids = sorted(pd.read_csv(REPO / "outputs/joint_calibration/catalog.csv").event)
    held = [e for i, e in enumerate(ids) if i % 2 == 1]
    ho = {}
    for name in ("pnsn1d", "fused_joint"):
        f = REPO / "outputs/relocation" / name / "picks.csv"
        if f.exists():
            pk = pd.read_csv(f)
            st = L.residual_stats(pk[pk.event.isin(held)])
            ho[name] = {ph: {"rms_s": st[ph]["rms_s"], "n": st[ph]["n"]} for ph in ("P", "S")}
    put(
        "s14.held_out",
        ho,
        "RMS on the 44 held-out S13 events after S14 relocation in each model",
        "outputs/relocation/<model>/picks.csv, split of outputs/joint_calibration/catalog.csv",
    )
    put(
        "s14.models",
        out,
        "relocation of the 88 calibration events in each model (with file date)",
        "outputs/relocation/<model>/stats.json (S14)",
    )


# ----------------------------------------------------------------------------------------------------- S21
def imush():
    c = pd.read_csv(REPO / "outputs/model_comparison/ulberg2020_by_depth.csv")
    put(
        "s21.by_depth",
        c.to_dict("records"),
        "iMUSH against the models by depth below ground and region",
        "outputs/model_comparison/ulberg2020_by_depth.csv (S21)",
    )


# ----------------------------------------------------------------------------------------------------- model
def _levels(store):
    from rainier3d.io.store import read_tree

    dom = load_domain()
    t = read_tree(dom.path("processed") / store)
    return {lv: t[lv].to_dataset() for lv in ("L1", "L2", "L3") if lv in t}, t


def model():
    from rainier3d.geomodel.rules import AIR, ICE, MAGMA, MIDDLE
    from rainier3d.petro.table import unit_names

    m, mt = _levels("model.zarr")
    g, gt = _levels("geomodel.zarr")
    pg, pgt = _levels("properties_geology.zarr")
    names = unit_names()
    by = {v: k for k, v in names.items()}
    kinds = yaml.safe_load((REPO / "configs/units.yaml").read_text())["units"]
    uncons = [int(k) for k, v in kinds.items() if v.get("kind") == "unconsolidated"]
    src = "data/processed/model.zarr"

    fr = pd.read_csv(REPO / "outputs/fusion_report.csv")
    put(
        "fusion.report",
        fr.to_dict("records"),
        "low-pass departure and mean ln(fused/regional) by level",
        "outputs/fusion_report.csv (S5)",
    )
    put(
        "fusion.invariant_max",
        fr.lowpass_rms_lnV.max(),
        "largest low-pass departure (tolerance 0.03)",
        "outputs/fusion_report.csv",
    )

    # cells below Vp/Vs = sqrt(8/3) (negative Poisson ratio), all levels, non-air non-ice
    n_low = n_all = 0
    for ds in m.values():
        u = ds.unit.values
        ok = (u != AIR) & (u != ICE)
        r = ds.vp.values / ds.vs.values
        n_low += int((ok & (r < math.sqrt(8 / 3))).sum())
        n_all += int(ok.sum())
    put(
        "model.vpvs_below_sqrt83",
        {"n": n_low, "of": n_all},
        "fused non-air non-ice cells with Vp/Vs < sqrt(8/3)",
        src,
    )

    # depth-binned mean ln(geology/regional) over L1-L3 without ice, and in the top 300 m
    bins = [(0, 300), (300, 1000), (1000, 2000), (2000, 4000)]
    agree = {}
    for ph in ("vp", "vs"):
        acc = {b: [] for b in bins}
        for ds in m.values():
            u, d = ds.unit.values, ds.depth.values
            ok = (u != AIR) & (u != ICE)
            lr = np.log(ds[f"{ph}_geology"].values / ds[f"{ph}_regional"].values)
            for b in bins:
                k = ok & (d >= b[0]) & (d < b[1]) & np.isfinite(lr)
                acc[b].append(lr[k])
        agree[ph] = {f"{a}-{b}": float(np.mean(np.concatenate(acc[(a, b)]))) for a, b in bins}
    put(
        "model.ln_geology_over_regional",
        agree,
        "mean ln(V_geology/V_regional, corrected) by depth below ground (m), L1-L3 without air and ice",
        src,
    )

    # magma body: cells, weight-1 cells, Vs contrast with the middle crust at the same elevations
    mag = {}
    for lv, ds in g.items():
        u, w = ds.unit.values, ds.magma_weight.values
        mag[lv] = {
            "cells": int((u == MAGMA).sum()),
            "weight_1": int((w >= 0.999).sum()),
            "weight_gt_0": int((w > 0).sum()),
        }
    for lv in ("L2", "L3"):
        ds = m[lv]
        u = ds.unit.values
        con = {}
        for var in ("vs_geology", "vs"):
            v = ds[var].values
            num = []
            for iz in range(u.shape[0]):
                mk, mc = u[iz] == MAGMA, u[iz] == MIDDLE
                if mk.any() and mc.any():
                    num.append(np.log(v[iz][mk] / np.median(v[iz][mc])))
            con[var] = float(np.mean(np.concatenate(num))) if num else None
        mag[lv]["mean_ln_vs_over_middle_crust"] = con
        core = []
        for iz in range(u.shape[0]):
            k1, mc = (ds.magma_weight.values[iz] >= 0.999) & (u[iz] == MAGMA), u[iz] == MIDDLE
            if k1.any() and mc.any():
                core.append(np.log(ds.vs.values[iz][k1] / np.median(ds.vs.values[iz][mc])))
        mag[lv]["core_mean_ln_vs_over_middle_crust"] = float(np.mean(np.concatenate(core))) if core else None
        cz = ds.magma_weight.values >= 0.999
        mag[lv]["centre_vs_median"] = float(np.median(ds.vs.values[cz])) if cz.any() else None
    put(
        "magma",
        mag,
        "magma body: cells of unit magma_mush, cells at weight 1 and > 0, and mean ln(Vs/median Vs of "
        "middle crust at the same z) in the geology and the fused model",
        "geomodel.zarr, model.zarr",
    )

    # plutons: rock-law Vp below the critical zone and at 2 km (geology, L1), and L3 extent
    pid = by["miocene_intrusive"]
    u1, d1 = g["L1"].unit.values, g["L1"].depth.values
    vp1 = pg["L1"].vp.values
    plut = {}
    for a, b in ((200, 300), (1950, 2050)):
        k = (u1 == pid) & (d1 >= a) & (d1 < b)
        plut[f"{a}-{b}"] = {"median_vp_kms": float(np.median(vp1[k])) / 1e3, "n": int(k.sum())}
    u3 = g["L3"].unit.values
    plan = (u3 == pid).any(axis=0)
    dx3 = float(abs(g["L3"].x.values[1] - g["L3"].x.values[0]))
    plut["L3_cells"] = int((u3 == pid).sum())
    plut["L3_plan_km2"] = float(plan.sum() * dx3 * dx3 / 1e6)
    put(
        "model.pluton",
        plut,
        "Miocene plutons: median geology Vp (L1, by depth below ground, m) and L3 extent",
        "properties_geology.zarr, geomodel.zarr",
    )

    # edifice base and footprint
    s = gt["surface"].to_dataset()
    fp = s.footprint.values.astype(bool)
    dxs = float(abs(s.x.values[1] - s.x.values[0]))
    eb = s.edifice_base.values[fp]
    put(
        "model.edifice",
        {
            "base_min_m": np.nanmin(eb),
            "base_max_m": np.nanmax(eb),
            "footprint_km2": fp.sum() * dxs * dxs / 1e6,
        },
        "edifice base range and footprint",
        "geomodel.zarr /surface",
    )

    # Puget Group (eocene_sedimentary) easting on the summit row of L1
    sx, sy = load_domain().summit_xy
    ds = g["L1"]
    iy = int(np.argmin(np.abs(ds.y.values - sy)))
    cols = np.where((ds.unit.values[:, iy, :] == by["eocene_sedimentary"]).any(axis=0))[0]
    if cols.size:
        xs = ds.x.values[cols] / 1e3
        put(
            "model.puget_summit_row_km",
            [xs.min(), xs.max()],
            "easting range (km, cell centres) of eocene_sedimentary on the L1 summit row",
            "geomodel.zarr",
        )

    # CRESCENT/regional Vs uncertainty medians by level
    put(
        "model.vs_unc_regional_median",
        {lv: float(np.nanmedian(ds.vs_unc_regional.values / ds.vs_regional.values)) for lv, ds in m.items()},
        "median relative Vs uncertainty of the regional model (vs_unc_regional / vs_regional)",
        src,
    )

    # L1 against regional: mean ln over non-air L1 cells, and top 300 m
    ds = m["L1"]
    u, d = ds.unit.values, ds.depth.values
    ok = u != AIR
    top = ok & (d < 300)
    put(
        "model.L1_ln_fused_over_regional",
        {
            ph: {
                "all": float(np.nanmean(np.log(ds[ph].values / ds[f"{ph}_regional"].values)[ok])),
                "top_300m_geology": float(
                    np.nanmean(np.log(ds[f"{ph}_geology"].values / ds[f"{ph}_regional"].values)[top])
                ),
            }
            for ph in ("vp", "vs")
        },
        "mean ln ratio over non-air L1 cells",
        src,
    )

    # critical zone
    czd = mt["cz"].to_dataset()
    d = ds.depth.values
    rock = (u != AIR) & (u != ICE)
    ice = czd.ice_thickness.values
    db = d - ice[None]
    k = np.argmax(rock & (db >= 175), axis=0)
    v_l1 = np.take_along_axis(ds.vs.values, k[None], 0)[0]
    v_cz = czd.vs.values[-1]
    okc = np.isfinite(v_l1) & np.isfinite(v_cz) & rock.any(0)
    dev = np.abs(v_cz[okc] / v_l1[okc] - 1)
    cz = {"base_continuity": {"median": np.median(dev), "p90": np.percentile(dev, 90), "n": int(okc.sum())}}
    from rainier3d.petro.table import perturbations, petro_table
    from rainier3d.properties.assign import assign

    cal = yaml.safe_load((REPO / "configs/velocity_calibration.yaml").read_text())
    p0 = assign(g["L1"], petro_table(), perturbations(), cal.get("geology"), None)
    t50 = rock & (d >= 0) & (d < 50)
    r = (pg["L1"].vs.values / p0.vs.values)[t50]
    cz["top50_vs_ratio"] = {
        "median": np.nanmedian(r),
        "p10": np.nanpercentile(r, 10),
        "p90": np.nanpercentile(r, 90),
    }
    # top non-air cell of each column: Vp/Vs > 3, by consolidated or unconsolidated unit
    top = np.argmax(rock, axis=0)
    has = rock.any(0)
    ut = np.take_along_axis(u, top[None], 0)[0][has]
    rt = (
        np.take_along_axis(ds.vp.values, top[None], 0)[0] / np.take_along_axis(ds.vs.values, top[None], 0)[0]
    )[has]
    un = np.isin(ut, uncons)
    for lab, msk in (("unconsolidated", un), ("consolidated", ~un)):
        hi = msk & (rt > 3)
        cz[f"top_cell_vpvs_gt3_{lab}"] = {
            "n": int(hi.sum()),
            "of_top_cells": int(msk.sum()),
            "max": float(rt[msk].max()) if msk.any() else None,
        }
    cz["consolidated_L1_cells"] = int((rock & ~np.isin(u, uncons)).sum())
    cz["L1_vpvs_max"] = float(np.nanmax((ds.vp.values / ds.vs.values)[rock]))
    put(
        "cz",
        cz,
        "critical zone: Vs continuity at the 150 m base against the first L1 cell 175 m below the bed; Vs "
        "with/without the CZ in the top 50 m of L1; top-cell Vp/Vs > 3",
        "model.zarr, properties_geology.zarr",
    )
    uncalibrated(g, m, bins)
    invariant_without_magma(g)


def invariant_without_magma(g):
    """The fusion invariant of L2 and L3 with the magma anomaly left out (it is applied after the fusion)."""
    from rainier3d.fusion import build, regional
    from rainier3d.io.store import read_tree
    from rainier3d.petro.table import perturbations

    dom = load_domain()
    cal = yaml.safe_load((REPO / "configs/velocity_calibration.yaml").read_text())
    props = read_tree(dom.path("processed") / "properties_geology.zarr")
    cvm, cres = regional.load_cvm(dom), regional.load_crescent(dom)
    pert, out = perturbations(), {}
    for name in ("L2", "L3"):
        lev = dom.levels[name]
        reg = build.regional_level(lev, g[name]["depth"].values, cvm, cres, cal)
        _, rows = build.fuse_level(
            g[name], props[name].to_dataset(), reg, lev, dom.cfg["fusion"], pert["q"], name
        )
        out[name] = {r["var"]: r["lowpass_rms_lnV"] for r in rows}
    put(
        "fusion.invariant_without_magma",
        out,
        "fusion low-pass departure with the magma anomaly left out",
        "in memory: S5 code without the magma_mush factors",
    )


def uncalibrated(g, m, bins):
    """The model at theta = 0 (no geology multipliers, no regional correction), built in memory by the S4 and
    S5 code with the critical zone, as the S13 forward problem does: geology against regional by depth, the
    fusion invariant, and the Vp/Vs at 2-4 km below ground before and after the calibration."""
    from rainier3d.cz.level import context_from_disk
    from rainier3d.fusion import build, regional
    from rainier3d.geomodel.rules import AIR, ICE
    from rainier3d.io.store import read_tree
    from rainier3d.petro.table import perturbations, petro_table
    from rainier3d.properties.assign import assign

    dom = load_domain()
    geo = read_tree(dom.path("processed") / "geomodel.zarr")
    table, pert = petro_table(), perturbations()
    cz = context_from_disk(dom, geo)
    cvm, cres = regional.load_cvm(dom), regional.load_crescent(dom)
    fc = dom.cfg["fusion"]
    acc = {ph: {b: [] for b in bins} for ph in ("vp", "vs")}
    inv, vpvs = {}, {"uncalibrated_regional": [], "calibrated_fused": []}
    for name, lev in dom.levels.items():
        gl = g[name]
        p = assign(gl, table, pert, None, cz)  # as S4: the critical-zone context on every level
        reg = build.regional_level(lev, gl["depth"].values, cvm, cres, None)
        out, rows = build.fuse_level(gl, p, reg, lev, fc, pert["q"], name, magma=pert["magma_mush"])
        inv[name] = {r["var"]: r["lowpass_rms_lnV"] for r in rows}
        u, d = gl.unit.values, gl.depth.values
        ok = (u != AIR) & (u != ICE)
        for ph in ("vp", "vs"):
            lr = np.log(p[ph].values / reg[ph])
            for b in bins:
                k = ok & (d >= b[0]) & (d < b[1]) & np.isfinite(lr)
                acc[ph][b].append(lr[k])
        k = ok & (d >= 2000) & (d < 4000)
        vpvs["uncalibrated_regional"].append((reg["vp"] / reg["vs"])[k])
        vpvs["calibrated_fused"].append((m[name].vp.values / m[name].vs.values)[k])
    put(
        "uncal.ln_geology_over_regional",
        {ph: {f"{a}-{b}": float(np.mean(np.concatenate(acc[ph][(a, b)]))) for a, b in bins} for ph in acc},
        "uncalibrated: mean ln(V_geology/V_regional) by depth below ground (m), L1-L3 without air and ice",
        "in memory: S4 + S5 code with the critical zone, no calibration",
    )
    put("uncal.invariant", inv, "uncalibrated: fusion low-pass departure by level", "in memory, as above")
    put(
        "cal.vpvs_2_4km",
        {k: float(np.median(np.concatenate(v))) for k, v in vpvs.items()},
        "median Vp/Vs at 2-4 km below ground: regional as distributed against the calibrated fused model",
        "in memory (uncalibrated regional), model.zarr (fused)",
    )


# ----------------------------------------------------------------------------------------------------- S26
def catalog():
    s = json.loads((REPO / "outputs/catalog/summary.json").read_text())
    put("s26.summary", s, "S26 summary", "outputs/catalog/summary.json")
    c = pd.read_csv(REPO / "outputs/catalog/catalog_relocated.csv")
    dom = load_domain()
    sx, sy = dom.summit_xy
    ab = c[c.located.astype(bool) & c.x_pnsn1d.notna() & c.x_rainier3d.notna()]
    ab = ab[ab["quality"].isin(["A", "B"])]  # graded from the rainier3d location
    r = np.hypot(ab.x_cc - sx, ab.y_cc - sy)
    west = sx - ab.x_cc
    regions = {"summit": r <= 3000, "wrsz": (west >= 8000) & (west <= 25000)}
    out = {"n_ab_both": int(len(ab))}
    for name, k in regions.items():
        e = {"n": int(k.sum())}
        for m in ("cc", "pnsn1d", "rainier3d"):
            z = ab.loc[k, f"z_{m}"] / 1e3
            e[m] = {"median_km": z.median(), "p05_km": z.quantile(0.05), "p95_km": z.quantile(0.95)}
        out[name] = e
    dz = (ab.z_pnsn1d - ab.z_rainier3d) / 1e3  # positive: deeper in rainier3d
    dh = np.hypot(ab.x_rainier3d - ab.x_pnsn1d, ab.y_rainier3d - ab.y_pnsn1d) / 1e3
    out["shift_1d_to_3d"] = {
        "horizontal_median_km": dh.median(),
        "deeper_median_km": dz.median(),
        "deeper_p10_km": dz.quantile(0.1),
        "deeper_p90_km": dz.quantile(0.9),
    }
    for m in ("pnsn1d", "rainier3d"):
        out[f"median_rms_s_{m}"] = ab[f"rms_{m}"].median()
        out[f"median_z_sd_km_{m}"] = ab[f"z_sd_km_{m}"].median()
        out[f"median_h_unc_max_km_{m}"] = ab[f"h_unc_max_km_{m}"].median()
    # NonLinLoc rejections (max-likelihood point on the search-grid boundary): on a side (x or y at the
    # edge, which takes precedence at corners), else at the base, else elsewhere (the topography mask)
    nll = REPO / "outputs/catalog/nll"
    g = (nll / "nlloc_rainier3d.in").read_text().split("LOCGRID")[1].split()
    nx, ny, nz, x0, y0, z0, dx = int(g[0]), int(g[1]), int(g[2]), *map(float, g[3:7])
    x1, y1, z1 = x0 + (nx - 1) * dx, y0 + (ny - 1) * dx, z0 + (nz - 1) * dx
    tol = 0.6 * dx
    rej = {}
    for m in ("pnsn1d", "rainier3d"):
        cnt = {"side": 0, "base": 0, "other": 0, "no_hypocentre": 0}
        for f in (nll / "loc").glob(f"{m}.*.grid0.loc.hyp"):
            lines = f.read_text(errors="ignore").splitlines()
            if not (lines and '"REJECTED"' in lines[0]):
                continue
            hyp = next((x for x in lines if x.startswith("HYPOCENTER")), None)
            if hyp is None:
                cnt["no_hypocentre"] += 1
                continue
            v = hyp.split()
            x, y, z = float(v[2]), float(v[4]), float(v[6])
            if min(x - x0, x1 - x, y - y0, y1 - y) < tol:
                cnt["side"] += 1
            elif z1 - z < tol:
                cnt["base"] += 1
            else:
                cnt["other"] += 1
        rej[m] = cnt
    out["rejected"] = rej
    pin = c[c.above_ground_m_pnsn1d > 0]  # events the 1D location pushes to the topography mask
    out["pinned_1d"] = {
        "n": int(len(pin)),
        "cc_km_bsl": [(-pin.z_cc / 1e3).min(), (-pin.z_cc / 1e3).max()],
        "rainier3d_km_bsl": [(-pin.z_rainier3d / 1e3).min(), (-pin.z_rainier3d / 1e3).max()],
    }
    out["above_ground_rainier3d"] = {
        "n": int((c.above_ground_m_rainier3d > 0).sum()),
        "max_m": float(c.above_ground_m_rainier3d.max()),
    }
    put(
        "s26.table",
        out,
        "relocation table: grade A/B events located in both models; summit within 3 km and WRSZ "
        "8-25 km west of the summit by ComCat epicentre; elevations in km (negative below sea level)",
        "outputs/catalog/catalog_relocated.csv (S26)",
    )


# ----------------------------------------------------------------------------------------------------- S37
def tomography():
    d = REPO / "outputs/tomography"
    s = json.loads((d / "summary.json").read_text())
    put("s37.summary", s, "S37 summary", "outputs/tomography/summary.json")
    import xarray as xr

    n = xr.open_dataset(d / "nodes.nc")
    dws_min = load_domain().cfg["tomography"]["dws_min_m"]
    upd = {}
    for ph in ("p", "s"):
        m = n[f"dlnv{ph}"].values[n[f"dws_{ph}"].values >= dws_min]
        upd[ph.upper()] = {
            "mean": float(m.mean()),
            "rms": float(np.sqrt((m**2).mean())),
            "n_nodes": int(m.size),
        }
    put(
        "s37.update_sampled",
        upd,
        "ln V update on nodes with derivative weight sum >= tomography.dws_min_m",
        "outputs/tomography/nodes.nc",
    )
    for tag in ("start", "final"):
        f = d / f"picks_{tag}.csv"
        if not f.exists():
            continue
        p = pd.read_csv(f)
        out = {}
        for ph in ("P", "S"):
            # as fig08 of report.tomography_figures: held-out picks with weight > 0, stations with >= 20 picks
            g = (
                p[(p.phase == ph) & (p.w > 0) & ~p.fitting.astype(bool)]
                .groupby("si")
                .res.agg(["mean", "size"])
            )
            g = g[g["size"] >= 20]
            out[ph] = {"rms_s": float(np.sqrt(np.mean(g["mean"] ** 2))), "n_stations": int(len(g))}
        put(
            f"s37.station_mean_rms_{tag}",
            out,
            "RMS of held-out residuals averaged per station (s)",
            str(f.relative_to(REPO)),
        )


# --------------------------------------------------------------------------------------------- applications
def applications():
    from rainier3d.io.store import read_tree

    dom = load_domain()
    f = REPO / "outputs/gnss/strain_3d_summary.json"
    if f.exists():
        put("s18.strain_3d", json.loads(f.read_text()), "S18 volume summary", str(f.relative_to(REPO)))
    f = REPO / "outputs/gnss/summary.json"
    if f.exists():
        put("s18.gnss", json.loads(f.read_text()), "S17/S18 summary", str(f.relative_to(REPO)))
    for name in ("summary", "storm_summary", "weathering_depth"):
        f = REPO / "outputs/cz" / f"{name}.json"
        if f.exists():
            put(
                f"cz_app.{name}",
                json.loads(f.read_text()),
                f"outputs/cz/{name}.json",
                str(f.relative_to(REPO)),
            )
    p = dom.path("processed") / "strain_3d.zarr"
    if p.exists():
        import xarray as xr

        t = xr.open_datatree(p, engine="zarr", consolidated=False)
        sx, sy = dom.summit_xy
        ratio, shear = [], []
        for node in t.subtree:
            ds = node.to_dataset()
            if "load_max_shear_h" not in ds or "tect_max_shear_rate" not in ds:
                continue
            X, Y = np.meshgrid(ds.x.values, ds.y.values)
            near = np.hypot(X - sx, Y - sy) <= 20000
            ls, tr = ds.load_max_shear_h.values, ds.tect_max_shear_rate.values
            k = np.broadcast_to(near, ls.shape) & np.isfinite(ls) & np.isfinite(tr) & (tr > 0)
            ratio.append(ls[k] / tr[k])
            shear.append(ls[k])
        if ratio:
            r, sh = np.concatenate(ratio), np.concatenate(shear)
            put(
                "s18.load_over_tect_years",
                {f"p{q}": float(np.percentile(r, q)) for q in (5, 50, 95)},
                "per-cell load max shear over geodetic max shear rate (years) within 20 km of the summit",
                "data/processed/strain_3d.zarr",
            )
            put(
                "s18.load_shear_microstrain",
                {f"p{q}": float(np.percentile(sh, q)) * 1e6 for q in (5, 50, 95)},
                "load horizontal max shear strain within 20 km of the summit",
                "data/processed/strain_3d.zarr",
            )
    p = dom.path("processed") / "edifice_load.zarr"
    if p.exists():
        t = read_tree(p)
        put(
            "s18.edifice_load_vars",
            sorted(t.to_dataset().data_vars) or sorted(t.children),
            "edifice-load store contents",
            "data/processed/edifice_load.zarr",
        )


GROUPS = {
    "calibration": calibration,
    "validation": validation,
    "relocation": relocation,
    "imush": imush,
    "model": model,
    "catalog": catalog,
    "tomography": tomography,
    "applications": applications,
}


def make_all(only=None):
    NUM.clear()
    skipped = {}
    for name, fn in GROUPS.items():
        if only and name not in only:
            continue
        try:
            fn()
        except FileNotFoundError as e:
            skipped[name] = f"missing input: {e.filename}"
            logging.warning("paper numbers: %s skipped (%s)", name, skipped[name])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"numbers": NUM, "skipped": skipped}, indent=1))
    logging.info("wrote %s (%d numbers)", OUT, len(NUM))
    return NUM
