"""S5: fuse the geology model with the regional model -> data/processed/model.zarr.

model.zarr is the master product: /surface plus /L1, /L2, /L3 with unit, alteration, depth, the
fused vp, vs, rho, qp, qs, and the two inputs (``*_geology``, ``*_regional``) for comparison.
Vs and Vp/Vs are fused (Vp = Vs * Vp/Vs). Writes outputs/fusion_report.csv with the low-pass misfit
per level for Vp and Vs.
"""

from __future__ import annotations

import argparse
import logging

import numpy as np
import pandas as pd
import xarray as xr
import yaml

from rainier3d.config.domain import REPO, load_domain
from rainier3d.fusion import blend, regional
from rainier3d.geomodel.rules import AIR, ICE
from rainier3d.io.store import read, read_tree, write
from rainier3d.petro.relations import nafe_drake_rho_from_vp, q_from_vs
from rainier3d.petro.table import perturbations
from rainier3d.validate.calibrate import log_factor


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default=None)
    ap.add_argument(
        "--no-vs-calibration", action="store_true", help="ignore configs/vs_calibration.yaml (for S12)"
    )
    a = ap.parse_args()
    dom = load_domain(a.profile)
    fc = dom.cfg["fusion"]
    cal_path = REPO / "configs" / "vs_calibration.yaml"
    cal = None if a.no_vs_calibration or not cal_path.exists() else yaml.safe_load(cal_path.read_text())
    geo = read_tree(dom.path("processed") / "geomodel.zarr")
    props = read_tree(dom.path("processed") / "properties_geology.zarr")
    cvm, cres = regional.load_cvm(dom), regional.load_crescent(dom)
    q = perturbations()["q"]

    surf = geo["surface"].to_dataset()
    env = dom.path("processed") / "surface_layers.zarr"
    if env.exists():  # S2 environmental layers share the surface grid
        surf = surf.merge(read(env), compat="override", combine_attrs="drop_conflicts")
    nodes, report = {"/surface": surf}, []
    for name, lev in dom.levels.items():
        g, p = geo[name].to_dataset(), props[name].to_dataset()
        unit, depth = g["unit"].values, g["depth"].values
        mask = unit != AIR
        reg = regional.regional_on_level(lev, depth, cvm, cres)
        if cal is not None:  # S12: depth-dependent factor on the regional Vs, calibrated on PNSN S-P times
            reg["vs"] = reg["vs"] * np.exp(
                log_factor(depth, np.array(cal["log_factor"]), np.array(cal["knots_m"]))
            )
            # floor at Vp/Vs = vpvs_floor (quartz-rich crust, Christensen 1996): raising Vs where the regional
            # ratio is already low would otherwise give unphysical ratios (min 1.45 in L2 without it)
            reg["vs"] = np.minimum(reg["vs"], reg["vp"] / cal.get("vpvs_floor", 1.6))
        out = g.copy()
        # fuse Vs and Vp/Vs (not Vp and Vs separately), so Vp/Vs stays between its two inputs
        args = (depth, mask, fc["lambda_c_by_depth"], lev.dx, fc["geology_only_depth_m"], fc["taper_depth_m"])
        vs_f = blend.fuse(p["vs"].values, reg["vs"], *args)
        kappa = blend.fuse(p["vp"].values / p["vs"].values, reg["vp"] / reg["vs"], *args)
        for v, fused in (("vp", vs_f * kappa), ("vs", vs_f)):
            out[v] = (("z", "y", "x"), fused.astype(np.float32), {"units": "m/s"})
            out[f"{v}_geology"] = p[v]
            out[f"{v}_regional"] = (
                ("z", "y", "x"),
                np.where(mask, reg[v], np.nan).astype(np.float32),
                {"units": "m/s"},
            )
            report.append(
                {
                    "level": name,
                    "var": v,
                    "lowpass_rms_lnV": blend.lowpass_misfit(
                        fused, reg[v], depth, mask, fc["lambda_c_by_depth"], lev.dx, fc["taper_depth_m"]
                    ),
                    "mean_ln_fused_minus_regional": float(np.nanmean(np.log(fused / reg[v])[mask])),
                }
            )
        vp_g, vp_f = p["vp"].values / 1e3, out["vp"].values / 1e3
        ratio = nafe_drake_rho_from_vp(vp_f) / nafe_drake_rho_from_vp(vp_g)
        rho = np.where(unit == ICE, p["rho"].values, p["rho"].values * ratio)
        out["rho"] = (("z", "y", "x"), rho.astype(np.float32), {"units": "kg/m3"})
        qp, qs = q_from_vs(out["vs"].values / 1e3, q["qs_per_vs"], q["qp_over_qs"])
        out["qp"] = (("z", "y", "x"), qp.astype(np.float32))
        out["qs"] = (("z", "y", "x"), qs.astype(np.float32))
        out["vs_unc_regional"] = (
            ("z", "y", "x"),
            np.where(mask, reg["vs_unc"], np.nan).astype(np.float32),
            {"units": "m/s", "source": "crescent_gen0"},
        )
        if cal is not None:
            out.attrs["vs_calibration"] = f"configs/vs_calibration.yaml ({cal['date']})"
        nodes[f"/{name}"] = out

    tree = xr.DataTree.from_dict(nodes)
    tree.attrs = {
        "crs": dom.crs,
        "vertical_datum": dom.vertical_datum,
        "domain": dom.name,
        "method": "M1: rule-based geology + petrophysics, fused with CVM v1.7 / CRESCENT Gen0",
    }
    write(tree, dom.path("processed") / "model.zarr")
    rep = pd.DataFrame(report)
    rep.to_csv(dom.path("outputs") / "fusion_report.csv", index=False)
    logging.info("\n%s", rep.to_string(index=False, float_format=lambda v: f"{v:.4f}"))


if __name__ == "__main__":
    main()
