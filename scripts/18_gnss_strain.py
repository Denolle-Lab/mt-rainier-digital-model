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

Strain in the model volume (formerly S25; run at the end unless --no-load or --no-volume, after S5) ->
data/processed/strain_3d.zarr, outputs/gnss/strain_orientation.csv, outputs/gnss/strain_3d_summary.json
and the paper figures fig16 (WRSZ), fig17 (edifice), fig18 (orientation).

Two fields on the grid of the 3D viewer volume (500 m x 250 m, surface to 20 km below sea level), rock only:

  tectonic strain rate  the GNSS horizontal strain-rate tensor (S18 strain_grid.nc) carried down unchanged,
                        with plane stress for e_zz (rainier3d.geodesy.volume); resolved on vertical planes
                        parallel to the West Rainier Seismic Zone, whose strike is fitted to its epicentres
  edifice-load strain   the Boussinesq stress of the edifice load (S18) turned into strain with the local
                        stiffness of the velocity model; SHmax is the most compressive horizontal stress.
                        Inside the cone above the half-space (z > reference plane - 250 m) the stress is the
                        laterally confined overburden, with volumetric strain but no SHmax (load_method = 2)

The orientation table gives both shortening directions on regular grids at fixed elevations, for comparison
with shear-wave splitting fast directions.

Usage: pixi run s18 [-- --no-load | --no-volume]
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
from rainier3d.export.grids import uniform
from rainier3d.geodesy import load as LD
from rainier3d.geodesy import volume as V
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
    ap.add_argument(
        "--no-load", action="store_true", help="skip the edifice load and the volume (need model.zarr)"
    )
    ap.add_argument("--no-volume", action="store_true", help="skip the strain in the model volume")
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
    if not a.no_volume:
        strain_volume()


logv = logging.getLogger("s18.volume")


def wrsz_events(events: dict, polygon_lonlat, tf) -> np.ndarray:
    """(x, y, depth_km) of the catalogue events inside the WRSZ polygon."""
    from matplotlib.path import Path as MPath

    poly = MPath(np.array(polygon_lonlat))
    rows = [
        (*f["geometry"]["coordinates"][:2], f["properties"]["depth"])
        for f in events["features"]
        if poly.contains_point(f["geometry"]["coordinates"][:2])
    ]
    a = np.array(rows, float)
    x, y = tf.transform(a[:, 0], a[:, 1])
    return np.column_stack([x, y, a[:, 2]])


def strain_volume():
    """The strain in the model volume (formerly S25; see the module docstring)."""
    dom = load_domain()
    cfg = yaml.safe_load((REPO / "configs" / "gnss.yaml").read_text())
    vc, lc = cfg["volume"], cfg["load"]
    nu = lc["poisson"]
    tf = Transformer.from_crs(4326, dom.crs, always_xy=True)
    tree = read_tree(dom.path("processed") / "model.zarr")
    grid = xr.open_dataset(dom.path("processed") / "gnss" / "strain_grid.nc")
    events = json.loads((REPO / "web" / "atlas" / "data" / "events.geojson").read_text())

    # the viewer volume grid, rock cells only
    g = uniform(tree, dx=vc["dx_m"], dz=vc["dz_m"], z_bot=vc["z_bot_m"], variables=("vp", "vs", "rho"))
    rock = ~g["air"].values.astype(bool)
    Z, Y, X = np.meshgrid(g.z.values, g.y.values, g.x.values, indexing="ij")
    shape = rock.shape
    logv.info("grid %s, %d rock cells", shape, rock.sum())

    # WRSZ strike from its epicentres
    ev = wrsz_events(events, cfg["regions"]["wrsz"]["polygon"], tf)
    strike, elong = V.strike_from_epicentres(ev[:, 0], ev[:, 1])
    logv.info("WRSZ: %d epicentres, strike %.1f deg, elongation %.1f", len(ev), strike, elong)

    # tectonic strain rate, uniform with depth down to rate_z_bot_m
    exx, eyy, exy = V.horizontal_rate_at(grid, X[0], Y[0])
    keep = rock & (Z >= vc["rate_z_bot_m"])

    def cube(a2d):
        return np.where(keep, np.broadcast_to(a2d, shape), np.nan).astype("float32")

    ph = V.principal_horizontal(exx, eyy, exy)
    rs = V.resolved_on_strike(exx, eyy, exy, strike)
    ezz = V.plane_stress_ezz(exx, eyy, nu)
    ds = xr.Dataset(coords={"z": g.z, "y": g.y, "x": g.x})
    rate = "1/yr"
    ds["tect_areal_rate"] = (
        ("z", "y", "x"),
        cube(exx + eyy),
        {"units": rate, "long_name": "GNSS areal strain rate e_xx + e_yy"},
    )
    ds["tect_volumetric_rate"] = (
        ("z", "y", "x"),
        cube(exx + eyy + ezz),
        {"units": rate, "long_name": "volumetric strain rate, plane stress"},
    )
    ds["tect_max_shear_rate"] = (
        ("z", "y", "x"),
        cube(ph["max_shear"]),
        {"units": rate, "long_name": "maximum horizontal shear strain rate"},
    )
    ds["tect_az_shortening"] = (
        ("z", "y", "x"),
        cube(ph["az_shortening"]),
        {"units": "degrees", "long_name": "azimuth of maximum horizontal shortening"},
    )
    ds["wrsz_shear_rate"] = (
        ("z", "y", "x"),
        cube(rs["right_lateral_shear"]),
        {
            "units": rate,
            "long_name": f"right-lateral shear strain rate, vertical planes striking {strike:.1f} deg (WRSZ)",
        },
    )
    ds["wrsz_normal_rate"] = (
        ("z", "y", "x"),
        cube(rs["normal"]),
        {"units": rate, "long_name": "normal strain rate across WRSZ-parallel planes"},
    )

    # edifice-load strain with the local stiffness
    loads = LD.edifice_loads(tree["surface"].to_dataset(), load_cell_m=lc["load_cell_m"], rho=lc["rho_kgm3"])
    pts = np.column_stack([X[rock], Y[rock], Z[rock]])
    st = LD.stress_at(pts, loads, nu=nu, min_depth_m=lc["min_depth_m"])
    # edifice interior above the half-space (the cone above z_ref - min_depth): laterally confined overburden,
    # s_zz = -rho g d (d below the local ground), s_h = nu / (1 - nu) s_zz; horizontal stress is isotropic
    # there, so it defines no SHmax
    elev = tree["surface"].to_dataset()["elevation"].interp(x=g.x, y=g.y, method="linear").values
    interior = ~np.isfinite(st[:, 0])
    d = np.clip(np.broadcast_to(elev, shape)[rock][interior] - pts[interior, 2], 0, None)
    szz = -lc["rho_kgm3"] * LD.G * d
    st[interior] = 0.0
    st[interior, 2] = szz
    st[interior, 0] = st[interior, 1] = nu / (1 - nu) * szz
    method = np.zeros(len(pts), "uint8")
    method[~interior], method[interior] = 1, 2
    eps = V.compliance(st, g["vp"].values[rock], g["vs"].values[rock], g["rho"].values[rock])

    def put(v):
        out = np.full(shape, np.nan, "float32")
        out[rock] = v
        return out

    hp = V.principal_horizontal(eps[:, 0], eps[:, 1], eps[:, 3])
    hp["max_shear"] = np.where(interior, np.nan, hp["max_shear"])  # isotropic horizontal stress: undefined
    for i, c in enumerate(("xx", "yy", "zz", "xy", "xz", "yz")):  # full tensor, for sections and splitting
        ds[f"load_e{c}"] = (
            ("z", "y", "x"),
            put(eps[:, i]),
            {"units": "1", "long_name": f"edifice-load strain e_{c}"},
        )
    ds["load_volumetric"] = (
        ("z", "y", "x"),
        put(eps[:, :3].sum(1)),
        {"units": "1", "long_name": "volumetric strain from the edifice load"},
    )
    ds["load_areal"] = (
        ("z", "y", "x"),
        put(eps[:, 0] + eps[:, 1]),
        {"units": "1", "long_name": "horizontal areal strain from the edifice load"},
    )
    ds["load_max_shear_h"] = (
        ("z", "y", "x"),
        put(hp["max_shear"]),
        {"units": "1", "long_name": "maximum horizontal shear strain from the edifice load"},
    )
    lm = np.zeros(shape, "uint8")
    lm[rock] = method
    ds["load_method"] = (
        ("z", "y", "x"),
        lm,
        {"long_name": "1 half-space, 2 confined overburden (edifice interior), 0 air"},
    )
    ds["load_shmax_az"] = (
        ("z", "y", "x"),
        put(np.where(interior, np.nan, V.shmax_azimuth(st[:, 0], st[:, 1], st[:, 3]))),
        {
            "units": "degrees",
            "long_name": "azimuth of the most compressive horizontal stress (SHmax) from the edifice load",
        },
    )
    ds["load_mean_stress"] = (
        ("z", "y", "x"),
        put(st[:, :3].sum(1) / 3),
        {"units": "Pa", "long_name": "mean stress from the edifice load, tension positive"},
    )
    ds.attrs = {
        "crs": dom.crs,
        "wrsz_strike_deg": strike,
        "wrsz_elongation": elong,
        "wrsz_events": int(len(ev)),
        "poisson": nu,
        "load_reference_plane_m": loads[3],
        "assumptions": "tectonic: GNSS horizontal strain rate uniform with depth, plane stress; load: "
        "homogeneous "
        "half-space stress, local isotropic stiffness from Vp, Vs, rho",
        "gnss_as_of": grid.attrs.get("as_of", ""),
    }
    p = store.write(ds, dom.path("processed") / "strain_3d.zarr")
    logv.info("wrote %s", p)

    # orientation grids for shear-wave splitting, and the summary
    sx, sy = dom.summit_xy
    inv = Transformer.from_crs(dom.crs, 4326, always_xy=True)
    rows = []
    for zm in vc["bars"]["elevations_m"]:
        lev = ds.sel(z=zm, method="nearest")
        for kind, sp in (
            ("tectonic", vc["bars"]["tectonic_spacing_m"]),
            ("load", vc["bars"]["load_spacing_m"]),
        ):
            step = max(1, int(round(sp / vc["dx_m"])))
            sub = lev.isel(x=slice(step // 2, None, step), y=slice(step // 2, None, step))
            xx, yy = np.meshgrid(sub.x.values, sub.y.values)
            for i, j in zip(
                *np.nonzero(
                    np.isfinite(sub["load_volumetric" if kind == "load" else "tect_max_shear_rate"].values)
                ),
                strict=True,
            ):
                x, y = xx[i, j], yy[i, j]
                if kind == "load" and np.hypot(x - sx, y - sy) > vc["bars"]["load_radius_m"]:
                    continue
                lon, lat = inv.transform(x, y)
                r = {"kind": kind, "z_m": float(lev.z), "x": x, "y": y, "lon": lon, "lat": lat}
                if kind == "tectonic":
                    r |= {
                        "azimuth": float(sub.tect_az_shortening[i, j]),
                        "magnitude": float(sub.tect_max_shear_rate[i, j]),
                        "value": float(sub.wrsz_shear_rate[i, j]),
                    }
                else:
                    r |= {
                        "azimuth": float(sub.load_shmax_az[i, j]),
                        "magnitude": float(sub.load_max_shear_h[i, j]),
                        "value": float(sub.load_volumetric[i, j]),
                    }
                rows.append(r)
    bars = pd.DataFrame(rows).dropna(subset=["azimuth"])  # the edifice interior has no SHmax
    odir = dom.path("outputs") / "gnss"
    bars.to_csv(odir / "strain_orientation.csv", index=False, float_format="%.6g")

    def at(var, x, y, z):
        return float(ds[var].sel(x=x, y=y, z=z, method="nearest"))

    exm, eym = tf.transform(*np.array(cfg["regions"]["wrsz"]["polygon"]).T)
    inside = (ds.x >= min(exm)) & (ds.x <= max(exm)) & (ds.y >= min(eym)) & (ds.y <= max(eym))
    w5 = ds.sel(z=-5000, method="nearest").where(inside)
    summit_col = ds.sel(x=sx, y=sy, method="nearest")
    summary = {
        "wrsz": {
            "strike_deg": strike,
            "elongation": elong,
            "events": int(len(ev)),
            "right_lateral_shear_rate_median_per_yr": float(w5.wrsz_shear_rate.median()),
            "normal_rate_median_per_yr": float(w5.wrsz_normal_rate.median()),
            "max_shear_rate_median_per_yr": float(w5.tect_max_shear_rate.median()),
            "az_shortening_median_deg": float(np.nanmedian(w5.tect_az_shortening.values)),
            "load_shmax_az_median_deg_at_-5km": float(np.nanmedian(w5.load_shmax_az.values)),
            "load_max_shear_h_median_at_-5km": float(w5.load_max_shear_h.median()),
        },
        "summit_column": {
            str(int(z)): {
                "load_volumetric": at("load_volumetric", sx, sy, z),
                "load_areal": at("load_areal", sx, sy, z),
                "load_max_shear_h": at("load_max_shear_h", sx, sy, z),
                "tect_areal_rate_per_yr": at("tect_areal_rate", sx, sy, z),
            }
            for z in (1500, 1000, 500, 0, -2000, -5000, -11500)
        },
        "edifice_above_sea_level": {  # summit column, 0 m to the surface
            "load_volumetric_min": float(summit_col.load_volumetric.where(summit_col.z >= 0).min()),
            "load_volumetric_at_2500m": at("load_volumetric", sx, sy, 2500),
            "half_space_top_m": float(loads[3] - lc["min_depth_m"]),
        },
        "orientation_rows": int(len(bars)),
    }
    (odir / "strain_3d_summary.json").write_text(json.dumps(summary, indent=1))
    logv.info(
        "WRSZ at -5 km: right-lateral shear %.1f nanostrain/yr, shortening azimuth %.0f deg",
        summary["wrsz"]["right_lateral_shear_rate_median_per_yr"] * 1e9,
        summary["wrsz"]["az_shortening_median_deg"],
    )
    logv.info(
        "wrote %s (%d rows), %s", odir / "strain_orientation.csv", len(bars), odir / "strain_3d_summary.json"
    )

    # paper figures
    from rainier3d.report import figures as F

    fig = REPO / "docs" / "paper" / "figures"
    poly = np.column_stack(tf.transform(*np.array(cfg["regions"]["wrsz"]["polygon"]).T))
    for p in (
        F.fig_strain_wrsz(ds, dom, ev, poly, fig / "fig16_strain_wrsz.png", vc["bars"]["tectonic_spacing_m"]),
        F.fig_strain_edifice(ds, dom, tree, events, vc["summit_events"], fig / "fig17_strain_edifice.png"),
        F.fig_strain_bars_depth(ds, dom, fig / "fig18_strain_orientation.png"),
    ):
        logv.info("figure %s", p.relative_to(REPO))


if __name__ == "__main__":
    main()
