"""S16: figures for the joint Vp-Vs calibration with 3D relocation (S13, S14) -> docs/joint_calibration/.

Reads configs/vs_calibration.yaml (S12), configs/velocity_calibration_v1.yaml (first S13 run, depth factors),
configs/velocity_calibration.yaml (S13 v2: geology multipliers + static bias of the regional model), the S14
relocations in outputs/relocation/<name>/ (all with slow air above the DEM + 1 cell), and the model snapshots
in data/processed/ named in MODELS.

Usage: pixi run python scripts/16_relocation_figures.py
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml

from rainier3d.config.domain import REPO, load_domain
from rainier3d.io.store import read_tree

OUT = REPO / "docs" / "joint_calibration"
# S14 run name -> (label, model snapshot or None for the 1D model)
MODELS = {
    "pnsn1d": ("PNSN 1D", None),
    "fused_nocal": ("3D, uncalibrated", "data/processed/model_nocal.zarr"),
    "fused_vscal": ("3D, Vs only (S12)", "data/processed/model_vscal_20260924.zarr"),
    "fused_v1": ("3D, depth factors (S13 v1)", "data/processed/model_joint_s13.zarr"),
    "fused_joint": ("3D, geology + bias (S13 v2)", "data/processed/model.zarr"),
}
COLORS = {
    "pnsn1d": "#7a7a7a",
    "fused_nocal": "#d98c2b",
    "fused_vscal": "#8a5cc2",
    "fused_v1": "#7fb3e8",
    "fused_joint": "#2a78d6",
}
BINS = np.array([0, 300, 1000, 2000, 3000, 4000, 5500, 7000, 9000, 11000, 14000, 18000, 24000])


def vpvs_profile(path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Median and 5-95% of Vp/Vs in bins of depth below ground, over L1-L3."""
    t = read_tree(REPO / path)
    d, r = [], []
    for lev in ("L1", "L2", "L3"):
        ds = t[lev].to_dataset()
        k = np.isfinite(ds.vs.values) & (ds.unit.values != 1)
        d.append(ds.depth.values[k])
        r.append((ds.vp.values / ds.vs.values)[k])
    d, r = np.concatenate(d), np.concatenate(r)
    i = np.digitize(d, BINS) - 1
    q = np.array(
        [
            np.percentile(r[i == j], [5, 50, 95]) if (i == j).sum() > 20 else [np.nan] * 3
            for j in range(BINS.size - 1)
        ]
    )
    return 0.5 * (BINS[1:] + BINS[:-1]), q[:, 1], q[:, [0, 2]]


def fig_factors():
    s12 = yaml.safe_load((REPO / "configs" / "vs_calibration.yaml").read_text())
    v1 = yaml.safe_load((REPO / "configs" / "velocity_calibration_v1.yaml").read_text())
    v2 = yaml.safe_load((REPO / "configs" / "velocity_calibration.yaml").read_text())["regional_bias"]
    k = np.array(v2["knots_m"]) / 1e3
    fig, ax = plt.subplots(1, 2, figsize=(9.5, 5.2), sharey=True, constrained_layout=True)
    ax[0].axvline(1, color="0.6", lw=0.8)
    ax[0].plot(
        s12["factor"], np.array(s12["knots_m"]) / 1e3, ":", color=COLORS["fused_vscal"], label="Vs, S12"
    )
    ax[0].plot(v1["vp"]["factor"], k, "--", color="#e08a78", label="Vp, S13 v1 (all depths)")
    ax[0].plot(v1["vs"]["factor"], k, "--", color=COLORS["fused_v1"], label="Vs, S13 v1 (all depths)")
    sd = v2["sd_log_factor"]
    kf = np.array(sd["free_knots_m"]) / 1e3
    for v, c, lab in (("vp", "#c2412d", "Vp"), ("vs", COLORS["fused_joint"], "Vs")):
        f = np.array(v2[v]["factor"])
        ax[0].plot(f, k, "o-", color=c, label=f"{lab}, S13 v2 static bias of the regional model")
        fk = f[np.isin(k, kf)]
        e = np.array(sd[v])
        ax[0].fill_betweenx(kf, fk * np.exp(-e), fk * np.exp(e), color=c, alpha=0.15, lw=0)
    ax[0].axhspan(-0.5, 1, color="0.85", alpha=0.5, lw=0)
    ax[0].text(1.12, 0.55, "geology model only", fontsize=8, color="0.3")
    ax[0].set(
        xlabel="factor on the regional velocity", ylabel="depth below ground (km)", title="(a) calibration"
    )
    ax[0].legend(frameon=False, fontsize=8, loc="lower right")
    for name in ("fused_nocal", "fused_vscal", "fused_v1", "fused_joint"):
        zc, med, band = vpvs_profile(MODELS[name][1])
        ax[1].plot(med, zc / 1e3, "-o", ms=3, color=COLORS[name], label=MODELS[name][0])
        if name in ("fused_nocal", "fused_joint"):
            ax[1].fill_betweenx(zc / 1e3, band[:, 0], band[:, 1], color=COLORS[name], alpha=0.12, lw=0)
    ax[1].axvline(np.sqrt(8 / 3), color="0.4", ls=":", lw=1)
    ax[1].text(np.sqrt(8 / 3), 23.5, " Qp = 2Qs limit", fontsize=8, color="0.3")
    ax[1].set(xlabel="Vp/Vs (median, 5-95%)", title="(b) Vp/Vs of the fused model", xlim=(1.55, 2.3))
    ax[1].legend(frameon=False, loc="lower right", fontsize=8)
    ax[0].invert_yaxis()
    fig.savefig(OUT / "fig1_factors_vpvs.png", dpi=160)


def fig_geology():
    """Crack-closure Vp and Vs of three rock units before and after the geology calibration (S4 law)."""
    from rainier3d.petro import relations as rel
    from rainier3d.petro.table import perturbations, petro_table

    g = yaml.safe_load((REPO / "configs" / "velocity_calibration.yaml").read_text())["geology"]
    t, pp = petro_table().set_index("unit"), perturbations()["pressure"]
    d = np.linspace(0, 6000, 200)
    p_mpa = (pp["rho_bulk_kgm3"] - pp["rho_water_kgm3"]) * 9.81 * d / 1e6
    fig, ax = plt.subplots(1, 2, figsize=(9.5, 5.2), sharey=True, constrained_layout=True)
    colors = {"rainier_andesite": "#c2412d", "ohanapecosh": "#2a78d6", "miocene_intrusive": "#3a9a5b"}
    for u, c in colors.items():
        r = t.loc[u]
        for cal, ls in (({}, "--"), (g, "-")):
            v0 = min(r.vp0_kms * np.exp(cal.get("ln_v0", 0)), 0.98 * r.vpinf_kms)
            vp = rel.crack_closure(v0, r.vpinf_kms, p_mpa, r.pstar_mpa * np.exp(cal.get("ln_pstar", 0)))
            vs = rel.brocher_vs_from_vp(vp) * np.exp(cal.get("ln_vs", 0))
            lab = f"{u.replace('_', ' ')}, {'calibrated' if cal else 'placeholder'}"
            ax[0].plot(vp, d / 1e3, ls, color=c, label=lab)
            ax[1].plot(vs, d / 1e3, ls, color=c)
    reg = read_tree(REPO / "data/processed/model_nocal.zarr")
    for j, v in enumerate(("vp", "vs")):
        dd, vv = [], []
        for lev in ("L1", "L2"):
            ds = reg[lev].to_dataset()
            k = np.isfinite(ds[f"{v}_regional"].values) & (ds.depth.values < 6000)
            dd.append(ds.depth.values[k])
            vv.append(ds[f"{v}_regional"].values[k])
        dd, vv = np.concatenate(dd), np.concatenate(vv) / 1e3
        b = np.arange(0, 6001, 500)
        i = np.digitize(dd, b) - 1
        med = [np.median(vv[i == m]) if (i == m).any() else np.nan for m in range(b.size - 1)]
        ax[j].plot(med, 0.5 * (b[1:] + b[:-1]) / 1e3, "k:", lw=1.5, label="CVM v1.7, median (uncalibrated)")
    ax[0].set(xlabel="Vp (km/s)", ylabel="depth below ground (km)", title="(a) Vp, crack-closure law (S4)")
    ax[1].set(xlabel="Vs (km/s)", title="(b) Vs")
    ax[0].legend(frameon=False, fontsize=7.5, loc="lower left")
    ax[1].legend(frameon=False, fontsize=7.5, loc="lower left")
    ax[0].invert_yaxis()
    fig.savefig(OUT / "fig4_geology_calibration.png", dpi=160)


def fig_residuals():
    fig, ax = plt.subplots(1, 2, figsize=(10, 5.2), constrained_layout=True)
    for j, ph in enumerate(("P", "S")):
        b = np.linspace(-1, 1, 61)
        for name, (lab, _) in MODELS.items():
            f = REPO / "outputs" / "relocation" / name / "picks.csv"
            if not f.exists():
                continue
            p = pd.read_csv(f)
            r = p[(p.phase == ph) & (p.w > 0)].res
            ax[j].hist(
                r,
                bins=b,
                histtype="step",
                lw=1.4,
                color=COLORS[name],
                label=f"{lab}: {np.sqrt(np.mean(r**2)):.3f} s",
            )
            ax[j].text(
                0.02,
                0.95 - 0.07 * list(MODELS).index(name),
                f"RMS {np.sqrt(np.mean(r**2)):.3f} s",
                transform=ax[j].transAxes,
                color=COLORS[name],
                fontsize=8,
                va="top",
            )
        ax[j].set(
            xlabel=f"{ph} residual after relocation (s)",
            ylabel="picks" if j == 0 else None,
            title=f"({'ab'[j]}) {ph}",
        )
    h, lab = ax[0].get_legend_handles_labels()
    fig.legend(
        h, [s_.split(":")[0] for s_ in lab], loc="outside lower center", ncol=4, frameon=False, fontsize=9
    )
    fig.savefig(OUT / "fig2_residuals.png", dpi=160)


def fig_hypocentres():
    dom = load_domain()
    c = pd.read_csv(REPO / "outputs" / "relocation" / "fused_joint" / "catalog.csv")
    c1 = pd.read_csv(REPO / "outputs" / "relocation" / "pnsn1d" / "catalog.csv").set_index("event")
    fig, ax = plt.subplots(1, 2, figsize=(10, 4.6), constrained_layout=True)
    x0, y0 = dom.bounds[0], dom.bounds[1]
    sx, sy = (c.x_catalog - x0) / 1e3, (c.y_catalog - y0) / 1e3
    ax[0].quiver(
        sx,
        sy,
        (c.x - c.x_catalog) / 1e3,
        (c.y - c.y_catalog) / 1e3,
        angles="xy",
        scale_units="xy",
        scale=1,
        width=0.003,
        color=COLORS["fused_joint"],
    )
    ax[0].scatter(sx, sy, s=8, color="k", zorder=3, label="ComCat")
    xs, ys = dom.summit_xy
    ax[0].plot((xs - x0) / 1e3, (ys - y0) / 1e3, "^", color="#c2412d", ms=9, label="summit")
    ax[0].set(
        aspect="equal",
        xlabel="easting from domain origin (km)",
        ylabel="northing (km)",
        title="(a) epicentre shift, ComCat to joint 3D",
    )
    ax[0].legend(frameon=False, fontsize=8)
    z_cat = -c.d_catalog / 1e3
    ax[1].scatter(z_cat, -c.d / 1e3, s=14, color=COLORS["fused_joint"], label="joint 3D")
    ax[1].scatter(
        z_cat,
        -c1.loc[c.event].d.values / 1e3,
        s=10,
        marker="x",
        color=COLORS["pnsn1d"],
        label="PNSN 1D (this locator)",
    )
    lim = [min(z_cat.min(), (-c.d / 1e3).min()) - 1, max(z_cat.max(), (-c.d / 1e3).max()) + 1]
    ax[1].plot(lim, lim, color="0.6", lw=0.8)
    ax[1].set(
        xlabel="ComCat elevation (km, depth taken below sea level)",
        ylabel="relocated elevation (km)",
        title="(b) hypocentre elevation",
        xlim=lim,
        ylim=lim,
        aspect="equal",
    )
    ax[1].legend(frameon=False, fontsize=8)
    fig.savefig(OUT / "fig3_hypocentres.png", dpi=160)


def relocation_qc():
    """Per model: events relocated above ground, at the grid top, or > 5 km in depth from ComCat."""
    dom = load_domain()
    surf = read_tree(dom.path("processed") / "model.zarr")["surface"].to_dataset()["elevation"]
    rows = []
    for name, (lab, _) in MODELS.items():
        c = pd.read_csv(REPO / "outputs" / "relocation" / name / "catalog.csv")
        g = surf.interp(x=("e", c.x.values), y=("e", c.y.values)).values
        dz = (c.d - c.d_catalog).abs()
        rows.append(
            {
                "model": lab,
                "events": len(c),
                "above_ground": int((-c.d.values > g).sum()),
                "at_grid_top": int((c.d <= -dom.cfg["validation"]["z_top"] + 100).sum()),
                "depth_change_gt_5km": int((dz > 5000).sum()),
                "events_depth_change_gt_5km": " ".join(c.event[dz > 5000]),
            }
        )
    pd.DataFrame(rows).to_csv(OUT / "relocation_qc.csv", index=False)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    relocation_qc()
    fig_factors()
    fig_geology()
    fig_residuals()
    fig_hypocentres()


if __name__ == "__main__":
    main()
