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


def assign(level: xr.Dataset, table: pd.DataFrame, pert: dict, geo_cal: dict | None = None) -> xr.Dataset:
    u = level["unit"].values
    rock = np.isin(u, rock_unit_ids())
    gc = {"ln_v0": 0.0, "ln_pstar": 0.0, "ln_vs": 0.0, **(geo_cal or {})}
    d = np.maximum(level["depth"].values, 0.0)
    a = level["alteration"].values
    pp = pert["pressure"]
    p_mpa = (pp["rho_bulk_kgm3"] - pp["rho_water_kgm3"]) * G * d / 1e6

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
    vp, vs, rho = vp * (1 - a * ap["dvp"]), vs * (1 - a * ap["dvs"]), rho * (1 - a * ap["drho"])

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
    for k, (un, ln) in {
        "vp": ("m/s", "P-wave speed"),
        "vs": ("m/s", "S-wave speed"),
        "rho": ("kg/m3", "density"),
        "qp": ("1", "P quality factor"),
        "qs": ("1", "S quality factor"),
    }.items():
        ds[k].attrs = {"units": un, "long_name": ln}
    return ds
