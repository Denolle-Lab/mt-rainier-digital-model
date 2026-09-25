"""S22: near-surface hydrothermal alteration from the helicopter EM survey of Finn et al. (2001)
-> data/processed/alteration_finn2001.zarr (maps on the model surface grid, read by S3),
   outputs/grids/rainier3d_alteration_finn2001.nc (3D alteration for download), docs/alteration/ figures.

Survey: Rystrom, Finn & Deszcz-Pan (2000), USGS OFR 00-027, downloaded to data/raw/rainier_aerogeophysics/.
Method: rainier3d.alteration.finn2001; thresholds in configs/units.yaml (geometry.alteration.finn_2001).
Then rerun S3, S4, S5 (and S9, S11) to carry the field into the velocity model, the exports and the viewer.

Usage: pixi run s22
"""

from __future__ import annotations

import json
import logging

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr

from rainier3d.alteration import aerogeophysics as A
from rainier3d.alteration import finn2001 as F
from rainier3d.config.domain import REPO, load_domain
from rainier3d.io.store import read_tree, write
from rainier3d.petro.table import units_config

DZ_3D = 10.0  # m, vertical spacing of the standalone 3D product
D_MAX_3D = 200.0  # m below the bedrock surface


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    dom = load_domain()
    cfg = units_config()["geometry"]["alteration"]["finn_2001"]
    raw = A.fetch(dom.path("raw") / "rainier_aerogeophysics")
    geo = read_tree(dom.path("processed") / "geomodel.zarr")
    s = geo["surface"].to_dataset()

    # the survey footprint on the model surface grid
    em = A.read_grid(raw, "33k")
    from pyproj import Transformer

    tf = Transformer.from_crs(A.NAD27_UTM10, dom.crs, always_xy=True)
    cx, cy = tf.transform([float(em.x.min()), float(em.x.max())], [float(em.y.min()), float(em.y.max())])
    sel = s.sel(x=slice(min(cx) - 200, max(cx) + 200), y=slice(min(cy) - 200, max(cy) + 200))
    x, y = sel.x.values, sel.y.values

    reg = A.check_registration(
        {k: A.to_model_grid(A.read_grid(raw, k), x, y, dom.crs) for k in (*F.FREQS, "rp")},
        sel["elevation"],
        sel["ice_thickness"],
    )
    logging.info("registration (corr): %s", reg)
    if reg["rp"] < 0.3 or min(reg[f] for f in F.FREQS) < 0.05:
        raise SystemExit(f"survey grids look mis-registered: {reg}")

    edifice = np.isin(sel["surface_unit"].values, cfg["units"])
    ds = F.em_fields(raw, x, y, dom.crs, cfg, edifice)
    M, minfo = F.apparent_magnetization(raw, s["elevation"], x, y, dom.crs)
    ln = "terrain-correlated apparent magnetisation (reduced-to-pole anomaly on terrain effect)"
    ds["apparent_magnetization"] = (("y", "x"), M, {"units": "A/m", "long_name": ln})
    # onto the full surface grid (zeros and no coverage outside the survey)
    full = ds.reindex(x=s.x, y=s.y, fill_value=0)
    for v in ("apparent_magnetization", *(f"alt_log10_rho_{f}" for f in F.FREQS)):
        full[v] = ds[v].reindex(x=s.x, y=s.y)
    full.attrs = {
        "source": "Rystrom, Finn & Deszcz-Pan 2000 (USGS OFR 00-027); method after Finn et al. 2001",
        "thresholds": json.dumps(cfg),
        "registration_corr": json.dumps(reg),
        "magnetization": json.dumps(minfo),
    }
    write(full, dom.path("processed") / "alteration_finn2001.zarr")

    # standalone 3D product: alteration against elevation, 10 m to 200 m below the bedrock surface
    allowed = np.isin(sel["surface_unit"].values, cfg["units"])
    bed = sel["elevation"].values - sel["ice_thickness"].fillna(0).values
    zs = np.arange(
        np.ceil(np.nanmax(bed) / DZ_3D) * DZ_3D, np.floor(np.nanmin(bed) / DZ_3D) * DZ_3D - D_MAX_3D, -DZ_3D
    )
    d_rock = bed[None] - zs[:, None, None]
    a3 = F.alteration_3d({k: ds[k].values[None] for k in ds.data_vars}, d_rock, allowed[None])
    a3 = np.where((d_rock >= 0) & (d_rock <= D_MAX_3D), a3, np.nan).astype(np.float32)
    keep = np.isfinite(a3).any(axis=(1, 2))
    prod = xr.Dataset(
        {
            "alteration": (
                ("z", "y", "x"),
                a3[keep],
                {
                    "units": "1",
                    "long_name": "hydrothermal alteration intensity",
                    "comment": "0 fresh, 1 fully altered; NaN in air, ice, or deeper "
                    "than 200 m below the bedrock surface",
                },
            ),  # fmt: skip
            "bedrock_elevation": (
                ("y", "x"),
                bed.astype(np.float32),
                {"units": "m", "long_name": "elevation of the bedrock surface (NAVD88)"},
            ),  # fmt: skip
            "alteration_surface": ds["alt_a_surface"],
            "apparent_magnetization": ds["apparent_magnetization"],
            **{f"log10_resistivity_{f}": ds[f"alt_log10_rho_{f}"] for f in F.FREQS},
            **{f"depth_of_investigation_{f}": ds[f"alt_doi_{f}"] for f in F.FREQS},
        },
        coords={
            "z": ("z", zs[keep], {"units": "m", "positive": "up", "long_name": "elevation (NAVD88)"}),
            "y": ("y", y, {"units": "m", "long_name": f"northing, {dom.crs}"}),
            "x": ("x", x, {"units": "m", "long_name": f"easting, {dom.crs}"}),
        },  # fmt: skip
        attrs={
            "title": "rainier3d near-surface hydrothermal alteration from the 1996 helicopter EM survey",
            "Conventions": "CF-1.8",
            "crs": dom.crs,
            "vertical_datum": "NAVD88 (EPSG:5703)",
            "references": "Finn, Sisson & Deszcz-Pan 2001, Nature 409, 600-603, doi:10.1038/35054533; "
            "Rystrom, Finn & Deszcz-Pan 2000, USGS OFR 00-027, doi:10.3133/ofr200027",
            "method": F.__doc__.strip().splitlines()[0],
            "thresholds": json.dumps(cfg),
            "repository": "https://github.com/Denolle-Lab/mt-rainier-digital-model",
        },
    )
    grids = dom.path("outputs") / "grids"
    grids.mkdir(parents=True, exist_ok=True)
    path = grids / "rainier3d_alteration_finn2001.nc"
    prod.to_netcdf(path, encoding={v: {"zlib": True, "complevel": 4} for v in prod.data_vars})

    # summary numbers and figures
    X, Y = np.meshgrid(x, y)
    sx, sy = dom.summit_xy
    R = np.hypot(X - sx, Y - sy)
    E = allowed & (ds["alt_coverage"].values > 0)
    a_s = ds["alt_a_surface"].values
    cell = (x[1] - x[0]) ** 2
    vol = float(np.nansum(np.where(np.isfinite(a3), a3, 0.0)) * cell * DZ_3D / 1e9)
    zones = {
        "west flank": E & (X < sx - 1500) & (R < 6000),
        "east flank": E & (X > sx + 1500) & (R < 6000),
        "summit r<1.5 km": E & (R < 1500),
    }
    summary = {
        "surface_area_a_ge_0.5_km2": float((E & (a_s >= 0.5)).sum() * cell / 1e6),
        "surveyed_edifice_area_km2": float(E.sum() * cell / 1e6),
        "altered_volume_equiv_km3": vol,
        "zones": {
            k: {
                "mean_a_surface": float(a_s[m].mean()),
                "frac_a_ge_0.5": float((a_s[m] >= 0.5).mean()),
                "median_M_app": float(np.nanmedian(M[m])),
            }
            for k, m in zones.items()
        },  # fmt: skip
        "registration_corr": reg,
        "magnetization": minfo,
        "product": str(path.relative_to(REPO)) if path.is_relative_to(REPO) else str(path),
    }
    out = dom.path("outputs") / "alteration"
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps(summary, indent=1))
    figures(ds, sel, x, y, dom, a3, zs, REPO / "docs" / "alteration")
    logging.info("\n%s", json.dumps(summary, indent=1))


def figures(ds, sel, x, y, dom, a3, zs, out):
    out.mkdir(parents=True, exist_ok=True)
    sx, sy = dom.summit_xy
    ext = (x[0] / 1e3, x[-1] / 1e3, y[0] / 1e3, y[-1] / 1e3)
    el = sel["elevation"].values
    ice = sel["ice_thickness"].fillna(0).values
    fig, ax = plt.subplots(2, 3, figsize=(16, 9), constrained_layout=True)
    panels = [
        (ds[f"alt_log10_rho_{f}"], f"log10 apparent resistivity, {f}", "turbo_r", None) for f in F.FREQS
    ]
    panels += [(ds["alt_a_surface"], "alteration intensity of the surface rock", "magma", (0, 1)),
               (ds["apparent_magnetization"], "apparent magnetisation (A/m)", "RdBu_r", (-1, 5))]  # fmt: skip
    for a, (v, t, cm, lim) in zip(ax.flat, panels, strict=True):
        vv = v.values
        lo, hi = lim or np.nanpercentile(vv, [2, 98])
        im = a.imshow(vv, origin="lower", extent=ext, cmap=cm, vmin=lo, vmax=hi)
        a.contour(x / 1e3, y / 1e3, el, levels=np.arange(1500, 4400, 500), colors="0.3", linewidths=0.4)
        a.contour(x / 1e3, y / 1e3, (ice > 10).astype(float), levels=[0.5], colors="c", linewidths=0.8)
        a.plot(sx / 1e3, sy / 1e3, "k^", ms=9)
        a.set_title(t, fontsize=10)
        a.set(xlabel="easting (km)", ylabel="northing (km)")
        plt.colorbar(im, ax=a, shrink=0.8)
    fig.savefig(out / "fig1_em_alteration_maps.png", dpi=130)

    # west-east section through the summit
    j = int(np.argmin(np.abs(y - sy)))
    fig, a = plt.subplots(figsize=(12, 4), constrained_layout=True)
    im = a.pcolormesh(
        x / 1e3, zs, np.ma.masked_invalid(a3[:, j, :]), cmap="magma", vmin=0, vmax=1, shading="nearest"
    )
    a.plot(x / 1e3, el[j], "k", lw=1, label="surface")
    a.plot(x / 1e3, el[j] - ice[j], "c", lw=1, label="glacier bed")
    a.set(
        xlabel="easting (km)",
        ylabel="elevation (m)",
        title="Alteration, W-E section through the summit (top 200 m)",
    )
    a.legend(frameon=False)
    plt.colorbar(im, ax=a, label="alteration intensity")
    fig.savefig(out / "fig2_section_we.png", dpi=130)


if __name__ == "__main__":
    main()
