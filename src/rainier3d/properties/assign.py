"""Geology -> Vp, Vs, density, Qp, Qs per cell (the "geology model", before fusion).

Per unit: Vp from the crack-closure law at the effective pressure of the overburden; Vs from the
unit's Vp/Vs, else Brocher (2005); density from the unit's value, else Nafe-Drake (Brocher 2005).
Then the magma_mush and alteration factors, then Q from Vs. Output units: m/s, kg/m^3.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import xarray as xr

from rainier3d.geomodel.rules import AIR, MAGMA
from rainier3d.petro import relations as rel

G = 9.81


def _lut(table: pd.DataFrame, col: str, n: int = 256) -> np.ndarray:
    out = np.full(n, np.nan)
    for uid, v in table[col].items():
        out[int(uid)] = v
    return out


def assign(level: xr.Dataset, table: pd.DataFrame, pert: dict) -> xr.Dataset:
    u = level["unit"].values
    d = np.maximum(level["depth"].values, 0.0)
    a = level["alteration"].values
    pp = pert["pressure"]
    p_mpa = (pp["rho_bulk_kgm3"] - pp["rho_water_kgm3"]) * G * d / 1e6

    vp = rel.crack_closure(
        _lut(table, "vp0_kms")[u], _lut(table, "vpinf_kms")[u], p_mpa, _lut(table, "pstar_mpa")[u]
    )
    vpvs = _lut(table, "vpvs")[u]
    vs = np.where(np.isnan(vpvs), rel.brocher_vs_from_vp(vp), vp / vpvs)
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
