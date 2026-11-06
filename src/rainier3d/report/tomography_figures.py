"""Figures of the S37 local-earthquake tomography, from its saved outputs -> outputs/tomography/report/.

Called at the end of scripts/37_tomography.py, or alone with its ``--figures-only`` (formerly a script of
its own).

Reads outputs/tomography/ (summary.json, history.json, nodes.nc, checkerboard.nc, picks_*.csv, catalog_*.csv,
stations.csv, fd_check.csv), data/processed/model.zarr (starting model) and model_let.zarr (final model).
Nothing is recomputed.

Colours: dln V on a diverging blue (fast) to red (slow) scale with a grey midpoint; ray coverage on one blue
ramp; start / final and fitting / held-out on the first two categorical slots (blue, orange). Nodes whose
derivative weight sum is below ``tomography.dws_min_m`` are greyed out.

Every figure is drawn at its printed width in Supplement S1 (docs/paper/tomography/, through
``rainier3d.report.style.save``, all text at least 11 pt) and copied to report/. With ``--site DIR``
(docs/tomography for the GitHub Pages report) the figures are also copied to DIR and the 3D data written there
with at most 30 vertices per ray, to keep the committed file small.

Usage: pixi run python scripts/37_tomography.py --figures-only [--site docs/tomography]
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr
from matplotlib.colors import LinearSegmentedColormap, ListedColormap
from pyproj import Transformer

from rainier3d.config.domain import load_domain
from rainier3d.io.store import read_tree
from rainier3d.report import style

BLUE, ORANGE, INK, MUTED, GRID = "#2a78d6", "#eb6834", "#1f2328", "#5b6068", "#d9dbde"
DIV = LinearSegmentedColormap.from_list(
    "slow_fast", ["#7f1d1d", "#d03b3b", "#ef9a8f", "#f0efec", "#86b6ef", "#2a78d6", "#0d366b"]
)  # negative (slow) red, positive (fast) blue
SEQ = ListedColormap(["#f6f8fb", "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"])
MASK = ListedColormap(["#ffffff"])
PAPER = style.PAPER / "tomography"  # the figures of Supplement S1
W_FULL, W_80 = style.PAGE_WIDTH_IN, 0.8 * style.PAGE_WIDTH_IN  # printed widths (in) of the figures

plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 11,
        "axes.titlesize": 11,
        "axes.labelsize": 11,
        "xtick.labelsize": 11,
        "ytick.labelsize": 11,
        "legend.fontsize": 11,
        "axes.edgecolor": MUTED,
        "axes.labelcolor": INK,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "figure.dpi": 150,
        "savefig.dpi": 300,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.01,  # the tight box stays within the printed width
        "legend.frameon": False,
    }
)


def make_all(site=None):
    """All report figures from outputs/tomography/; with ``site``, also the copies for the site folder."""
    dom = load_domain()
    tc = dom.cfg["tomography"]
    src = dom.path("outputs") / "tomography"
    out = src / "report"
    out.mkdir(exist_ok=True)
    S = json.loads((src / "summary.json").read_text())
    H = json.loads((src / "history.json").read_text())
    nodes = xr.open_dataset(src / "nodes.nc").load()
    cb = xr.open_dataset(src / "checkerboard.nc").load()
    st = pd.read_csv(src / "stations.csv", index_col="si")
    p0, p1 = pd.read_csv(src / "picks_start.csv"), pd.read_csv(src / "picks_final.csv")
    c0, c1 = (
        pd.read_csv(src / "catalog_start.csv", index_col=0),
        pd.read_csv(src / "catalog_final.csv", index_col=0),
    )
    fd = pd.read_csv(src / "fd_check.csv")
    sx, sy = Transformer.from_crs("EPSG:4326", dom.crs, always_xy=True).transform(*dom.cfg["summit_lonlat"])
    ctx = dict(nodes=nodes, st=st, summit=(sx, sy), dws_min=tc["dws_min_m"], bounds=dom.bounds)

    fig_data(out, c1, st, ctx, S)
    fig_checks(out, fd, S, H)
    for cell in tc["checkerboard_cells_m"]:
        fig_checkerboard(out, cb, int(cell), ctx)
    fig_recovery(out, S)
    fig_model(out, ctx, c1)
    fig_sections(out, dom, ctx, c1)
    fig_residuals(out, p0, p1)
    fig_station_terms(out, p0, p1, ctx)
    fig_relocation(out, c0, c1)
    if (src / "ray_density.nc").exists():
        dens = xr.open_dataset(src / "ray_density.nc").load()
        rays = json.loads((src / "rays_sample.json").read_text())
        fig_ray_density(out, dens, ctx)
        fig_rays_3d(out, rays, st, dom)
        export_3d(out, rays, st, dom)
    if site:
        site = Path(site)
        site.mkdir(parents=True, exist_ok=True)
        for f in sorted(out.glob("fig*.png")):
            shutil.copy2(f, site / f.name)
        if (src / "rays_sample.json").exists():
            export_3d(site, rays, st, dom, max_vertices=30)
        print("site files in", site)
    print("figures in", out)


# ---------------------------------------------------------------- helpers
def save(fig, out, name):
    """Write the figure of the supplement (docs/paper/tomography/) and copy it to the report folder."""
    PAPER.mkdir(exist_ok=True)
    style.save(fig, PAPER / name)
    shutil.copy2(PAPER / name, out / name)
    plt.close(fig)


def km(a):
    return np.asarray(a) / 1e3


def frame(ax, ctx, ticks=True):
    x0, y0, x1, y1 = ctx["bounds"]
    ax.set_xlim(km(x0), km(x1))
    ax.set_ylim(km(y0), km(y1))
    ax.set_aspect("equal")
    ax.plot(km(ctx["summit"][0]), km(ctx["summit"][1]), marker="^", ms=6, mfc="none", mec=INK, mew=1.0)
    if not ticks:
        ax.set_xticklabels([])
        ax.set_yticklabels([])


def node_map(ax, field, dws, ctx, vmax, cmap=DIV):
    n = ctx["nodes"]
    im = ax.pcolormesh(km(n.x), km(n.y), field.T, cmap=cmap, vmin=-vmax, vmax=vmax, shading="nearest")
    hide = np.where(dws.T < ctx["dws_min"], 1.0, np.nan)
    ax.pcolormesh(km(n.x), km(n.y), hide, cmap=MASK, shading="nearest", alpha=0.85)
    return im


def stations(ax, st, size=10):
    ax.scatter(km(st.x), km(st.y), s=size, marker="v", c="none", edgecolors=INK, linewidths=0.6, zorder=5)


def slice_grid(nrows, ncols, height):
    """Map panels (rows x depth columns) at the full printed width, tightly packed, without tick labels."""
    fig, ax = plt.subplots(nrows, ncols, figsize=(W_FULL, height), squeeze=False, layout="constrained")
    fig.get_layout_engine().set(w_pad=0.02, h_pad=0.02, wspace=0.02, hspace=0.02)
    return fig, ax


def depth_title(ax, d):
    ax.set_title(f"{d / 1e3:.0f} km", pad=3)


# ---------------------------------------------------------------- figures
def fig_data(out, cat, st, ctx, S):
    fig = plt.figure(figsize=(W_FULL, 3.5), layout="constrained")
    fig.get_layout_engine().set(wspace=0.03)
    gs = fig.add_gridspec(1, 3, width_ratios=[1, 1, 0.62])
    ax = fig.add_subplot(gs[0])
    for flag, col, lab in ((True, BLUE, "fitting"), (False, ORANGE, "held out")):
        c = cat[cat.fitting == flag]
        ax.scatter(km(c.x), km(c.y), s=2, c=col, lw=0, alpha=0.7, label=f"{lab} ({len(c)})")
    b = S["held_out_split"]["block_m"]
    x0, y0, x1, y1 = ctx["bounds"]
    for g in np.arange(np.floor(x0 / b) * b, x1 + 1, b):
        ax.axvline(km(g), color=GRID, lw=0.4, zorder=0)
    for g in np.arange(np.floor(y0 / b) * b, y1 + 1, b):
        ax.axhline(km(g), color=GRID, lw=0.4, zorder=0)
    stations(ax, st)
    frame(ax, ctx)
    ax.set_xticks([560, 590, 620])
    ax.set_xlabel("easting (km)")
    ax.set_ylabel("northing (km)")
    ax.set_title("(a) epicentres\nby set", loc="left")
    fig.legend(*ax.get_legend_handles_labels(), loc="outside lower left", ncol=2, markerscale=5,
               handletextpad=0.1)  # fmt: skip
    a1 = fig.add_subplot(gs[1], sharey=ax)
    sz = 4 + 40 * st.n_picks / st.n_picks.max()
    a1.scatter(km(st.x), km(st.y), s=sz, marker="v", c=BLUE, edgecolors="white", linewidths=0.4)
    frame(a1, ctx)
    a1.tick_params(labelleft=False)
    a1.set_xticks([560, 590, 620])
    a1.set_xlabel("easting (km)")
    a1.set_title(f"(b) {len(st)} stations\nmax {st.n_picks.max():,} picks", loc="left")
    a2 = fig.add_subplot(gs[2])
    bins = np.arange(-4, 31, 1)
    for flag, col in ((True, BLUE), (False, ORANGE)):
        a2.hist(
            km(cat.d[cat.fitting == flag]), bins=bins, orientation="horizontal", color=col, alpha=0.6, lw=0
        )
    a2.invert_yaxis()
    a2.set_ylabel("depth bsl (km)")
    a2.set_xlabel("events per km")
    a2.set_title("(c) hypocentre\ndepth", loc="left")
    a2.set_box_aspect(75 / 70 / 0.62)  # as tall as the maps
    save(fig, out, "fig01_data.png")


def fig_checks(out, fd, S, H):
    fig, ax = plt.subplots(1, 3, figsize=(W_FULL, 3.0), layout="constrained")
    fig.get_layout_engine().set(wspace=0.06)
    a = ax[0]
    lim = [min(fd.finite_difference.min(), fd.ray.min()), max(fd.finite_difference.max(), fd.ray.max())]
    a.plot(lim, lim, color=MUTED, lw=0.8, ls="--")
    a.scatter(fd.finite_difference, fd.ray, s=2, c=BLUE, lw=0, alpha=0.4)
    a.xaxis.set_major_locator(plt.MaxNLocator(3))
    f = S["fd_check"]
    a.set_title(f"(a) S kernel\nslope {f['slope_ray_on_fd']:.2f}, r = {f['corr']:.3f}", loc="left")
    a.set_xlabel("finite difference (s)")
    a.set_ylabel("ray integral dT/dm (s)")
    a = ax[1]
    sc = pd.DataFrame(S["lam_scan"])
    a.semilogx(sc.lam_s, sc.held_out_linear_nrms, "-o", color=BLUE, ms=4, lw=1.5)
    a.axhline(S["held_out_linear_nrms_no_change"], color=MUTED, lw=0.8, ls="--")
    k = sc.held_out_linear_nrms.idxmin()
    a.plot(sc.lam_s[k], sc.held_out_linear_nrms[k], "o", ms=8, mfc="none", mec=ORANGE, mew=1.5)
    a.set_xlabel("smoothing weight λs")
    a.set_ylabel("held-out nRMS (linearised)")
    a.set_title(f"(b) smoothing\nchosen λs = {S['lam_s']:g}", loc="left")
    a = ax[2]
    H = [h for h in H if "held_out_misfit" in h]  # failed trials have no misfit
    lab = [
        h["model"].replace("start", "0").replace("it ", "").replace(" step x1", "").replace(" step x0.5", "½")
        for h in H
    ]
    y = [h["held_out_misfit"] for h in H]
    col = [BLUE if h["accepted"] else ORANGE for h in H]
    a.plot(range(len(y)), y, color=GRID, lw=1, zorder=0)
    a.scatter(range(len(y)), y, c=col, s=28, zorder=2)
    a.set_xticks(range(len(y)))
    a.set_xticklabels(lab)
    a.set_xlabel("iteration (½ step)")
    a.set_ylabel("held-out mean (r/σ)²")
    a.set_title("(c) trial models", loc="left")
    save(fig, out, "fig02_checks.png")


def depth_columns(nodes):
    return [d for d in nodes.d.values if 0 <= d <= 13000]


def fig_checkerboard(out, cb, cell, ctx):
    n = ctx["nodes"]
    ds = depth_columns(n)
    fig, ax = slice_grid(4, len(ds), 4.9)
    rows = (
        (f"true_p_{cell}", "dws_p", "input P"),
        (f"recovered_p_{cell}", "dws_p", "recovered P"),
        (f"true_s_{cell}", "dws_s", "input S"),
        (f"recovered_s_{cell}", "dws_s", "recovered S"),
    )
    for r, (v, w, lab) in enumerate(rows):
        vmax = 0.05 if r % 2 == 0 else 0.02
        for c, d in enumerate(ds):
            a = ax[r, c]
            im = node_map(a, cb[v].sel(d=d).values, n[w].sel(d=d).values, ctx, vmax)
            frame(a, ctx, ticks=False)
            if r == 0:
                depth_title(a, d)
            if c == 0:
                a.set_ylabel(lab, labelpad=2)
        fig.colorbar(im, ax=ax[r, :].tolist(), pad=0.01, aspect=10, ticks=[-vmax, 0, vmax])
    save(fig, out, f"fig03_checkerboard_{cell // 1000}km.png")


def fig_recovery(out, S):
    fig, ax = plt.subplots(1, 2, figsize=(0.75 * W_FULL, 3.4), sharey=True, layout="constrained")
    for cell, ls in (("12000", "-"), ("6000", ":")):
        for ph, col in (("P", BLUE), ("S", ORANGE)):
            rows = [r for r in S["checkerboard"][cell][ph] if "corr" in r]
            d = km([r["d_m"] for r in rows])
            ax[0].plot([r["corr"] for r in rows], d, ls, color=col, marker="o", ms=3, lw=1.5,
                       label=f"{ph}, {int(cell) // 1000} km")  # fmt: skip
            ax[1].plot([r["amp_ratio"] for r in rows], d, ls, color=col, marker="o", ms=3, lw=1.5)
    for a, lab in zip(ax, ("correlation", "amplitude ratio"), strict=True):
        a.axvline(0, color=GRID, lw=0.8)
        a.set_xlabel(lab)
        a.xaxis.set_major_locator(plt.MaxNLocator(3))
    ax[0].invert_yaxis()
    ax[0].set_ylabel("node depth bsl (km)")
    fig.legend(*ax[0].get_legend_handles_labels(), loc="outside lower center", ncol=4, handlelength=1.6,
               columnspacing=0.8, handletextpad=0.3)  # fmt: skip
    ax[0].set_title("(a) pattern", loc="left")
    ax[1].set_title("(b) amplitude", loc="left")
    save(fig, out, "fig04_recovery_by_depth.png")


def fig_model(out, ctx, cat):
    n = ctx["nodes"]
    ds = depth_columns(n)
    fig, ax = slice_grid(3, len(ds), 3.8)
    for c, d in enumerate(ds):
        near = cat[np.abs(cat.d - d) < 1500]
        for r, (v, w, lab) in enumerate((("dlnvp", "dws_p", "dln Vp"), ("dlnvs", "dws_s", "dln Vs"))):
            a = ax[r, c]
            im = node_map(a, n[v].sel(d=d).values, n[w].sel(d=d).values, ctx, 0.08)
            a.scatter(km(near.x), km(near.y), s=0.6, c=INK, lw=0, alpha=0.5)
            frame(a, ctx, ticks=False)
            if r == 0:
                depth_title(a, d)
            if c == 0:
                a.set_ylabel(lab, labelpad=2)
        a = ax[2, c]
        dws = n["dws_s"].sel(d=d).values
        im2 = a.pcolormesh(km(n.x), km(n.y), np.log10(np.maximum(dws, 1)).T, cmap=SEQ, vmin=3, vmax=7,
                           shading="nearest")  # fmt: skip
        stations(a, ctx["st"], 5)
        frame(a, ctx, ticks=False)
        if c == 0:
            a.set_ylabel("DWS, S", labelpad=2)
    v = ax[:2, :].ravel().tolist()
    fig.colorbar(im, ax=v, pad=0.01, aspect=16, label="dln V", ticks=[-0.08, 0, 0.08])
    fig.colorbar(im2, ax=ax[2, :].tolist(), pad=0.01, aspect=8, label="log₁₀ m", ticks=[3, 5, 7])
    save(fig, out, "fig05_model_slices.png")


def section(tree, var, along, at, s_axis, zs):
    """var on a vertical section (len(zs), len(s_axis)) through L1-L3; along 'x' (W-E at y=at) or 'y'."""
    outv = np.full((zs.size, s_axis.size), np.nan)
    for lev in ("L1", "L2", "L3"):
        ds = tree[lev].to_dataset()
        dz = ds.attrs["dz"]
        sel = (zs <= float(ds.z.max()) + dz / 2) & (zs > float(ds.z.min()) - dz / 2) & np.isnan(outv[:, 0])
        if not sel.any():
            continue
        a = ds[var].sel(y=at, method="nearest") if along == "x" else ds[var].sel(x=at, method="nearest")
        kw = {"x": s_axis} if along == "x" else {"y": s_axis}
        outv[sel] = a.sel(z=zs[sel], method="nearest").sel(**kw, method="nearest").values
    return outv


def fig_sections(out, dom, ctx, cat):
    t0 = read_tree(dom.path("processed") / "model.zarr")
    t1 = read_tree(dom.path("processed") / "model_let.zarr")
    sx, sy = ctx["summit"]
    x0, y0, x1, y1 = dom.bounds
    zs = np.arange(4400, -20001, -100.0)
    fig, ax = plt.subplots(4, 2, figsize=(W_FULL, 8.3), sharey=True, layout="constrained")
    fig.get_layout_engine().set(wspace=0.03, hspace=0.04)
    for c, (along, at, s_axis, lab) in enumerate(
        (("x", sy, np.arange(x0, x1, 250.0), "W–E"),
         ("y", sx, np.arange(y0, y1, 250.0), "S–N"))
    ):  # fmt: skip
        vs0 = section(t0, "vs", along, at, s_axis, zs)
        vs1 = section(t1, "vs", along, at, s_axis, zs)
        vp1 = section(t1, "vp", along, at, s_axis, zs)
        near = cat[np.abs((cat.y if along == "x" else cat.x) - at) < 3000]
        hs = near.x if along == "x" else near.y
        panels = (
            (vs0, "Vs, starting (m/s)", "viridis_r", (1500, 4000)),
            (vs1, "Vs, updated (m/s)", "viridis_r", (1500, 4000)),
            (np.log(vs1 / vs0), "dln Vs", DIV, (-0.08, 0.08)),
            (vp1 / vs1, "Vp/Vs, updated", "cividis", (1.6, 1.95)),
        )
        for r, (f, ttl, cm, (lo, hi)) in enumerate(panels):
            a = ax[r, c]
            im = a.pcolormesh(
                km(s_axis), km(zs), f, cmap=cm, vmin=lo, vmax=hi, shading="nearest", rasterized=True
            )
            a.scatter(km(hs), -km(near.d), s=0.8, c="white" if r < 2 else INK, lw=0, alpha=0.6)
            a.set_ylim(-20, 4.5)
            a.set_title(f"{lab}: {ttl}", loc="left")
            if r < 3:
                a.tick_params(labelbottom=False)
            if c == 1:
                cbar = fig.colorbar(im, ax=ax[r, :].tolist(), pad=0.01, aspect=12)
                cbar.ax.yaxis.set_major_locator(plt.MaxNLocator(3))
        ax[3, c].set_xlabel("easting (km)" if along == "x" else "northing (km)")
    for r in range(4):
        ax[r, 0].set_ylabel("elevation (km)")
    save(fig, out, "fig06_sections.png")


def fig_residuals(out, p0, p1):
    fig, ax = plt.subplots(2, 2, figsize=(W_FULL, 5.4), layout="constrained")
    fig.get_layout_engine().set(wspace=0.04, hspace=0.06)
    for r, ph in enumerate(("P", "S")):
        for c, (fit, lab) in enumerate(((True, "fitting events"), (False, "held-out events"))):
            a = ax[r, c]
            lim = 0.6 if ph == "P" else 1.0
            bins = np.linspace(-lim, lim, 61)
            for p, col, tag in ((p0, BLUE, "start"), (p1, ORANGE, "final")):
                g = p[(p.phase == ph) & (p.fitting == fit) & (p.w > 0)]
                rms = np.sqrt(np.mean(g.res**2))
                a.hist(g.res, bins=bins, histtype="step", color=col, lw=1.5, label=f"{tag}, RMS {rms:.3f} s")
            a.set_title(f"{ph}, {lab}")
            a.legend(loc="upper left", handlelength=1.2, borderaxespad=0.2)
            a.set_ylim(top=a.get_ylim()[1] * 1.35)  # room for the legend
            a.yaxis.set_major_locator(plt.MaxNLocator(4))
            if r == 1:
                a.set_xlabel("residual after relocation (s)")
    ax[0, 0].set_ylabel("picks per bin")
    ax[1, 0].set_ylabel("picks per bin")
    save(fig, out, "fig07_residuals.png")


def fig_station_terms(out, p0, p1, ctx):
    st = ctx["st"]
    fig, ax = plt.subplots(2, 2, figsize=(W_FULL, 6.6), sharex=True, sharey=True, layout="constrained")
    fig.get_layout_engine().set(wspace=0.02, hspace=0.04)
    for r, ph in enumerate(("P", "S")):
        lim = 0.15 if ph == "P" else 0.3
        for c, (p, tag) in enumerate(((p0, "start"), (p1, "final"))):
            g = p[(p.phase == ph) & (p.w > 0) & ~p.fitting].groupby("si").res.agg(["mean", "size"])
            g = g[g["size"] >= 20].join(st)
            a = ax[r, c]
            im = a.scatter(km(g.x), km(g.y), c=g["mean"], cmap=DIV.reversed(), vmin=-lim, vmax=lim, s=40,
                           marker="v", edgecolors=INK, linewidths=0.4)  # fmt: skip
            frame(a, ctx)
            a.set_xticks([560, 590, 620])
            rms = np.sqrt(np.mean(g["mean"] ** 2))
            a.set_title(f"{ph}, {tag} model\nRMS {rms:.3f} s, {len(g)} stations", loc="left")
            if r == 1:
                a.set_xlabel("easting (km)")
            if c == 0:
                a.set_ylabel("northing (km)")
        fig.colorbar(im, ax=ax[r, :].tolist(), pad=0.01, aspect=14, label="mean residual (s)",
                     ticks=[-lim, 0, lim])  # fmt: skip
    save(fig, out, "fig08_station_means.png")


def fig_relocation(out, c0, c1):
    j = c0.join(c1, lsuffix="_0", rsuffix="_1")
    dh = np.hypot(j.x_1 - j.x_0, j.y_1 - j.y_0)
    dd = j.d_1 - j.d_0
    fig = plt.figure(figsize=(W_80, 5.0), layout="constrained")
    fig.get_layout_engine().set(wspace=0.04, hspace=0.06)
    gs = fig.add_gridspec(2, 2)
    ax = [fig.add_subplot(gs[0, 0]), fig.add_subplot(gs[0, 1]), fig.add_subplot(gs[1, :])]
    ax[0].hist(km(dh), bins=np.arange(0, 3.001, 0.1), color=BLUE, lw=0)
    ax[0].set_xlabel("epicentre shift (km)")
    ax[0].set_ylabel("events")
    ax[0].set_title(f"(a) median {np.median(dh):.0f} m", loc="left")
    ax[1].hist(km(dd), bins=np.arange(-3, 3.001, 0.1), color=BLUE, lw=0)
    ax[1].set_xlabel("depth change (km)")
    ax[1].set_title(f"(b) median {np.median(dd):+.0f} m".replace("-", "−"), loc="left")
    ax[2].scatter(km(j.d_0), km(dd), s=2, c=BLUE, lw=0, alpha=0.4)
    ax[2].axhline(0, color=GRID, lw=0.8)
    ax[2].set_xlabel("starting depth below sea level (km)")
    ax[2].set_ylabel("depth change (km)\n+ deeper")
    ax[2].set_title("(c) depth change with depth", loc="left")
    save(fig, out, "fig09_relocation.png")


def fig_ray_density(out, dens, ctx):
    """Ray length density in 1 km cubes (km of ray per km^3, the eikonal-grid lengths summed over the cube):
    depth slices for P and S and sections through the summit for P + S."""
    dx = float(dens.attrs.get("dx_m", 250))
    k = max(int(round(1000 / dx)), 1)
    agg = {ph: dens[f"length_{ph}"].coarsen(x=k, y=k, z=k, boundary="trim").sum() / 1e3 for ph in ("p", "s")}
    ds = [0, 2000, 4000, 6000, 9000, 13000]
    fig, ax = slice_grid(2, len(ds), 2.75)
    for r, ph in enumerate(("p", "s")):
        for c, d in enumerate(ds):
            a = ax[r, c]
            sl = agg[ph].sel(z=-d, method="nearest")
            lg = np.log10(np.maximum(sl.values, 0.1)).T
            im = a.pcolormesh(
                km(sl.x), km(sl.y), lg, cmap=SEQ, vmin=0, vmax=4, shading="nearest", rasterized=True
            )
            stations(a, ctx["st"], 4)
            frame(a, ctx, ticks=False)
            if r == 0:
                depth_title(a, d)
            if c == 0:
                a.set_ylabel(f"{ph.upper()} rays", labelpad=2)
    fig.colorbar(im, ax=ax.ravel().tolist(), pad=0.01, aspect=12, label="log₁₀ km/km³", ticks=[0, 2, 4])
    save(fig, out, "fig10_ray_density_slices.png")

    sx, sy = ctx["summit"]
    tot = agg["p"] + agg["s"]
    fig, ax = plt.subplots(2, 1, figsize=(W_80, 4.6), layout="constrained")
    fig.get_layout_engine().set(hspace=0.06)
    for a, (sec, lab, axis) in zip(ax, ((tot.sel(y=sy, method="nearest"), "W–E through the summit", "x"),
                                       (tot.sel(x=sx, method="nearest"), "S–N through the summit", "y")),
                                   strict=True):  # fmt: skip
        h = sec.transpose("z", axis)
        lg = np.log10(np.maximum(h.values, 0.1))
        im = a.pcolormesh(
            km(h[axis]), km(h.z), lg, cmap=SEQ, vmin=0, vmax=4, shading="nearest", rasterized=True
        )
        a.set_ylim(-25, 4.5)
        a.set_ylabel("elevation (km)")
        a.set_xlabel("easting (km)" if axis == "x" else "northing (km)")
        a.set_title(lab, loc="left")
    fig.colorbar(
        im, ax=ax.tolist(), pad=0.01, aspect=20, label="log₁₀ km of ray per km³", ticks=[0, 1, 2, 3, 4]
    )
    save(fig, out, "fig10b_ray_density_sections.png")


def fig_rays_3d(out, rays, st, dom):
    """Static 3D view of the sampled rays (P blue, S orange), stations and hypocentres."""
    from mpl_toolkits.mplot3d import Axes3D  # noqa: F401

    fig = plt.figure(figsize=(W_80, 4.4))
    a = fig.add_subplot(111, projection="3d")
    n = {"P": 0, "S": 0}
    for r in rays:
        if n[r["phase"]] >= 400:  # 400 per phase keeps the figure legible
            continue
        n[r["phase"]] += 1
        q = np.asarray(r["xyz_km"])
        a.plot(q[:, 0], q[:, 1], q[:, 2], color=BLUE if r["phase"] == "P" else ORANGE, lw=0.35, alpha=0.35)
    src = np.array([r["xyz_km"][0] for r in rays])
    a.scatter(src[:, 0], src[:, 1], src[:, 2], s=1.5, c=INK, alpha=0.5, depthshade=False)
    a.scatter(km(st.x), km(st.y), st.elev / 1e3, marker="v", s=14, c="white", edgecolors=INK, linewidths=0.6)
    x0, y0, x1, y1 = dom.bounds
    a.set_xlim(km(x0), km(x1))
    a.set_ylim(km(y0), km(y1))
    a.set_zlim(-25, 5)
    a.set_xticks([560, 590, 620])
    a.set_yticks([5160, 5190, 5220])
    a.set_zticks([-20, -10, 0])
    a.set_box_aspect((70, 75, 30))
    a.view_init(elev=22, azim=-60)
    a.set_xlabel("easting (km)", labelpad=6)
    a.set_ylabel("northing (km)", labelpad=10)
    a.set_zlabel("elevation (km)", labelpad=4)
    a.set_title(f"{n['P']} P (blue) and {n['S']} S (orange) rays", y=0.93)
    save(fig, out, "fig11_rays_3d.png")


def export_3d(out, rays, st, dom, max_vertices=None):
    """Data of the interactive 3D view: rays (as sampled, or thinned to ``max_vertices`` keeping both ends),
    stations and a 1 km terrain grid (km, z up)."""
    if max_vertices:
        thin = []
        for r in rays:
            q = r["xyz_km"]
            idx = np.unique(np.linspace(0, len(q) - 1, min(len(q), max_vertices)).round().astype(int))
            thin.append({"phase": r["phase"], "event": r["event"],
                         "xyz_km": [[round(c, 2) for c in q[i]] for i in idx]})  # fmt: skip
        rays = thin
    tree = read_tree(dom.path("processed") / "model.zarr")
    e = tree["surface"].to_dataset()["elevation"].coarsen(x=10, y=10, boundary="trim").mean()
    data = {
        "rays": rays,
        "stations": np.round(np.column_stack([km(st.x), km(st.y), st.elev / 1e3]), 3).tolist(),
        "terrain": {"x": np.round(km(e.x.values), 2).tolist(), "y": np.round(km(e.y.values), 2).tolist(),
                    "z": np.round(e.values / 1e3, 3).tolist()},
    }  # fmt: skip
    (out / "rays3d.json").write_text(json.dumps(data))
