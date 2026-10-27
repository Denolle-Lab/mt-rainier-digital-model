"""Model assembly shared by S5 (written to model.zarr) and S13 (in memory, inside the calibration).

regional_level: the regional Vp and Vs on a level, times the static bias of the calibration file, with the
Vp/Vs floor. fuse_level: geology + regional -> fused vp, vs, rho, qp, qs, then the magma-body anomaly
(``magma_weight`` of S3 times the magma_mush factors of configs/perturbations.yaml) on the fused model, so
that neither the high-pass of the fusion nor its clamp removes it.
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


def regional_level(lev, depth, cvm, cres, cal: dict | None, fc: dict) -> dict:
    """Regional Vp, Vs (m/s) on a level with the calibration's static bias and Vp/Vs floor applied; ``fc`` is
    the fusion block of configs/domain.yaml (its CVM-to-CRESCENT window)."""
    reg = regional.regional_on_level(lev, depth, cvm, cres, fc["regional_blend_m"])
    return apply_bias(reg, depth, cal)


def smoothing(fc: dict) -> dict:
    """The geology filters of the fusion block of configs/domain.yaml (fusion.blend.smooth_geology)."""
    return {
        "z_smooth": fc.get("lambda_z_from_depth_m", 0.0),
        "lambda_z": fc.get("lambda_z_m", 0.0),
        "lambda_h": fc.get("lambda_h_m", 0.0),
        "growth_h": fc.get("lambda_h_growth", 1.0),
        "lambda_h0": fc.get("lambda_h_start_m", 0.0),
        "ramp_h": fc.get("lambda_h_ramp", np.inf),
    }


def fuse_level(
    g, p, reg: dict, lev, fc: dict, q: dict, name: str, full: bool = True, magma: dict | None = None
):
    """Fused level dataset and its low-pass report rows. ``full=False`` returns vp and vs only (for S13).
    ``magma``: the magma_mush factors (dvp, dvs, drho) applied with the S3 weight ``magma_weight``."""
    unit, depth = g["unit"].values, g["depth"].values
    mask = unit != AIR
    out = g.copy()
    # fuse Vs and Vp/Vs (not Vp and Vs separately), so Vp/Vs stays between its two inputs
    args = (depth, mask, fc["lambda_c_by_depth"], lev.dx, fc["geology_only_depth_m"], fc["taper_depth_m"])
    kw = {"dz": lev.dz, **smoothing(fc)}
    vs_f = blend.fuse(p["vs"].values, reg["vs"], *args, **kw)
    kappa = blend.fuse(p["vp"].values / p["vs"].values, reg["vp"] / reg["vs"], *args, **kw)
    vp_f = vs_f * kappa
    wm = g["magma_weight"].values if magma is not None and "magma_weight" in g else None
    vp_rock = vp_f  # before the magma anomaly: the density ratio below
    if wm is not None:
        vp_f, vs_f = vp_f * (1 - wm * magma["dvp"]), vs_f * (1 - wm * magma["dvs"])
    report = []
    for v, fused in (("vp", vp_f), ("vs", vs_f)):
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
    vp_g = p["vp"].values / 1e3
    ratio = nafe_drake_rho_from_vp(vp_rock / 1e3) / nafe_drake_rho_from_vp(vp_g)
    rho = np.where(unit == ICE, p["rho"].values, p["rho"].values * ratio)
    if wm is not None:
        rho = rho * (1 - wm * magma["drho"])
    out["rho"] = (("z", "y", "x"), rho.astype(np.float32), {"units": "kg/m3"})
    qp, qs = q_from_vs(out["vs"].values / 1e3, q["qs_per_vs"], q["qp_over_qs"])
    out["qp"] = (("z", "y", "x"), qp.astype(np.float32))
    out["qs"] = (("z", "y", "x"), qs.astype(np.float32))
    for v in ("porosity", "log10_permeability", "weathering_index"):  # the critical zone of S4, unfused
        if v in p:
            out[v] = p[v]
    out["vs_unc_regional"] = (
        ("z", "y", "x"),
        np.where(mask, reg["vs_unc"], np.nan).astype(np.float32),
        {"units": "m/s", "source": "crescent_gen0"},
    )
    return out, report
