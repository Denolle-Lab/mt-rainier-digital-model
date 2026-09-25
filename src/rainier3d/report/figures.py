"""Figures for the model report (docs/report/figures/). Each function writes one PNG and returns its path.

Colour choices: velocities use Crameri's perceptually uniform ``roma`` (red slow, blue fast);
density ``cividis``; event depth a single-hue sequential ramp; categorical classes use the
validated reference palette in fixed order.
"""

from __future__ import annotations

import json

import matplotlib

matplotlib.use("Agg")
import cmcrameri.cm as cmc  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import xarray as xr  # noqa: E402
from matplotlib.colors import BoundaryNorm, LightSource, ListedColormap  # noqa: E402
from pyproj import Transformer  # noqa: E402

from rainier3d.petro.table import unit_names  # noqa: E402

CAT = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
INK, MUTED, GRID = "#1b1b1a", "#6b6a66", "#d9d8d3"
# fixed colours for the 16 model units: warm = young volcanic, greys/browns = basement, blues = ice/water
UNIT_COLORS = {
    1: "#dfeefb",
    2: "#7fb8e6",
    3: "#e8dcb5",
    4: "#f4e9c9",
    5: "#d9b88f",
    6: "#e07a5f",
    7: "#f2a65a",
    8: "#c9504b",
    9: "#8e7cc3",
    10: "#b7a6d6",
    11: "#6d6875",
    12: "#a8896c",
    13: "#c9b79c",
    14: "#5c5c5c",
    20: "#9aa5b1",
    21: "#b5179e",
}

plt.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.size": 8.5,
        "axes.labelsize": 8.5,
        "axes.titlesize": 9,
        "axes.edgecolor": MUTED,
        "axes.labelcolor": INK,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "axes.titleweight": "bold",
        "axes.titlelocation": "left",
        "legend.frameon": False,
        "savefig.dpi": 220,
        "savefig.bbox": "tight",
        "figure.dpi": 110,
    }
)


def _utm(dom):
    return Transformer.from_crs("EPSG:4326", dom.crs, always_xy=True)


def _unit_cmap():
    ids = sorted(UNIT_COLORS)
    cmap = ListedColormap([UNIT_COLORS[i] for i in ids])
    bounds = np.r_[np.array(ids) - 0.5, ids[-1] + 0.5]
    return cmap, BoundaryNorm(bounds, cmap.N), ids


def section_arrays(tree, var: str, axis: str, at: float):
    """Pieces (distance m, z m, values) of a vertical section along x (axis='x') or y from each level."""
    other = "y" if axis == "x" else "x"
    out = []
    for lev in ("L1", "L2", "L3"):
        ds = tree[lev].to_dataset()
        if var == "vpvs":
            da = ds["vp"] / ds["vs"]
        else:
            da = ds[var]
        sec = da.sel({other: at}, method="nearest").transpose("z", axis)
        out.append((sec[axis].values, sec["z"].values, sec.values.astype(float)))
    return out


def _events_near(events, dom, axis, at, width_m=2000.0):
    tf = _utm(dom)
    rows = []
    for f in events["features"]:
        x, y = tf.transform(*f["geometry"]["coordinates"])
        d = abs((y if axis == "x" else x) - at)
        if d <= width_m:
            rows.append(
                ((x if axis == "x" else y), -f["properties"]["depth"] * 1000, f["properties"]["mag"] or 0)
            )
    return np.array(rows) if rows else np.zeros((0, 3))


def _section_axes(ax, tree, var, axis, at, cmap, norm, zmin, events=None, dom=None, ice=True):
    m = None
    for d, z, v in section_arrays(tree, var, axis, at):
        if var == "unit":
            v = np.where(v == 0, np.nan, v)
        m = ax.pcolormesh(d / 1e3, z / 1e3, v, cmap=cmap, norm=norm, shading="nearest", rasterized=True)
    s = tree["surface"].to_dataset()
    other = "y" if axis == "x" else "x"
    surf = s["elevation"].sel({other: at}, method="nearest")
    ax.plot(surf[axis] / 1e3, surf / 1e3, color=INK, lw=0.8)
    if ice:
        h = s["ice_thickness"].sel({other: at}, method="nearest")
        ax.fill_between(
            surf[axis] / 1e3,
            (surf - h) / 1e3,
            surf / 1e3,
            where=h.values > 2,
            color="#bfe3ff",
            lw=0,
            zorder=3,
        )
    ax.axhline(0, color=MUTED, lw=0.5, ls=(0, (3, 3)))
    if events is not None:
        ev = _events_near(events, dom, axis, at)
        if len(ev):
            ax.scatter(
                ev[:, 0] / 1e3,
                ev[:, 1] / 1e3,
                s=2 + 3 * np.clip(ev[:, 2], 0, 4),
                facecolor="white",
                edgecolor=INK,
                lw=0.35,
                zorder=4,
            )
    ax.set_ylim(zmin / 1e3, 4.6)
    ax.set_ylabel("Elevation (km)")
    return m


def fig_map(tree, dom, sites, events, das, path, sec_a, sec_b):
    s = tree["surface"].to_dataset().sortby("y")
    x, y = s.x.values / 1e3, s.y.values / 1e3
    ls = LightSource(azdeg=315, altdeg=40)
    hs = ls.hillshade(s["elevation"].values, vert_exag=1.5, dx=100, dy=100)
    cmap, norm, ids = _unit_cmap()
    rgba = cmap(norm(np.clip(s["surface_unit"].values, 1, 21)))
    rgb = rgba[..., :3] * (0.55 + 0.45 * hs[..., None])
    fig, ax = plt.subplots(figsize=(7.2, 7.4))
    ext = [x[0] - 0.05, x[-1] + 0.05, y[0] - 0.05, y[-1] + 0.05]
    ax.imshow(rgb, origin="lower", extent=ext, interpolation="bilinear")
    ice = s["ice_thickness"].values
    ax.contour(x, y, ice, levels=[1.0], colors="#3b6ea5", linewidths=0.5)
    tf = _utm(dom)
    ev = pd.DataFrame(
        [
            (
                *tf.transform(*f["geometry"]["coordinates"]),
                f["properties"]["depth"],
                f["properties"]["mag"] or 0,
            )
            for f in events["features"]
        ],
        columns=["x", "y", "depth", "mag"],
    )
    depth_cmap = ListedColormap(cmc.lapaz_r(np.linspace(0.25, 1.0, 256)))  # drop the near-white end
    sc = ax.scatter(
        ev.x / 1e3,
        ev.y / 1e3,
        c=ev.depth,
        cmap=depth_cmap,
        vmin=0,
        vmax=20,
        s=1.5 + 2.5 * ev.mag.clip(0, 4),
        lw=0,
        alpha=0.8,
        zorder=3,
    )
    classes = [
        ("seismic", "Seismometer", "^", CAT[0]),
        ("infrasound", "Infrasound", "s", CAT[2]),
        ("gnss", "GNSS", "D", CAT[6]),
        ("strong", "Strong motion", "v", CAT[1]),
    ]
    for fam, label, mk, col in classes:
        pts = [
            tf.transform(*f["geometry"]["coordinates"])
            for f in sites["features"]
            if f["properties"]["status"] == "operating"
            and fam in f["properties"]["families"].split(",")
            and f["properties"]["family"] != "nodes"
        ]
        if pts:
            p = np.array(pts) / 1e3
            ax.scatter(
                p[:, 0],
                p[:, 1],
                marker=mk,
                s=22,
                facecolor=col,
                edgecolor="white",
                lw=0.6,
                zorder=5,
                label=f"{label} ({len(p)})",
            )
    nodes = [
        tf.transform(*f["geometry"]["coordinates"])
        for f in sites["features"]
        if f["properties"]["id"].startswith("node-")
    ]
    p = np.array(nodes) / 1e3
    ax.scatter(
        p[:, 0],
        p[:, 1],
        marker="o",
        s=6,
        facecolor=CAT[3],
        edgecolor=INK,
        lw=0.25,
        zorder=4,
        label=f"2025 nodes ({len(p)})",
    )
    dx, dy = tf.transform(das.lon.values, das.lat.values)
    ax.plot(np.array(dx) / 1e3, np.array(dy) / 1e3, color=INK, lw=2.4, zorder=5)
    ax.plot(np.array(dx) / 1e3, np.array(dy) / 1e3, color="white", lw=1.1, zorder=6, label="DAS fiber")
    for (a, b), lab in ((sec_a, "A"), (sec_b, "B")):  # each section = (start xy, end xy) in m
        ax.plot(
            [a[0] / 1e3, b[0] / 1e3], [a[1] / 1e3, b[1] / 1e3], color=INK, lw=1.0, ls=(0, (5, 3)), zorder=6
        )
        ax.annotate(
            lab, (a[0] / 1e3, a[1] / 1e3), xytext=(3, 3), textcoords="offset points", fontweight="bold"
        )
        ax.annotate(
            lab + "′",
            (b[0] / 1e3, b[1] / 1e3),
            xytext=(-12, 3) if b[0] > a[0] + 1 else (3, -12),
            textcoords="offset points",
            fontweight="bold",
        )
    ax.set_xlim(ext[0], ext[1])
    ax.set_ylim(ext[2], ext[3])
    ax.set_xlabel("UTM 10N easting (km)")
    ax.set_ylabel("UTM 10N northing (km)")
    ax.set_aspect("equal")
    ax.legend(
        loc="lower left",
        fontsize=7,
        markerscale=1.1,
        facecolor="white",
        frameon=True,
        framealpha=0.85,
        edgecolor=GRID,
    )
    cb = fig.colorbar(sc, ax=ax, shrink=0.45, pad=0.015)
    cb.set_label("PNSN event depth (km)")
    fig.savefig(path)
    plt.close(fig)
    return path


def fig_fusion(tree, dom, path, at_y, zmin=-12000):
    fig, axs = plt.subplots(3, 1, figsize=(7.2, 6.4), sharex=True, constrained_layout=True)
    norm = plt.Normalize(500, 4000)
    for ax, var, title in zip(
        axs,
        ("vs_geology", "vs_regional", "vs"),
        (
            "a  Geology-driven model (rock physics on the 3D units)",
            "b  Regional model (CVM v1.7 to 9.9 km, CRESCENT Gen0 below)",
            "c  Fused model: long wavelengths of b, short wavelengths of a",
        ),
        strict=True,
    ):
        m = _section_axes(ax, tree, var, "x", at_y, cmc.roma, norm, zmin)
        ax.set_title(title)
    axs[-1].set_xlabel("UTM 10N easting (km), section A–A′")
    cb = fig.colorbar(m, ax=axs, shrink=0.6, pad=0.01)
    cb.set_label("Vs (m/s)")
    fig.savefig(path)
    plt.close(fig)
    return path


def fig_sections(
    tree, dom, events, path, axis, at, label, zmin=-12000, variables=("vp", "vs", "rho", "unit")
):
    cfg = {
        "vp": (cmc.roma, plt.Normalize(1500, 7000), "Vp (m/s)"),
        "vs": (cmc.roma, plt.Normalize(500, 4000), "Vs (m/s)"),
        "rho": (plt.get_cmap("cividis"), plt.Normalize(1900, 2900), "Density (kg/m³)"),
        "vpvs": (cmc.vik, plt.Normalize(1.55, 2.2), "Vp/Vs"),
        "unit": (*_unit_cmap()[:2], "Model unit"),
    }
    fig, axs = plt.subplots(
        len(variables), 1, figsize=(7.2, 2.05 * len(variables)), sharex=True, constrained_layout=True
    )
    names = unit_names()
    for i, (ax, var) in enumerate(zip(axs, variables, strict=True)):
        cmap, norm, lab = cfg[var]
        m = _section_axes(ax, tree, var, axis, at, cmap, norm, zmin, events=events, dom=dom)
        ax.set_title(f"{'abcdef'[i]}  {lab}")
        if var == "unit":
            from matplotlib.patches import Patch

            present = sorted(
                {
                    int(u)
                    for *_, v in section_arrays(tree, "unit", axis, at)
                    for u in np.unique(v[np.isfinite(v)])
                    if u > 0
                }
            )
            handles = [
                Patch(facecolor=UNIT_COLORS[u], edgecolor=GRID, label=names[u].replace("_", " "))
                for u in present[::-1]
            ]
            ax.legend(
                handles=handles,
                loc="center left",
                bbox_to_anchor=(1.01, 0.5),
                fontsize=6.5,
                handlelength=1.2,
                handleheight=0.9,
                borderaxespad=0,
            )
        else:
            cb = fig.colorbar(m, ax=ax, pad=0.01, aspect=12)
            cb.set_label(lab)
    axs[-1].set_xlabel(f"UTM 10N {'easting' if axis == 'x' else 'northing'} (km), section {label}")
    fig.savefig(path)
    plt.close(fig)
    return path


def fig_profiles(tree, dom, path, points, pnsn_1d):
    fig, axs = plt.subplots(1, len(points), figsize=(7.2, 3.8), sharey=True, constrained_layout=True)
    tf = _utm(dom)
    for ax, (name, lon, lat) in zip(axs, points, strict=True):
        x, y = tf.transform(lon, lat)
        for var, ls_ in (("vp", "-"), ("vs", "--")):
            for suffix, col, lab in (
                ("_geology", CAT[1], "geology"),
                ("_regional", CAT[0], "regional"),
                ("", INK, "fused"),
            ):
                zz, vv = [], []
                for lev in ("L1", "L2", "L3"):
                    ds = tree[lev].to_dataset()
                    col_ = ds[var + suffix].sel(x=x, y=y, method="nearest")
                    zz.append(ds.z.values)
                    vv.append(col_.values)
                zz, vv = np.concatenate(zz), np.concatenate(vv)
                ax.plot(
                    vv / 1e3,
                    zz / 1e3,
                    color=col,
                    ls=ls_,
                    lw=1.3 if suffix == "" else 0.9,
                    label=f"{lab}" if var == "vp" else None,
                )
            zp = np.linspace(-20000, 0, 400)
            ax.plot(
                pnsn_1d(zp, "P" if var == "vp" else "S") / 1e3,
                zp / 1e3,
                color=CAT[2],
                ls=ls_,
                lw=0.9,
                label="PNSN 1D" if var == "vp" else None,
            )
        ax.set_title(name)
        ax.set_xlabel("Velocity (km/s)")
        ax.set_xlim(0, 7.5)
        ax.grid(color=GRID, lw=0.4)
    axs[0].set_ylabel("Elevation (km)")
    axs[0].set_ylim(-20, 4.6)
    axs[0].legend(loc="lower left", fontsize=7)
    fig.text(0.5, -0.02, "solid: Vp · dashed: Vs", ha="center", color=MUTED, fontsize=7.5)
    fig.savefig(path)
    plt.close(fig)
    return path


def fig_pnsn(res_csv, sta_csv, path):
    r = pd.read_csv(res_csv)
    st = pd.read_csv(sta_csv)
    fig, axs = plt.subplots(1, 2, figsize=(7.2, 3.2), constrained_layout=True)
    ax = axs[0]
    for m, col, lab in (("1d", CAT[0], "PNSN 1D"), ("3d", CAT[1], "rainier3d 3D")):
        p = r[r.phase == "P"]
        res = p.tt_obs - p[f"tt_{m}"]
        dm = res - res.groupby(p.event).transform("mean")
        ax.hist(
            dm,
            bins=np.linspace(-0.8, 0.8, 49),
            histtype="step",
            lw=1.4,
            color=col,
            label=f"{lab}  (RMS {np.sqrt((dm**2).mean()):.3f} s)",
        )
    ax.set_xlabel("P residual, event mean removed (s)")
    ax.set_ylabel("Picks")
    ax.set_title("a  P-pick residuals, 1828 picks")
    ax.legend(fontsize=7)
    ax = axs[1]
    for ph, col in (("P", CAT[0]), ("S", CAT[1])):
        g = st[(st.phase == ph) & (st.n >= 5)]
        c = np.corrcoef(g.res_1d, g.delay_3d_1d)[0, 1]
        ax.scatter(
            g.res_1d,
            g.delay_3d_1d,
            s=14,
            color=col,
            edgecolor="white",
            lw=0.4,
            label=f"{ph}: r = {c:.2f} ({len(g)} stations)",
        )
    g = st[st.n >= 5]
    ax.set_xlim(g.res_1d.min() - 0.1, g.res_1d.max() + 0.1)
    ax.set_ylim(min(0, g.delay_3d_1d.min() - 0.05), g.delay_3d_1d.max() + 0.1)
    ax.set_xlabel("Mean 1D residual per station (s)")
    ax.set_ylabel("Mean 3D − 1D predicted delay (s)")
    ax.set_title("b  Station terms explained by the 3D model")
    ax.legend(fontsize=7, loc="upper left")
    ax.grid(color=GRID, lw=0.4)
    fig.savefig(path)
    plt.close(fig)
    return path


def fig_glaciers(check_csv, path):
    c = pd.read_csv(check_csv)
    fig, ax = plt.subplots(figsize=(3.6, 3.4), constrained_layout=True)
    ax.scatter(
        c.glathida_mean_m, c.iceboost_mean_m, s=26, color=CAT[0], edgecolor="white", lw=0.5, label="mean"
    )
    ax.scatter(
        c.glathida_max_m,
        c.iceboost_max_m,
        s=26,
        marker="s",
        color=CAT[1],
        edgecolor="white",
        lw=0.5,
        label="maximum",
    )
    for _, r in c.iterrows():
        ax.annotate(
            r.glacier.split()[0].title(),
            (r.glathida_max_m, r.iceboost_max_m),
            xytext=(3, -2),
            textcoords="offset points",
            fontsize=6.5,
            color=MUTED,
        )
    ax.plot([0, 300], [0, 300], color=MUTED, lw=0.6, ls="--")
    ax.set_xlim(0, 300)
    ax.set_ylim(0, 300)
    ax.set_xlabel("GlaThiDa, 1981 radar (m)")
    ax.set_ylabel("IceBoost v2 (m)")
    ax.legend(fontsize=7, loc="upper left")
    ax.grid(color=GRID, lw=0.4)
    fig.savefig(path)
    plt.close(fig)
    return path


def fig_surface_layers(tree, dom, path):
    """Six environmental surface layers on the model grid, each over a hillshade, in km from the summit."""
    from matplotlib.colors import LogNorm, Normalize

    from rainier3d.export.atlas import NLCD

    s = tree["surface"].to_dataset()
    sx, sy = dom.summit_xy
    ext = [(dom.x[0] - sx) / 1e3, (dom.x[-1] - sx) / 1e3, (dom.y[0] - sy) / 1e3, (dom.y[-1] - sy) / 1e3]
    hs = LightSource(315, 40).hillshade(s["elevation"].values, dx=dom.surface_res_m, dy=dom.surface_res_m)
    panels = [
        ("soil_thickness", "(a) Soil thickness, SOLUS100 (m)", cmc.lajolla, (0, 2.01), False),
        ("water_table_depth", "(b) Water table, Ma et al. 2026 (m)", cmc.devon, (1, 100), True),
        ("water_table_depth_fan", "(c) Water table, Fan et al. 2017 (m)", cmc.devon, (1, 100), True),
        ("canopy_height", "(d) Canopy height, ETH 2020 (m)", cmc.bamako_r, (0, 60), False),
        ("land_cover", "(e) Land cover, NLCD 2021", None, None, False),
        ("stream_order", "(f) Stream order, NHDPlus HR", cmc.oslo_r, (0, 8), False),
    ]
    panels = [p for p in panels if p[0] in s]
    fig, axs = plt.subplots(2, 3, figsize=(7.2, 6.4), constrained_layout=True, sharex=True, sharey=True)
    for ax, (var, title, cmap, lim, log) in zip(axs.flat, panels, strict=False):
        a = s[var].values.astype(float)
        ax.imshow(hs, cmap="gray", origin="lower", extent=ext, vmin=0, vmax=1.2)
        if var == "land_cover":
            ids = sorted(NLCD)
            lut = ListedColormap([NLCD[i][1] for i in ids])
            norm = BoundaryNorm(np.r_[np.array(ids) - 0.5, ids[-1] + 0.5], lut.N)
            ax.imshow(
                np.where(a > 0, a, np.nan),
                cmap=lut,
                norm=norm,
                origin="lower",
                extent=ext,
                alpha=0.85,
                interpolation="nearest",
            )
        else:
            if var == "stream_order":
                a = np.where(a >= 1, a, np.nan)
            norm = LogNorm(*lim) if log else Normalize(*lim)
            im = ax.imshow(
                np.clip(a, lim[0], None) if log else a,
                cmap=cmap,
                norm=norm,
                origin="lower",
                extent=ext,
                alpha=0.9,
                interpolation="nearest",
            )
            fig.colorbar(im, ax=ax, orientation="horizontal", shrink=0.8, pad=0.02, aspect=30)
        ax.set_title(title, fontsize=7, loc="left")
        ax.set_aspect("equal")
    for ax in axs.flat[len(panels) :]:
        ax.set_visible(False)
    for ax in axs[:, 0]:
        ax.set_ylabel("km north of summit")
    fig.supxlabel("km east of summit", fontsize=8.5)
    fig.savefig(path)
    plt.close(fig)
    return path


def fig_vs_calibration(cal_yaml, pairs_csv, path):
    """(a) calibrated log-factor on the regional Vs against depth; (b) held-out S-P residuals before/after."""
    import yaml

    cal = yaml.safe_load(cal_yaml.read_text())
    k, f = np.array(cal["knots_m"]) / 1e3, np.array(cal["factor"])
    p = pd.read_csv(pairs_csv)
    held = p[~p.train]
    fig, (a, b) = plt.subplots(
        1, 2, figsize=(7.2, 3.2), constrained_layout=True, gridspec_kw={"width_ratios": [1, 1.6]}
    )
    a.plot(f, k, color=CAT[0], lw=1.6, marker="o", ms=4)
    a.axvline(1.0, color=MUTED, lw=0.6, ls="--")
    a.set_ylim(k.max(), 0)
    a.set_xlabel("Factor on regional Vs")
    a.set_ylabel("Depth below ground (km)")
    a.grid(color=GRID, lw=0.4)
    a.set_title("(a)", loc="left", fontsize=8.5)
    bins = np.arange(-1.5, 1.0, 0.05)
    for col, lab, c in (("r_before", "before", CAT[1]), ("r_after", "after", CAT[0])):
        r = held[col]
        b.hist(
            r,
            bins=bins,
            histtype="step",
            lw=1.4,
            color=c,
            label=f"{lab}: mean {r.mean():+.2f} s, RMS {np.sqrt((r**2).mean()):.2f} s",
        )
    b.axvline(0, color=MUTED, lw=0.6, ls="--")
    b.set_xlabel("S−P residual, observed − predicted (s)")
    b.set_ylabel("Held-out pairs")
    b.legend(fontsize=7, loc="upper left", frameon=False)
    b.grid(color=GRID, lw=0.4)
    b.set_title("(b)", loc="left", fontsize=8.5)
    fig.savefig(path)
    plt.close(fig)
    return path


def fig_strain(grid_nc, vel_csv, load_tree, tree, dom, gnss_cfg, path):
    """(a) Secular dilatation rate from GNSS (MIDAS velocities, adaptive Gaussian fit) with the QC-passed
    velocities; (b) mean stress and maximum shear from the edifice load, west-east through the summit."""
    from matplotlib.colors import LogNorm, TwoSlopeNorm

    g = xr.open_dataset(grid_nc)
    v = pd.read_csv(vel_csv)
    sx, sy = dom.summit_xy
    tf = Transformer.from_crs(4326, dom.crs, always_xy=True)
    fig, (a, b) = plt.subplots(
        1, 2, figsize=(7.2, 3.6), constrained_layout=True, gridspec_kw={"width_ratios": [1, 1.25]}
    )
    X, Y = (g.x.values - sx) / 1e3, (g.y.values - sy) / 1e3
    dil = g["dilatation"].values * 1e9
    im = a.pcolormesh(
        X, Y, dil, cmap=cmc.vik, norm=TwoSlopeNorm(0, -60, 60), shading="nearest", rasterized=True
    )
    fig.colorbar(im, ax=a, orientation="horizontal", shrink=0.85, pad=0.02, aspect=30).set_label(
        "Dilatation rate (nanostrain/yr)", fontsize=7.5
    )
    x0, y0, x1, y1 = dom.bounds
    a.plot(
        np.array([x0, x1, x1, x0, x0]) / 1e3 - sx / 1e3,
        np.array([y0, y0, y1, y1, y0]) / 1e3 - sy / 1e3,
        color=INK,
        lw=0.7,
    )
    px, py = tf.transform(*np.array(gnss_cfg["regions"]["wrsz"]["polygon"]).T)
    a.fill(np.array(px) / 1e3 - sx / 1e3, np.array(py) / 1e3 - sy / 1e3, fill=False, ec=INK, lw=0.7, ls="--")
    xy = np.array(tf.transform(v.lon.values, v.lat.values)).T
    ok = v.flag.isna() | (v.flag.astype(str).str.len() == 0)
    rel = (xy - [sx, sy]) / 1e3
    ve, vn = v.ve.values * 1e3, v.vn.values * 1e3
    ve0, vn0 = np.median(ve[ok]), np.median(vn[ok])  # velocities relative to the network median
    q = a.quiver(
        rel[ok, 0], rel[ok, 1], ve[ok] - ve0, vn[ok] - vn0, scale=40, width=0.004, color=INK, zorder=3
    )
    a.quiverkey(q, 0.8, 0.06, 2, "2 mm/yr", labelpos="N", fontproperties={"size": 7})
    a.scatter(rel[~ok, 0], rel[~ok, 1], marker="x", s=12, lw=0.8, color="#e34948", zorder=3)
    a.plot(0, 0, marker="^", ms=6, color=INK, mec="white", zorder=4)
    a.set_xlim(-70, 70)
    a.set_ylim(-70, 70)
    a.set_aspect("equal")
    a.set_xlabel("km east of summit")
    a.set_ylabel("km north of summit")
    a.set_title("(a) Secular dilatation rate, GNSS", fontsize=8, loc="left")

    at = sy
    zmin = -20000
    m = None
    for d, z, val in section_arrays(load_tree, "stress_mean", "x", at):
        comp = np.where(-val / 1e6 > 0.05, -val / 1e6, np.nan)  # compressive mean stress, MPa
        m = b.pcolormesh(
            (d - sx) / 1e3,
            z / 1e3,
            comp,
            cmap=cmc.lajolla,
            norm=LogNorm(0.5, 40),
            shading="nearest",
            rasterized=True,
        )
    for d, z, val in section_arrays(load_tree, "stress_max_shear", "x", at):
        D, Z = np.meshgrid((d - sx) / 1e3, z / 1e3)
        cs = b.contour(D, Z, val / 1e6, levels=[1, 2, 5, 10], colors=INK, linewidths=0.5)
        b.clabel(cs, fontsize=6, fmt="%g")
    surf = tree["surface"].to_dataset()["elevation"].sel(y=at, method="nearest")
    b.plot((surf.x - sx) / 1e3, surf / 1e3, color=INK, lw=0.8)
    b.axhline(0, color=MUTED, lw=0.5, ls=(0, (3, 3)))
    b.set_xlim(-25, 25)
    b.set_ylim(zmin / 1e3, 4.6)
    b.set_xlabel("km east of summit")
    b.set_ylabel("Elevation (km)")
    b.set_title("(b) Edifice load: mean stress, max shear contours (MPa)", fontsize=8, loc="left")
    fig.colorbar(m, ax=b, orientation="horizontal", shrink=0.85, pad=0.02, aspect=30).set_label(
        "Compressive mean stress (MPa)", fontsize=7.5
    )
    fig.savefig(path)
    plt.close(fig)
    return path


def fig_canopy(canopy, tree, dom, path):
    """Vegetation layers of the canopy-storage project (S19) on the surface grid, over a hillshade."""
    from matplotlib.colors import Normalize

    s = tree["surface"].to_dataset()
    sx, sy = dom.summit_xy
    ext = [(dom.x[0] - sx) / 1e3, (dom.x[-1] - sx) / 1e3, (dom.y[0] - sy) / 1e3, (dom.y[-1] - sy) / 1e3]
    hs = LightSource(315, 40).hillshade(s["elevation"].values, dx=dom.surface_res_m, dy=dom.surface_res_m)
    panels = [
        ("canopy_height_lidar", "(a) Canopy height, airborne lidar (m)", cmc.bamako_r, (0, 60)),
        ("vegetation_cover_lidar", "(b) Vegetation cover, lidar", cmc.bamako_r, (0, 1)),
        ("lai_sentinel2", "(c) Leaf area index, Sentinel-2", cmc.bamako_r, (0, 6)),
        ("gedi_pai", "(d) Plant area index, GEDI L2B", cmc.bamako_r, (0, 6)),
        ("gedi_canopy_height", "(e) Canopy height, GEDI L3 (m)", cmc.bamako_r, (0, 60)),
        ("gedi_biomass", "(f) Aboveground biomass, GEDI L4B (Mg/ha)", cmc.bamako_r, (0, 600)),
    ]
    fig, axs = plt.subplots(2, 3, figsize=(7.2, 6.4), constrained_layout=True, sharex=True, sharey=True)
    for ax, (var, title, cmap, lim) in zip(axs.flat, panels, strict=True):
        ax.imshow(hs, cmap="gray", origin="lower", extent=ext, vmin=0, vmax=1.2)
        im = ax.imshow(
            canopy[var].values.astype(float),
            cmap=cmap,
            norm=Normalize(*lim),
            origin="lower",
            extent=ext,
            alpha=0.9,
            interpolation="nearest",
        )
        fig.colorbar(im, ax=ax, orientation="horizontal", shrink=0.8, pad=0.02, aspect=30)
        ax.set_title(title, fontsize=7, loc="left")
        ax.set_aspect("equal")
    for ax in axs[:, 0]:
        ax.set_ylabel("km north of summit")
    fig.supxlabel("km east of summit", fontsize=8.5)
    fig.savefig(path)
    plt.close(fig)
    return path


def load_json(p):
    return json.loads(p.read_text())


def open_tree(path):
    return xr.open_datatree(path, engine="zarr", consolidated=False).load()
