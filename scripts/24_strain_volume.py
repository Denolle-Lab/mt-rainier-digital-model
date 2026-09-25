"""S24: strain in the model volume -> data/processed/strain_3d.zarr, outputs/gnss/strain_orientation.csv,
outputs/gnss/strain_3d_summary.json and the paper figures fig16 (WRSZ), fig17 (edifice), fig18 (orientation).

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

Usage: pixi run s24   (after S5 and S18)
"""

from __future__ import annotations

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
from rainier3d.io import store
from rainier3d.io.store import read_tree

log = logging.getLogger("s24")


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


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
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
    log.info("grid %s, %d rock cells", shape, rock.sum())

    # WRSZ strike from its epicentres
    ev = wrsz_events(events, cfg["regions"]["wrsz"]["polygon"], tf)
    strike, elong = V.strike_from_epicentres(ev[:, 0], ev[:, 1])
    log.info("WRSZ: %d epicentres, strike %.1f deg, elongation %.1f", len(ev), strike, elong)

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
    log.info("wrote %s", p)

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
    log.info(
        "WRSZ at -5 km: right-lateral shear %.1f nanostrain/yr, shortening azimuth %.0f deg",
        summary["wrsz"]["right_lateral_shear_rate_median_per_yr"] * 1e9,
        summary["wrsz"]["az_shortening_median_deg"],
    )
    log.info(
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
        log.info("figure %s", p.relative_to(REPO))


if __name__ == "__main__":
    main()
