"""Geology -> Vp, Vs, density, Qp, Qs per cell (the "geology model", before fusion).

Per unit: Vp from the crack-closure law at the effective pressure of the overburden; Vs from the
unit's Vp/Vs, else Brocher (2005); density from the unit's value, else Nafe-Drake (Brocher 2005).
Then the magma_mush and alteration factors, then Q from Vs. Output units: m/s, kg/m^3.

``geo_cal`` (the ``geology`` block of configs/velocity_calibration.yaml, fitted by S13) scales, for rock units
only, the zero-pressure Vp (V0 * exp(ln_v0), kept below 0.98 Vinf), the crack-closure pressure
(P* * exp(ln_pstar)) and Vs (* exp(ln_vs), a Vp/Vs shift). Unit contrasts and the sourced table are unchanged.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import xarray as xr

from rainier3d.geomodel.rules import AIR, MAGMA
from rainier3d.petro import relations as rel
from rainier3d.petro.table import rock_unit_ids

G = 9.81


def _lut(table: pd.DataFrame, col: str, n: int = 256) -> np.ndarray:
    out = np.full(n, np.nan)
    for uid, v in table[col].items():
        out[int(uid)] = v
    return out


def rock_properties(u, p_mpa, a, table: pd.DataFrame, pert: dict, geo_cal: dict | None = None):
    """Vp, Vs (km/s) and density (g/cm3) of map units ``u`` at effective pressure ``p_mpa`` and alteration
    ``a``:
    crack closure, Vp/Vs or Brocher (2005), unit density or Nafe-Drake, then the magma and alteration factors.
    The one rock law of the model: S4 applies it to every cell, and the critical-zone medium
    (rainier3d.cz.medium) to its rock end-member, at the same effective pressure."""
    rock = np.isin(u, rock_unit_ids())
    gc = {"ln_v0": 0.0, "ln_pstar": 0.0, "ln_vs": 0.0, **(geo_cal or {})}
    v0, vinf, pstar = _lut(table, "vp0_kms")[u], _lut(table, "vpinf_kms")[u], _lut(table, "pstar_mpa")[u]
    v0 = np.where(rock, np.minimum(v0 * np.exp(gc["ln_v0"]), 0.98 * vinf), v0)
    pstar = np.where(rock, pstar * np.exp(gc["ln_pstar"]), pstar)
    vp = rel.crack_closure(v0, vinf, p_mpa, pstar)
    vpvs = _lut(table, "vpvs")[u]
    vs = np.where(np.isnan(vpvs), rel.brocher_vs_from_vp(vp), vp / vpvs)
    vs = np.where(rock, vs * np.exp(gc["ln_vs"]), vs)
    rho = _lut(table, "rho_gcc")[u]
    rho = np.where(np.isnan(rho), rel.nafe_drake_rho_from_vp(vp), rho)
    m = u == MAGMA
    mp = pert["magma_mush"]
    vp, vs, rho = (np.where(m, v * (1 - mp[k]), v) for v, k in ((vp, "dvp"), (vs, "dvs"), (rho, "drho")))
    ap = pert["alteration"]
    return vp * (1 - a * ap["dvp"]), vs * (1 - a * ap["dvs"]), rho * (1 - a * ap["drho"])


def effective_pressure_mpa(depth, pert: dict, water_table=None):
    """Effective pressure (MPa) at ``depth`` below the ground: lithostatic at rho_bulk minus a hydrostatic
    pore
    pressure below the water table (depth below ground; None: at the ground, the M1 rule)."""
    pp = pert["pressure"]
    if water_table is None:  # the M1 rule, kept bit for bit
        return (pp["rho_bulk_kgm3"] - pp["rho_water_kgm3"]) * G * depth / 1e6
    u = pp["rho_water_kgm3"] * G * np.maximum(depth - water_table, 0.0)
    return (pp["rho_bulk_kgm3"] * G * depth - u) / 1e6


def assign(
    level: xr.Dataset, table: pd.DataFrame, pert: dict, geo_cal: dict | None = None, cz=None
) -> xr.Dataset:
    """Properties of every cell. ``cz`` (a rainier3d.cz.level.Context) adds the critical zone: the water
    table of the effective pressure, porosity and permeability everywhere, and the near-surface cells replaced
    by the travel-time average of the critical-zone columns inside them."""
    u = level["unit"].values
    d = np.maximum(level["depth"].values, 0.0)
    a = level["alteration"].values
    wt = None if cz is None else cz.water_table_depth(level)
    p_mpa = effective_pressure_mpa(d, pert, wt)
    vp, vs, rho = rock_properties(u, p_mpa, a, table, pert, geo_cal)
    hyd = None
    if cz is not None:
        vp, vs, rho, hyd = cz.apply(level, vp, vs, rho, d, table, pert, geo_cal)

    q = pert["q"]
    qp, qs = rel.q_from_vs(vs, q["qs_per_vs"], q["qp_over_qs"])

    air = u == AIR
    dims = ("z", "y", "x")

    def f32(v, scale=1.0):
        return (dims, np.where(air, np.nan, v * scale).astype(np.float32))

    ds = xr.Dataset(
        {"vp": f32(vp, 1e3), "vs": f32(vs, 1e3), "rho": f32(rho, 1e3), "qp": f32(qp), "qs": f32(qs)},
        coords=level[["z", "y", "x"]].coords,
    )
    if hyd is not None:  # the structure a groundwater model will run on
        ds["porosity"] = f32(hyd["porosity"])
        ds["log10_permeability"] = f32(hyd["log10_permeability"])
        ds["weathering_index"] = f32(hyd["weathering_index"])
        ds["porosity"].attrs = {"units": "1", "long_name": "porosity"}
        ds["log10_permeability"].attrs = {"units": "log10(m2)", "long_name": "permeability"}
        ds["weathering_index"].attrs = {
            "units": "1",
            "long_name": "weathering index, 1 regolith to 0 fresh rock",
        }
    for k, (un, ln) in {
        "vp": ("m/s", "P-wave speed"),
        "vs": ("m/s", "S-wave speed"),
        "rho": ("kg/m3", "density"),
        "qp": ("1", "P quality factor"),
        "qs": ("1", "S quality factor"),
    }.items():
        ds[k].attrs = {"units": un, "long_name": ln}
    return ds
