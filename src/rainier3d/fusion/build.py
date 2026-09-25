"""Model assembly shared by S5 (written to model.zarr) and S13 (in memory, inside the calibration).

regional_level: the regional Vp and Vs on a level, times the static bias of the calibration file, with the
Vp/Vs floor. fuse_level: geology + regional -> fused vp, vs, rho, qp, qs (the S5 recipe, unchanged).
"""

from __future__ import annotations

import numpy as np

from rainier3d.fusion import blend, regional
from rainier3d.geomodel.rules import AIR, ICE
from rainier3d.petro.relations import nafe_drake_rho_from_vp, q_from_vs
from rainier3d.validate.calibrate import log_factor


def regional_bias(cal: dict | None) -> tuple[np.ndarray, dict] | None:
    """(knots_m, {"vp": log_factor or None, "vs": ...}) from any calibration file version.

    velocity_calibration.yaml v2 keeps it under ``regional_bias``; v1 (S13, depth factors) and
    vs_calibration.yaml (S12, Vs only) keep ``knots_m`` at the top level.
    """
    if cal is None:
        return None
    rb = cal.get("regional_bias", cal)
    lf = {v: np.array(rb[v]["log_factor"]) if v in rb else None for v in ("vp", "vs")}
    if lf["vs"] is None and "log_factor" in rb:
        lf["vs"] = np.array(rb["log_factor"])
    return np.array(rb["knots_m"]), lf


def apply_bias(reg: dict, depth: np.ndarray, cal: dict | None) -> dict:
    """Regional Vp, Vs times the calibration's static bias, then the Vp/Vs floor (a new dict)."""
    out = dict(reg)
    rb = regional_bias(cal)
    if rb is None:
        return out
    knots, lf = rb
    for v in ("vp", "vs"):
        if lf[v] is not None:
            out[v] = reg[v] * np.exp(log_factor(depth, lf[v], knots))
    # floor at Vp/Vs = vpvs_floor (quartz-rich crust, Christensen 1996): raising Vs where the regional
    # ratio is already low would otherwise give unphysical ratios (min 1.45 in L2 without it)
    out["vs"] = np.minimum(out["vs"], out["vp"] / cal.get("vpvs_floor", 1.6))
    return out


def regional_level(lev, depth, cvm, cres, cal: dict | None) -> dict:
    """Regional Vp, Vs (m/s) on a level with the calibration's static bias and Vp/Vs floor applied."""
    return apply_bias(regional.regional_on_level(lev, depth, cvm, cres), depth, cal)


def fuse_level(g, p, reg: dict, lev, fc: dict, q: dict, name: str, full: bool = True):
    """Fused level dataset and its low-pass report rows. ``full=False`` returns vp and vs only (for S13)."""
    unit, depth = g["unit"].values, g["depth"].values
    mask = unit != AIR
    out = g.copy()
    # fuse Vs and Vp/Vs (not Vp and Vs separately), so Vp/Vs stays between its two inputs
    args = (depth, mask, fc["lambda_c_by_depth"], lev.dx, fc["geology_only_depth_m"], fc["taper_depth_m"])
    vs_f = blend.fuse(p["vs"].values, reg["vs"], *args)
    kappa = blend.fuse(p["vp"].values / p["vs"].values, reg["vp"] / reg["vs"], *args)
    report = []
    for v, fused in (("vp", vs_f * kappa), ("vs", vs_f)):
        out[v] = (("z", "y", "x"), fused.astype(np.float32), {"units": "m/s"})
        if not full:
            continue
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
    if not full:
        return out, report
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
    return out, report
