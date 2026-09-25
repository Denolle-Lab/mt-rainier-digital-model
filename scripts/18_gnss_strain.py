"""S18: GNSS velocities, surface strain, and stress from the edifice load.

  outputs/gnss/velocities.csv           MIDAS velocities per site (PANGA first, UNR where PANGA has no site),
                                        frame-aligned, with QC flags
  outputs/gnss/strain_<region>.csv      daily uniform strain of the stations around each region
                                        (configs/gnss.yaml), with and without the secular trend
  outputs/gnss/summary.json             frame fit, regional secular rates, QC flags, edifice-load totals
  data/processed/gnss/strain_grid.nc    secular strain-rate components and the annual (seasonal) areal-strain
                                        amplitude/phase
  data/processed/edifice_load.zarr      stress from the edifice weight on the model levels L1-L3 (Boussinesq
                                        half-space)

The as_of date is the one S17 used (data/processed/gnss/fetch.json). --no-load skips the edifice load, which
needs the local model.zarr and does not change with the GNSS data (the weekly refresh runs without it).

Usage: pixi run s18 [-- --no-load]
"""

from __future__ import annotations

import argparse
import json
import logging

import numpy as np
import pandas as pd
import xarray as xr
import yaml
from pyproj import Transformer

from rainier3d.config.domain import REPO, load_domain
from rainier3d.geodesy import load as LD
from rainier3d.geodesy.strain import COMPONENTS, strain_grid, uniform_strain
from rainier3d.geodesy.velocity import midas, trajectory
from rainier3d.io import store
from rainier3d.io.store import read_tree

log = logging.getLogger("s18")
T_REF = 2015.0


def site_models(daily, steps, min_years):
    """MIDAS velocities and trajectory fits per (site, archive) series."""
    rows, series = [], {}
    for (site, arch), d in daily.groupby(["site", "archive"]):
        d = d.sort_values("decyear")
        t = d.decyear.to_numpy()
        if t.size < 365 or t[-1] - t[0] < min_years:
            continue
        st = steps.loc[steps.site == site, "decyear"].to_numpy()
        r = {
            "site": site,
            "archive": arch,
            "lat": d.lat.iloc[-1],
            "lon": d.lon.iloc[-1],
            "start": t[0],
            "end": t[-1],
            "days": t.size,
        }
        corr = {}
        for k in ("e", "n", "u"):
            v, s, npair = midas(t, d[k].to_numpy(), steps=st)
            f = trajectory(t, d[k].to_numpy(), steps=st, t_ref=T_REF)
            r |= {
                f"v{k}": v,
                f"s{k}": max(s, 2e-4),
                f"ann_s_{k}": f["ann_s"],
                f"ann_c_{k}": f["ann_c"],
                f"rms_{k}": f["rms"],
                f"b_{k}": f["b"],
            }
            corr[k] = f["corrected"]
            corr[f"{k}_res"] = f["residual"]
        rows.append(r)
        series[(site, arch)] = pd.DataFrame({"decyear": t, "date": d.date.to_numpy(), **corr})
    return pd.DataFrame(rows), series


def align_frames(vel, xy):
    """Fit UNR - PANGA horizontal velocity differences on shared sites (translation + rotation, local plane);
    return the correction to subtract from UNR velocities at any point, and the fit residual RMS (m/yr)."""
    p = vel[vel.archive == "panga"].set_index("site")
    u = vel[vel.archive == "unr"].set_index("site")
    shared = sorted(set(p.index) & set(u.index))
    if len(shared) < 3:
        return (lambda x, y: (0.0, 0.0)), np.nan, 0
    X = np.array([xy[s] for s in shared])
    x0 = X.mean(0)
    dx, dy = (X - x0).T
    dv = np.r_[u.loc[shared, "ve"] - p.loc[shared, "ve"], u.loc[shared, "vn"] - p.loc[shared, "vn"]]
    n = len(shared)
    A = np.zeros((2 * n, 3))
    A[:n, 0], A[n:, 1] = 1, 1
    A[:n, 2], A[n:, 2] = -dy, dx
    c, *_ = np.linalg.lstsq(A, dv, rcond=None)
    rms = float(np.sqrt(np.mean((dv - A @ c) ** 2)))
    return (lambda x, y: (c[0] - c[2] * (y - x0[1]), c[1] + c[2] * (x - x0[0]))), rms, n


def region_sites(sel, cfg_r, tf):
    x, y = tf.transform(sel.lon.to_numpy(), sel.lat.to_numpy())
    if "center" in cfg_r:
        cx, cy = tf.transform(*cfg_r["center"])
        return np.hypot(x - cx, y - cy) <= cfg_r["radius_km"] * 1e3
    from shapely.geometry import Point, Polygon

    poly = Polygon([tf.transform(*p) for p in cfg_r["polygon"]]).buffer(cfg_r.get("buffer_km", 0) * 1e3)
    return np.array([poly.contains(Point(a, b)) for a, b in zip(x, y, strict=True)])


def daily_strain(sel, series, xy, min_sites=4):
    """Uniform strain each day: from step-corrected, epoch-referenced positions (total), with each site's
    secular trend removed (detrended), and from trajectory residuals (transient: trend, seasonal terms and
    steps removed)."""
    frames = []
    for r in sel.itertuples():
        s = series[(r.site, r.archive)]
        frames.append(
            pd.DataFrame(
                {
                    "date": s.date,
                    "site": r.site,
                    "e": s.e,
                    "n": s.n,
                    "e_dt": s.e - r.b_e * (s.decyear - T_REF),
                    "n_dt": s.n - r.b_n * (s.decyear - T_REF),
                    "e_res": s.e_res,
                    "n_res": s.n_res,
                }
            )
        )
    d = pd.concat(frames)
    out = []
    for date, g in d.groupby("date"):
        if len(g) < min_sites:
            continue
        P = np.array([xy[s] for s in g.site])
        sig = np.full((len(g), 2), 2e-3)
        a = uniform_strain(P, g[["e", "n"]].to_numpy(), sig)
        b = uniform_strain(P, g[["e_dt", "n_dt"]].to_numpy(), sig)
        # transient: residuals of each site's trajectory model (zero mean), robust to stations joining/leaving
        c = uniform_strain(P, g[["e_res", "n_res"]].to_numpy(), sig)
        out.append(
            {
                "date": date,
                "n_sites": len(g),
                **{k: float(a[k]) for k in ("dilatation", "max_shear", "rotation")},
                **{f"{k}_detrended": float(b[k]) for k in ("dilatation", "max_shear")},
                **{f"{k}_transient": float(c[k]) for k in ("dilatation", "max_shear")},
                "dilatation_sigma": a["dilatation_sigma"],
            }
        )
    return pd.DataFrame(out)


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-load", action="store_true", help="skip the edifice load (needs model.zarr)")
    a = ap.parse_args()
    dom = load_domain()
    cfg = yaml.safe_load((REPO / "configs" / "gnss.yaml").read_text())
    gdir, odir = dom.path("processed") / "gnss", dom.path("outputs") / "gnss"
    fetched = json.loads((gdir / "fetch.json").read_text()) if (gdir / "fetch.json").exists() else {}
    as_of = fetched.get("as_of", cfg["as_of"])
    odir.mkdir(parents=True, exist_ok=True)
    daily = pd.read_parquet(gdir / "daily.parquet")
    steps = pd.read_csv(gdir / "steps.csv")
    sites = pd.read_csv(gdir / "sites.csv")
    daily = daily.drop(columns=["lat", "lon"]).merge(
        sites[["site", "lat", "lon"]].drop_duplicates("site"), on="site"
    )
    tf = Transformer.from_crs(4326, dom.crs, always_xy=True)

    vel, series = site_models(daily, steps, cfg["min_years"])
    xy = {r.site: np.array(tf.transform(r.lon, r.lat)) for r in vel.itertuples()}
    corr, rms, nshared = align_frames(vel, xy)
    log.info("UNR -> PANGA frame: %d shared sites, residual RMS %.2f mm/yr", nshared, rms * 1e3)
    # one series per site: PANGA where it exists, else UNR corrected into the PANGA frame
    use = vel[(vel.archive == "panga") | ~vel.site.isin(vel.loc[vel.archive == "panga", "site"])].copy()
    for i, r in use[use.archive == "unr"].iterrows():
        cx, cy = corr(*xy[r.site])
        use.loc[i, ["ve", "vn"]] = [r.ve - cx, r.vn - cy]
        s = series[(r.site, r.archive)]
        s["e"] -= cx * (s.decyear - T_REF)
        s["n"] -= cy * (s.decyear - T_REF)
        use.loc[i, ["b_e", "b_n"]] = [r.b_e - cx, r.b_n - cy]
    # quality control: inconsistent with PANGA's published velocity, or far from the neighbours' median
    qc = cfg["qc"]
    from rainier3d.geodesy.archive import parse_panga_velocities

    raw = dom.path("raw") / "gnss" / "panga"
    pv = parse_panga_velocities(raw / "panga_nam20_hvel.xml").set_index("site")
    use["flag"] = ""
    for i, r in use.iterrows():
        if r.archive == "panga" and r.site in pv.index:
            d = np.hypot(r.ve * 1e3 - pv.loc[r.site, "ve"], r.vn * 1e3 - pv.loc[r.site, "vn"])
            if d > qc["max_diff_from_panga_mm_yr"]:
                use.loc[i, "flag"] = f"inconsistent with PANGA velocity ({d:.1f} mm/yr)"
    P0 = np.array([xy[s] for s in use.site])
    for i, (k, r) in enumerate(use.iterrows()):
        dist = np.hypot(*(P0 - P0[i]).T)
        nb = (dist > 0) & (dist < qc["neighbour_radius_km"] * 1e3)
        if nb.sum() >= 3:
            d = np.hypot(r.ve - np.median(use.ve[nb]), r.vn - np.median(use.vn[nb])) * 1e3
            if d > qc["max_diff_from_neighbours_mm_yr"]:
                use.loc[k, "flag"] = (use.loc[k, "flag"] + "; " if use.loc[k, "flag"] else "") + (
                    f"differs from neighbours ({d:.1f} mm/yr)"
                )
    flagged = use[use.flag != ""]
    log.info("QC flagged %d sites: %s", len(flagged), ", ".join(flagged.site))
    use.to_csv(odir / "velocities.csv", index=False)
    use_all, use = use, use[use.flag == ""].copy()
    log.info(
        "velocities: %d sites (%d PANGA, %d UNR)",
        len(use),
        (use.archive == "panga").sum(),
        (use.archive == "unr").sum(),
    )

    # strain grid over the network box: secular (MIDAS) and annual (sin/cos coefficient fields)
    w, s_, e, n = cfg["network_bbox"]
    gx0, gy0 = tf.transform(w, s_)
    gx1, gy1 = tf.transform(e, n)
    sp = cfg["strain"]["grid_spacing_m"]
    gx, gy = np.arange(gx0, gx1, sp), np.arange(gy0, gy1, sp)
    G = np.array(np.meshgrid(gx, gy)).reshape(2, -1).T
    P = np.array([xy[s] for s in use.site])
    sc = cfg["strain"]
    kw = dict(min_weight=sc["min_weight"], scales=tuple(sc["scales_m"]), min_stations=sc["min_stations"])
    sec, scale = strain_grid(P, use[["ve", "vn"]].to_numpy(), use[["se", "sn"]].to_numpy(), G, **kw)
    sig_ann = np.full((len(use), 2), 5e-4)
    ss, _ = strain_grid(P, use[["ann_s_e", "ann_s_n"]].to_numpy(), sig_ann, G, **kw)
    cc, _ = strain_grid(P, use[["ann_c_e", "ann_c_n"]].to_numpy(), sig_ann, G, **kw)
    shape = (gy.size, gx.size)
    ds = xr.Dataset(coords={"y": gy, "x": gx})
    for k in (*COMPONENTS, "dilatation_sigma"):
        ds[k] = (("y", "x"), sec[k].reshape(shape), {"units": "1/yr" if k != "azimuth" else "degrees"})
    ds["scale_m"] = (("y", "x"), scale.reshape(shape))
    ds["annual_dilatation_amplitude"] = (
        ("y", "x"),
        np.hypot(ss["dilatation"], cc["dilatation"]).reshape(shape),
    )
    ds["annual_dilatation_peak_doy"] = (
        ("y", "x"),
        (np.mod(np.degrees(np.arctan2(ss["dilatation"], cc["dilatation"])), 360) / 360 * 365.25).reshape(
            shape
        ),
    )
    ds.attrs = {
        "crs": dom.crs,
        "method": "MIDAS velocities; adaptive Gaussian-weighted velocity-gradient fit",
        "archives": "PANGA (CWU) primary, UNR (NGL) where PANGA has no site; UNR aligned to PANGA by a "
        "translation + rotation fit on shared sites",
        "as_of": as_of,
        "frame_fit_rms_m_per_yr": rms,
    }
    ds.to_netcdf(gdir / "strain_grid.nc")
    sx, sy = dom.summit_xy
    at = ds.sel(x=sx, y=sy, method="nearest")
    log.info(
        "secular strain at the summit cell: dilatation %.1f, max shear %.1f nanostrain/yr (scale %.0f km)",
        float(at.dilatation) * 1e9,
        float(at.max_shear) * 1e9,
        float(at.scale_m) / 1e3,
    )

    # daily strain of the station groups around each region
    summary = {
        "as_of": as_of,
        "last_day": fetched.get("last_day"),
        "frame_fit": {"shared_sites": nshared, "rms_mm_per_yr": rms * 1e3},
        "regions": {},
        "qc_flagged": dict(zip(flagged.site, flagged.flag, strict=True)),
    }
    runs = [(k, rc, use) for k, rc in cfg["regions"].items()] + [
        ("edifice_all", cfg["regions"]["edifice"], use_all)
    ]
    for key, rc, pool in runs:
        m = region_sites(pool, rc, tf)
        sel = pool[m]
        ts = daily_strain(sel, series, xy)
        ts.to_csv(odir / f"strain_{key}.csv", index=False)
        # secular rate from the MIDAS velocities of the same sites (uniform strain), not from the daily
        # series, whose station set changes over time
        U = uniform_strain(
            np.array([xy[x] for x in sel.site]), sel[["ve", "vn"]].to_numpy(), sel[["se", "sn"]].to_numpy()
        )
        rate = float(U["dilatation"])
        summary["regions"][key] = {
            "sites": sorted(sel.site),
            "days": len(ts),
            "secular_dilatation_per_yr": rate,
            "secular_dilatation_sigma_per_yr": float(U["dilatation_sigma"]),
            "secular_max_shear_per_yr": float(U["max_shear"]),
            "e1_azimuth_deg": float(U["azimuth"]),
        }
        log.info(
            "%s: %d sites, %d days, secular dilatation %.1f +- %.1f, max shear %.1f nanostrain/yr",
            key,
            len(sel),
            len(ts),
            rate * 1e9,
            U["dilatation_sigma"] * 1e9,
            U["max_shear"] * 1e9,
        )

    if a.no_load:
        (odir / "summary.json").write_text(json.dumps(summary, indent=1, default=float))
        log.info("wrote %s, %s (edifice load skipped)", gdir / "strain_grid.nc", odir / "summary.json")
        return

    # edifice load on the model levels (surface and level grids are geometry only: calibration-independent)
    lc = cfg["load"]
    tree = read_tree(dom.path("processed") / "model.zarr")
    loads = LD.edifice_loads(tree["surface"].to_dataset(), load_cell_m=lc["load_cell_m"], rho=lc["rho_kgm3"])
    nodes = {}
    for lev in ("L1", "L2", "L3"):
        L = tree[lev].to_dataset()
        Z, Y, X = np.meshgrid(L.z.values, L.y.values, L.x.values, indexing="ij")
        pts = np.c_[X.ravel(), Y.ravel(), Z.ravel()]
        st = LD.stress_at(pts, loads, nu=lc["poisson"], min_depth_m=lc["min_depth_m"])
        inv = LD.invariants(st)
        dsl = xr.Dataset(coords={"z": L.z, "y": L.y, "x": L.x})
        for i, k in enumerate(("sxx", "syy", "szz", "sxy", "sxz", "syz")):
            dsl[k] = (("z", "y", "x"), st[:, i].reshape(Z.shape).astype("float32"), {"units": "Pa"})
        for k, v in inv.items():
            dsl[f"stress_{k}"] = (("z", "y", "x"), v.reshape(Z.shape).astype("float32"), {"units": "Pa"})
        nodes[f"/{lev}"] = dsl
    lt = xr.DataTree.from_dict(nodes)
    lt.attrs = {
        "method": "Boussinesq point loads on an elastic half-space (rainier3d.geodesy.load)",
        "rho": lc["rho_kgm3"],
        "poisson": lc["poisson"],
        "reference_plane_m": loads[3],
        "edifice_weight_N": float(loads[2].sum()),
    }
    store.write(lt, dom.path("processed") / "edifice_load.zarr")
    summary["edifice_load"] = {
        "reference_plane_m": loads[3],
        "weight_N": float(loads[2].sum()),
        "load_cells": int(len(loads[0])),
    }
    (odir / "summary.json").write_text(json.dumps(summary, indent=1, default=float))
    log.info("wrote %s, %s, edifice_load.zarr", gdir / "strain_grid.nc", odir / "summary.json")


if __name__ == "__main__":
    main()
