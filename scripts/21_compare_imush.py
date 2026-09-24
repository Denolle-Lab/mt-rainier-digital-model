"""S21: compare rainier3d and its regional baseline with the iMUSH local-earthquake tomography
(Ulberg et al. 2020).

A test of the S13 static bias on CVM v1.7 / CRESCENT: at every Ulberg node inside the domain that the EMC
file leaves unmasked (checkerboard recovery for 20 km features), sample
  regional      CVM v1.7 / CRESCENT as distributed        (vp_regional, vs_regional of model_nocal.zarr)
  regional_bias the same with the S13 static bias          (vp_regional, vs_regional of model_v2.zarr)
  fused_uncal   the fused model before calibration          (vp, vs of model_nocal.zarr)
  fused_v2      the fused model after S13 v2                (vp, vs of model_v2.zarr)
and report ln(V_Ulberg / V_model) by depth below the ground, for the whole domain and for its south
(< 46.65 N, inside the iMUSH array) and north (>= 46.75 N, Rainier). Vp/Vs is compared with Ulberg's
'matched' Vp and Vs
(the same ~3600 arrivals for both phases).

Ulberg depth is taken as km below sea level: the EMC page and figure captions say so, although the netCDF
long_name says "depth below earth surface" (the axis starts at -5 km, which only sea level allows).

Writes outputs/model_comparison/ulberg2020_by_depth.csv and docs/joint_calibration/fig5_imush_comparison.png.
Usage: pixi run python scripts/21_compare_imush.py
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr
from pyproj import Transformer

from rainier3d.config.domain import REPO, load_domain
from rainier3d.io.store import read_tree

ULBERG = REPO / "data" / "raw" / "emc" / "iMUSH-localEQ-Ulberg-2020.r0.0-n4c.nc"
URL = (
    "https://data.earthscope.org/archive/seismology/products/emc/netcdf/iMUSH-localEQ-Ulberg-2020.r0.0-n4c.nc"
)
BINS = np.array([0, 1000, 2000, 3000, 4000, 6000, 8000, 11000, 15000, 20000])
SOUTH_MAX, NORTH_MIN = 46.65, 46.75
MODELS = {
    "regional": ("data/processed/model_nocal.zarr", "{v}_regional"),
    "regional_bias": ("data/processed/model_v2.zarr", "{v}_regional"),
    "fused_uncal": ("data/processed/model_nocal.zarr", "{v}"),
    "fused_v2": ("data/processed/model_v2.zarr", "{v}"),
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
    styles = {
        "regional": ("#d98c2b", "CVM v1.7 / CRESCENT"),
        "regional_bias": ("#8a5cc2", "same + S13 static bias"),
        "fused_v2": ("#2a78d6", "rainier3d (S13 v2)"),
    }
    mid = {f"{a}-{b}": (a + b) / 2e3 for a, b in zip(BINS[:-1], BINS[1:], strict=True)}
    fig, ax = plt.subplots(1, 3, figsize=(12, 5.2), sharey=True, constrained_layout=True)
    for j, v in enumerate(("vp", "vs")):
        ax[j].axvline(0, color="0.6", lw=0.8)
        for reg, ls in (("all", "-"), ("north", ":")):
            t = tab[tab.region == reg]
            z = t.depth_bg_m.map(mid)
            for m, (c, lab) in styles.items():
                lab_r = f"{lab}{'' if reg == 'all' else ', north'}"
                mk = "o" if ls == "-" else None
                ax[j].plot(t[f"ln_{v}_ulberg_over_{m}"], z, ls, marker=mk, ms=3, color=c, label=lab_r)
        ax[j].set(
            xlabel=f"ln({v.upper()[0]}{v[1]} Ulberg / model)", title=f"({'ab'[j]}) {v[0].upper()}{v[1:]}"
        )
    for reg, ls in (("all", "-"), ("north", ":")):
        t = tab[tab.region == reg]
        z = t.depth_bg_m.map(mid)
        sfx = "" if reg == "all" else ", north"
        ax[2].plot(
            t.vpvs_ulberg_matched, z, ls, color="k", marker="o", ms=3, label=f"Ulberg 2020, matched{sfx}"
        )
        ax[2].plot(t.vpvs_regional, z, ls, color="#d98c2b", label=f"CVM v1.7 / CRESCENT{sfx}")
        ax[2].plot(
            t.vpvs_fused_v2, z, ls, color="#2a78d6", marker="o", ms=3, label=f"rainier3d (S13 v2){sfx}"
        )
    ax[2].set(xlabel="Vp/Vs (median, matched nodes)", title="(c) Vp/Vs")
    ax[0].set_ylabel("depth below ground (km)")
    ax[0].invert_yaxis()
    ax[0].legend(frameon=False, fontsize=7.5)
    ax[2].legend(frameon=False, fontsize=7.5)
    fig.savefig(path, dpi=160)


def main():
    dom = load_domain()
    df = ulberg_nodes(dom)
    trees = {p: read_tree(REPO / p) for p, _ in MODELS.values()}
    surf = trees["data/processed/model_v2.zarr"]["surface"].to_dataset()["elevation"]
    g = surf.interp(x=xr.DataArray(df.x.values, dims="p"), y=xr.DataArray(df.y.values, dims="p")).values
    df["depth_bg"] = g - df.z.values
    df = df[df.depth_bg > 0].reset_index(drop=True)
    for m, (p, pat) in MODELS.items():
        for v in ("vp", "vs"):
            df[f"{v}_{m}"] = sample(trees[p], pat.format(v=v), df)
    out = dom.path("outputs") / "model_comparison"
    out.mkdir(parents=True, exist_ok=True)
    tab = summarize(df)
    tab.to_csv(out / "ulberg2020_by_depth.csv", index=False)
    figure(tab, REPO / "docs" / "joint_calibration" / "fig5_imush_comparison.png")
    figure(tab, REPO / "docs" / "report" / "figures" / "fig13_imush.png")
    cols = ["region", "depth_bg_m"] + [c for c in tab.columns if c.startswith(("ln_", "vpvs"))]
    print(f"{len(df)} Ulberg nodes below ground in the domain")
    print(tab[cols].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
