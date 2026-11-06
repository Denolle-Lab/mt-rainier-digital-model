"""S21: compare rainier3d and its regional baseline with the iMUSH local-earthquake tomography
(Ulberg et al. 2020).

A test of the S13 static bias on CVM v1.7 / CRESCENT: at every Ulberg node inside the domain that the EMC
file leaves unmasked (checkerboard recovery for 20 km features), sample
  regional      CVM v1.7 / CRESCENT, the CVM-to-CRESCENT jump spread over fusion.regional_blend_m (8-16 km
                below the ground), with no calibration          (vp_regional, vs_regional of model_nocal.zarr)
  regional_bias the same with the S13 static bias          (vp_regional, vs_regional of model.zarr)
  fused_uncal   the fused model before calibration          (vp, vs of model_nocal.zarr)
  fused_v2      the fused model after S13 (critical zone)   (vp, vs of model.zarr)
and report ln(V_Ulberg / V_model) by depth below the ground, for the whole domain and for its south
(< 46.65 N, inside the iMUSH array) and north (>= 46.75 N, Rainier). Vp/Vs is compared with Ulberg's
'matched' Vp and Vs
(the same ~3600 arrivals for both phases).

Ulberg depth is taken as km below sea level: the EMC page and figure captions say so, although the netCDF
long_name says "depth below earth surface" (the axis starts at -5 km, which only sea level allows).

Writes outputs/model_comparison/ulberg2020_by_depth.csv and docs/joint_calibration/fig5_imush_comparison.png.
Usage: pixi run python scripts/21_compare_imush.py [--figures-only]  (redraw from ulberg2020_by_depth.csv)
"""

from __future__ import annotations

import argparse

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr
from pyproj import Transformer

from rainier3d.config.domain import REPO, load_domain
from rainier3d.io.store import read_tree
from rainier3d.report import style

ULBERG = REPO / "data" / "raw" / "emc" / "iMUSH-localEQ-Ulberg-2020.r0.0-n4c.nc"
URL = (
    "https://data.earthscope.org/archive/seismology/products/emc/netcdf/iMUSH-localEQ-Ulberg-2020.r0.0-n4c.nc"
)
BINS = np.array([0, 1000, 2000, 3000, 4000, 6000, 8000, 11000, 15000, 20000])
SOUTH_MAX, NORTH_MIN = 46.65, 46.75
MODELS = {
    "regional": ("data/processed/model_nocal.zarr", "{v}_regional"),
    "regional_bias": ("data/processed/model.zarr", "{v}_regional"),
    "fused_uncal": ("data/processed/model_nocal.zarr", "{v}"),
    "fused_v2": ("data/processed/model.zarr", "{v}"),
}


def ulberg_nodes(dom) -> pd.DataFrame:
    """Unmasked Ulberg nodes inside the domain, with UTM x, y, elevation z (m) and velocities (m/s)."""
    if not ULBERG.exists():
        raise SystemExit(f"download {URL} to {ULBERG}")
    lon0, lat0, lon1, lat1 = dom.bbox_4326
    ds = xr.open_dataset(ULBERG).sel(latitude=slice(lat0, lat1), longitude=slice(lon0, lon1))
    ds = ds.sel(depth=slice(-5.0, 20.0))  # our model ends 20 km below sea level
    df = ds[["vp", "vs", "vp_matched", "vs_matched"]].to_dataframe().reset_index()
    df = df[np.isfinite(df.vp) | np.isfinite(df.vs)].copy()
    for c in ("vp", "vs", "vp_matched", "vs_matched"):
        df[c] *= 1e3
    tf = Transformer.from_crs("EPSG:4326", dom.crs, always_xy=True)
    df["x"], df["y"] = tf.transform(df.longitude.values, df.latitude.values)
    df["z"] = -df.depth.values * 1e3
    x0, y0, x1, y1 = dom.bounds
    return df[(df.x > x0) & (df.x < x1) & (df.y > y0) & (df.y < y1)].reset_index(drop=True)


def sample(tree, var: str, df: pd.DataFrame) -> np.ndarray:
    """Linear interpolation of a model variable at the nodes (NaN in air or outside the levels)."""
    out = np.full(len(df), np.nan)
    for lev in ("L1", "L2", "L3"):
        ds = tree[lev].to_dataset()
        dz = ds.attrs["dz"]
        k = (df.z <= float(ds.z.max()) + dz / 2) & (df.z >= float(ds.z.min()) - dz / 2) & np.isnan(out)
        if not k.any():
            continue
        p = {c: xr.DataArray(df.loc[k, c].values, dims="p") for c in ("x", "y", "z")}
        out[k.values] = ds[var].interp(x=p["x"], y=p["y"], z=p["z"]).values
    return out


def summarize(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    df = df.assign(bin=np.digitize(df.depth_bg, BINS) - 1)
    regions = {"all": df, "south": df[df.latitude < SOUTH_MAX], "north": df[df.latitude >= NORTH_MIN]}
    for reg, d in regions.items():
        for b, g in d.groupby("bin"):
            if b < 0 or b >= BINS.size - 1:
                continue
            r = {"region": reg, "depth_bg_m": f"{BINS[b]}-{BINS[b + 1]}"}
            for v in ("vp", "vs"):
                for m in MODELS:
                    lr = np.log(g[v] / g[f"{v}_{m}"])
                    lr = lr[np.isfinite(lr)]
                    r[f"n_{v}_{m}"] = int(lr.size)
                    r[f"ln_{v}_ulberg_over_{m}"] = float(lr.mean()) if lr.size else np.nan
            k = np.isfinite(g.vp_matched) & np.isfinite(g.vs_matched)
            r["vpvs_ulberg_matched"] = (
                float(np.median(g.vp_matched[k] / g.vs_matched[k])) if k.any() else np.nan
            )
            for m in ("regional", "fused_uncal", "fused_v2"):
                q = g[f"vp_{m}"] / g[f"vs_{m}"]
                r[f"vpvs_{m}"] = float(np.nanmedian(q[k])) if k.any() else np.nan
            rows.append(r)
    return pd.DataFrame(rows)


def figure(tab: pd.DataFrame, path):
    # printed at the text width (6.5 in) with every text at 11 pt
    rc = {
        "font.size": 11,
        "axes.titlesize": 11,
        "axes.titleweight": "bold",
        "axes.titlelocation": "left",
        "savefig.bbox": "standard",
    }
    with plt.rc_context(rc):
        _figure(tab, path)


def _figure(tab: pd.DataFrame, path):
    from matplotlib.lines import Line2D

    a, b = (v / 1e3 for v in load_domain().cfg["fusion"]["regional_blend_m"])
    reg_lab = f"CVM v1.7 / CRESCENT, blended {a:g}-{b:g} km"
    styles = {
        "regional": ("#d98c2b", reg_lab),
        "regional_bias": ("#8a5cc2", "same + S13 static bias"),
        "fused_v2": ("#2a78d6", "rainier3d"),
    }
    mid = {f"{a}-{b}": (a + b) / 2e3 for a, b in zip(BINS[:-1], BINS[1:], strict=True)}
    # printed at the text width (6.5 in) with every text at 11 pt
    rc = {
        "font.size": 11,
        "axes.titlesize": 11,
        "axes.titleweight": "bold",
        "axes.titlelocation": "left",
        "savefig.bbox": "standard",
    }
    with plt.rc_context(rc):
        fig, ax = plt.subplots(1, 3, figsize=(style.PAGE_WIDTH_IN, 6.2), sharey=True, layout="constrained")
    for j, v in enumerate(("vp", "vs")):
        ax[j].axvline(0, color="0.6", lw=0.8)
        for reg, ls in (("all", "-"), ("north", ":")):
            t = tab[tab.region == reg]
            z = t.depth_bg_m.map(mid)
            for m, (c, _) in styles.items():
                mk = "o" if ls == "-" else None
                ax[j].plot(t[f"ln_{v}_ulberg_over_{m}"], z, ls, marker=mk, ms=3, color=c)
        ax[j].set(
            xlabel=f"ln({v[0].upper()}{v[1]} iMUSH / model)", title=f"({'ab'[j]}) {v[0].upper()}{v[1:]}"
        )
    ax[0].set_xticks([0, 0.1], ["0", "0.1"])
    ax[1].set_xticks([-0.05, 0, 0.05, 0.1])
    ax[1].set_xticklabels(["-0.05", "0", "0.05", "0.1"])
    for reg, ls in (("all", "-"), ("north", ":")):
        t = tab[tab.region == reg]
        z = t.depth_bg_m.map(mid)
        ax[2].plot(t.vpvs_ulberg_matched, z, ls, color="k", marker="o", ms=3)
        ax[2].plot(t.vpvs_regional, z, ls, color="#d98c2b")
        ax[2].plot(t.vpvs_fused_v2, z, ls, color="#2a78d6", marker="o", ms=3)
    ax[2].set(xlabel="Vp/Vs (median)", title="(c) Vp/Vs", xticks=[1.7, 1.8])
    ax[0].set(ylabel="depth below ground (km)", yticks=[0, 5, 10, 15])
    ax[0].invert_yaxis()
    # one legend: colour = model, line style = region
    h = [Line2D([], [], color="k", marker="o", ms=3, label="Ulberg et al. (2020), matched")]
    h += [Line2D([], [], color=c, label=lab) for c, lab in styles.values()]
    h += [
        Line2D([], [], color="0.3", label="whole box"),
        Line2D([], [], color="0.3", ls=":", label="north of 46.75\N{DEGREE SIGN} N"),
    ]
    h += [Line2D([], [], lw=0, label="")] * 2  # fill the second column below the line styles
    fig.legend(handles=h, loc="outside lower center", ncol=2, frameon=False, fontsize=11)
    style.save(fig, path, dpi=200)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--figures-only",
        action="store_true",
        help="redraw from outputs/model_comparison/ulberg2020_by_depth.csv",
    )
    a = ap.parse_args()
    dom = load_domain()
    out = dom.path("outputs") / "model_comparison"
    figs = [
        REPO / "docs" / "joint_calibration" / "fig5_imush_comparison.png",
        REPO / "docs" / "paper" / "figures" / "fig13_imush.png",
    ]
    if a.figures_only:
        tab = pd.read_csv(out / "ulberg2020_by_depth.csv")
        for f in figs:
            figure(tab, f)
        return
    df = ulberg_nodes(dom)
    trees = {p: read_tree(REPO / p) for p in {p for p, _ in MODELS.values()}}  # each file read once
    surf = trees["data/processed/model.zarr"]["surface"].to_dataset()["elevation"]
    g = surf.interp(x=xr.DataArray(df.x.values, dims="p"), y=xr.DataArray(df.y.values, dims="p")).values
    df["depth_bg"] = g - df.z.values
    df = df[df.depth_bg > 0].reset_index(drop=True)
    for m, (p, pat) in MODELS.items():
        for v in ("vp", "vs"):
            df[f"{v}_{m}"] = sample(trees[p], pat.format(v=v), df)
    out.mkdir(parents=True, exist_ok=True)
    tab = summarize(df)
    tab.to_csv(out / "ulberg2020_by_depth.csv", index=False)
    for f in figs:
        figure(tab, f)
    cols = ["region", "depth_bg_m"] + [c for c in tab.columns if c.startswith(("ln_", "vpvs"))]
    print(f"{len(df)} Ulberg nodes below ground in the domain")
    print(tab[cols].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
