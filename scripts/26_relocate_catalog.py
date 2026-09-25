"""S26: relocate the PNSN catalogue with NonLinLoc, in the PNSN 1D model and in the rainier3d 3D model.

Both relocations use the same picks, stations, locator and settings, so their difference isolates the velocity
model (Vp and Vp/Vs); ComCat is kept as a third reference. NonLinLoc (Lomax et al. 2000): EDT likelihood,
oct-tree search, Gaussian pick errors (0.14 s P, 0.23 s S, as in S13), topography mask (LOCTOPO_SURFACE), so
no hypocentre is placed above the ground.

Writes outputs/catalog/: catalog_relocated.csv (one row per event: ComCat, 1D and 3D locations, uncertainties,
quality), summary.json, figures; NonLinLoc inputs and outputs under outputs/catalog/nll/.

Quality: A = gap < 180 deg, >= 8 phases, 3D depth sd < 2 km; B = gap < 250 deg, >= 6 phases; C = the rest.

Usage: pixi run python scripts/26_relocate_catalog.py [--start 2023-01-01 --end 2026-01-01 --minmag 1]
"""

from __future__ import annotations

import argparse
import json
import logging

import numpy as np
import pandas as pd
import xarray as xr

from rainier3d.catalog import fetch
from rainier3d.catalog import nll as N
from rainier3d.config.domain import load_domain
from rainier3d.export import grids
from rainier3d.io.store import read_tree
from rainier3d.validate import pnsn

MODELS = ("pnsn1d", "rainier3d")


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2023-01-01")
    ap.add_argument("--end", default="2026-01-01")
    ap.add_argument("--minmag", type=float, default=1.0)
    ap.add_argument("--dx", type=float, default=500.0, help="grid spacing (m), equal in x, y and z")
    ap.add_argument(
        "--figures-only", action="store_true", help="redraw from outputs/catalog/catalog_relocated.csv"
    )
    ap.add_argument("--viewer", default="", help="viewer atlas directory: also write quakes_relocated.*")
    a = ap.parse_args()
    dom = load_domain()
    if a.figures_only:
        figures(dom, dom.path("outputs") / "catalog")
        viewer(a.viewer, dom)
        return
    tag = f"catalog_{a.start[:4]}_{int(a.end[:4]) - 1}_m{a.minmag:g}"
    cache = dom.path("raw") / "pnsn" / tag
    out = dom.path("outputs") / "catalog"
    nd = out / "nll"
    for d in ("model", "time", "loc"):
        (nd / d).mkdir(parents=True, exist_ok=True)

    # ---- picks and stations
    picks = fetch.fetch(dom, a.start, a.end, a.minmag, cache)
    st = fetch.stations(dom, picks, cache)
    picks = picks.merge(st[["net", "sta"]], on=["net", "sta"])
    n = picks.groupby("event").phase.agg(n="size", n_p=lambda s: (s == "P").sum())
    keep = n[(n.n >= 6) & (n.n_p >= 4)].index
    ev = picks.drop_duplicates("event")[["event", "origin_time", "lon", "lat", "depth_km", "mag"]].set_index(
        "event"
    )
    ev["n_picks_domain"] = n.n.reindex(ev.index).fillna(0).astype(int)
    ev["located"] = ev.index.isin(keep)
    logging.info("%d events, %d with >= 6 picks (>= 4 P) at %d domain stations", len(ev), len(keep), len(st))

    # ---- grids: 3D model and the PNSN 1D model on the same geometry; topography surface
    tree = read_tree(dom.path("processed") / "model.zarr")
    g = grids.uniform(tree, dx=a.dx, dz=a.dx, z_bot=-20000.0)
    grids.write_nll(g, nd / "model" / "rainier3d")
    zz = np.broadcast_to(g.z.values[:, None, None], g["vp"].shape)
    g1 = g.copy()
    for v, ph in (("vp", "P"), ("vs", "S")):
        g1[v] = (g[v].dims, pnsn.pnsn_1d(zz, ph).astype(np.float32))
    grids.write_nll(g1, nd / "model" / "pnsn1d")
    s = tree["surface"].to_dataset()
    topo = N.write_topo_grd(s["elevation"].values, s.x.values, s.y.values, nd / "topo_km.grd")

    # ---- NonLinLoc
    obs = N.write_obs(picks[picks.event.isin(keep)].sort_values(["event", "pick_time"]), nd / "picks.obs")
    x0, y0, x1, y1 = (v / 1e3 for v in dom.bounds)
    d = 0.5
    z0 = round(-float(g.z[0]) / 1e3 + d, 1)  # one cell below the top of the time grids
    search = {"nx": int((x1 - x0 - 2) / d), "ny": int((y1 - y0 - 2) / d), "nz": int((19.0 - z0) / d),
              "x0": x0 + 1, "y0": y0 + 1, "z0": z0, "d": d}  # fmt: skip
    for m in MODELS:
        for ph in ("P", "S"):
            done = len(list((nd / "time").glob(f"{m}.{ph}.*.time.buf"))) == len(st)
            if not done:  # travel-time grids depend only on the model and the stations
                c = N.grid2time_control(nd / "model" / m, nd / "time" / m, ph, st, nd / f"gt_{m}_{ph}.in")
                N.run("Grid2Time", c, nd / f"gt_{m}_{ph}.log")
    # the two relocations are independent: run them side by side (NLLoc is single-threaded)
    ctl = {m: N.nlloc_control(obs, nd / "time" / m, nd / "loc" / m, search, topo, nd / f"nlloc_{m}.in")
           for m in MODELS}  # fmt: skip
    n_obs = obs.read_text().count("PUBLIC_ID")

    def complete(m):  # a summary with one block per observed event is reused (NLLoc takes ~8 s per event)
        f = nd / "loc" / f"{m}.sum.grid0.loc.hyp"
        return f.exists() and f.read_text().count("END_NLLOC") == n_obs

    todo = [m for m in MODELS if not complete(m)]
    if todo:
        N.run_parallel("NLLoc", {m: ctl[m] for m in todo}, {m: nd / f"nlloc_{m}.log" for m in todo})
    res = {}
    for m in MODELS:
        r = N.read_hyp(nd / "loc" / f"{m}.sum.grid0.loc.hyp")
        logging.info("%s: %d locations (%s)", m, len(r), r.status.str.split().str[0].value_counts().to_dict())
        res[m] = r.set_index("event")

    # ---- compare
    cat = ev.copy()
    from pyproj import Transformer

    cat["x_cc"], cat["y_cc"] = Transformer.from_crs(4326, dom.crs, always_xy=True).transform(
        cat.lon.values, cat.lat.values
    )
    cat["z_cc"] = -cat.depth_km * 1e3  # ComCat depth taken as km below sea level
    for m, r in res.items():
        ok = r.status.str.startswith("LOCATED")
        r = r[ok]
        cat[f"x_{m}"], cat[f"y_{m}"], cat[f"z_{m}"] = r.x_km * 1e3, r.y_km * 1e3, -r.z_km * 1e3
        for k in ("ot", "rms", "nphs", "gap", "x_sd_km", "z_sd_km", "h_unc_max_km"):
            cat[f"{k}_{m}"] = r[k]
    ground = s["elevation"]
    for k in ("cc", *MODELS):
        gx = xr.DataArray(cat[f"x_{k}"].values, dims="e")
        gy = xr.DataArray(cat[f"y_{k}"].values, dims="e")
        cat[f"above_ground_m_{k}"] = cat[f"z_{k}"].values - ground.interp(x=gx, y=gy).values
    m3 = "rainier3d"
    cat["quality"] = np.select(
        [
            (cat[f"gap_{m3}"] < 180) & (cat[f"nphs_{m3}"] >= 8) & (cat[f"z_sd_km_{m3}"] < 2),
            (cat[f"gap_{m3}"] < 250) & (cat[f"nphs_{m3}"] >= 6),
        ],
        ["A", "B"],
        "C",
    )
    cat.loc[cat[f"x_{m3}"].isna(), "quality"] = ""
    cat.to_csv(out / "catalog_relocated.csv")

    both = cat.dropna(subset=[f"x_{m}" for m in MODELS])
    summ = {"period": [a.start, a.end], "minmag": a.minmag, "n_events": int(len(cat)),
            "n_located": {m: int(cat[f"x_{m}"].notna().sum()) for m in MODELS},
            "quality_3d": cat.quality.value_counts().to_dict(), "n_stations": int(len(st)),
            "grid_dx_m": a.dx}  # fmt: skip
    for k in ("cc", *MODELS):
        summ[f"above_ground_{k}"] = int((both[f"above_ground_m_{k}"] > 0).sum())
    for m in MODELS:
        summ[f"rms_median_s_{m}"] = float(both[f"rms_{m}"].median())
    for a_, b_ in (("cc", "pnsn1d"), ("cc", "rainier3d"), ("pnsn1d", "rainier3d")):
        dh = np.hypot(both[f"x_{b_}"] - both[f"x_{a_}"], both[f"y_{b_}"] - both[f"y_{a_}"])
        dz = -(both[f"z_{b_}"] - both[f"z_{a_}"])  # positive = deeper in b
        summ[f"shift_{a_}_to_{b_}"] = {
            "horizontal_median_m": float(dh.median()),
            "deeper_median_m": float(dz.median()),
            "deeper_p10_p90_m": [float(dz.quantile(0.1)), float(dz.quantile(0.9))],
        }
    (out / "summary.json").write_text(json.dumps(summ, indent=1))
    logging.info("\n%s", json.dumps(summ, indent=1))
    figures(dom, out)
    viewer(a.viewer, dom)


def viewer(atlas: str, dom) -> None:
    if not atlas:
        return
    from pathlib import Path

    from rainier3d.export.atlas import export_relocated

    out = dom.path("outputs") / "catalog"
    summ = json.loads((out / "summary.json").read_text()) if (out / "summary.json").exists() else {}
    meta = export_relocated(Path(atlas).expanduser(), out / "catalog_relocated.csv", dom, summ)
    logging.info("viewer: %d relocated events -> %s/quakes_relocated.*", meta["count"], atlas)


def figures(dom, out):
    """Map and sections of the three catalogues, depth shifts, and 1D -> 3D shift lines (A and B quality)."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    cat = pd.read_csv(out / "catalog_relocated.csv", index_col=0)
    q = cat[cat.quality.isin(["A", "B"])]
    tree = read_tree(dom.path("processed") / "model.zarr")
    s = tree["surface"].to_dataset()
    sx, sy = dom.summit_xy
    x0, y0 = dom.bounds[0], dom.bounds[1]
    km = lambda v, o: (v - o) / 1e3  # noqa: E731
    styles = {"cc": ("ComCat (PNSN)", "#7a7a7a"), "pnsn1d": ("NonLinLoc, PNSN 1D", "#d98c2b"),
              "rainier3d": ("NonLinLoc, rainier3d 3D", "#2a78d6")}  # fmt: skip

    fig, ax = plt.subplots(
        2, 3, figsize=(16, 10), constrained_layout=True, gridspec_kw={"height_ratios": [1.6, 1]}
    )
    el = s["elevation"]
    for j, (k, (lab, c)) in enumerate(styles.items()):
        a = ax[0, j]
        a.contour(km(el.x.values, x0), km(el.y.values, y0), el.values, levels=np.arange(500, 4400, 500),
                  colors="0.75", linewidths=0.4)  # fmt: skip
        a.scatter(km(q[f"x_{k}"], x0), km(q[f"y_{k}"], y0), s=6 + 4 * q.mag, c=c, alpha=0.7, lw=0)
        a.plot(km(sx, x0), km(sy, y0), "k^", ms=9)
        a.set(aspect="equal", title=f"{lab} ({len(q)} events, A+B)", xlabel="easting (km)")
        # W-E section through the summit, +-5 km
        b = ax[1, j]
        band = np.abs(q[f"y_{k}"] - sy) < 5000
        b.scatter(
            km(q.loc[band, f"x_{k}"], x0),
            q.loc[band, f"z_{k}"] / 1e3,
            s=6 + 4 * q.mag[band],
            c=c,
            alpha=0.7,
            lw=0,
        )
        prof = el.sel(y=sy, method="nearest")
        b.plot(km(prof.x.values, x0), prof.values / 1e3, "k", lw=1)
        above = (q.loc[band, f"above_ground_m_{k}"] > 0).sum()
        b.set(
            xlabel="easting (km)", ylim=(-20, 4.6), title=f"W-E section, summit +-5 km: {above} above ground"
        )
    ax[0, 0].set_ylabel("northing (km)")
    ax[1, 0].set_ylabel("elevation (km)")
    fig.savefig(out / "fig_catalogs.png", dpi=130)

    fig, ax = plt.subplots(1, 2, figsize=(13, 5), constrained_layout=True)
    dz = -(q.z_rainier3d - q.z_pnsn1d) / 1e3
    dzc = -(q.z_rainier3d - q.z_cc) / 1e3
    b = np.arange(-6, 6.01, 0.25)
    ax[0].hist(
        dz, bins=b, color="#2a78d6", alpha=0.7, label=f"3D - 1D (NonLinLoc), median {dz.median():+.2f} km"
    )
    ax[0].hist(dzc, bins=b, histtype="step", color="k", label=f"3D - ComCat, median {dzc.median():+.2f} km")
    ax[0].set(xlabel="depth change (km, positive = deeper in 3D)", ylabel="events", title="Depth change")
    ax[0].legend(frameon=False)
    a = ax[1]
    a.contour(km(el.x.values, x0), km(el.y.values, y0), el.values, levels=np.arange(500, 4400, 500),
              colors="0.8", linewidths=0.4)  # fmt: skip
    for r in q.itertuples():
        a.plot([km(r.x_pnsn1d, x0), km(r.x_rainier3d, x0)], [km(r.y_pnsn1d, y0), km(r.y_rainier3d, y0)], "-",
               color="#2a78d6", lw=0.7)  # fmt: skip
    a.scatter(km(q.x_rainier3d, x0), km(q.y_rainier3d, y0), s=5, c="#2a78d6")
    a.plot(km(sx, x0), km(sy, y0), "k^", ms=9)
    a.set(aspect="equal", title="Epicentre shift, 1D -> 3D (lines end at the 3D location)",
          xlabel="easting (km)",
          ylabel="northing (km)")  # fmt: skip
    fig.savefig(out / "fig_shifts.png", dpi=130)


if __name__ == "__main__":
    main()
