"""Roughness of the velocity model: steps of ln Vs between neighbouring cells of a uniform 250 m grid.

Measures the interfaces that are not geology: the L2/L3 level boundary at -6 km, the change from CVM v1.7 to
CRESCENT (a switch at 9.9 km below the ground, or the blend window of rainier3d.fusion.regional), and the
lateral steps of extruded map units 150-2000 m below the ground, against the ordinary vertical step at 7-9 km
below the ground. The CVM-to-CRESCENT measure takes the steps inside the blend window of configs/domain.yaml
(``fusion.regional_blend_m``, 8-16 km below the ground), without the pair of cells across a level boundary
(the L2/L3 step has its own measure), so that it sees the steepest part of a blend and a switch at 9.9 km
alike. It is given as percentiles of all steps in the window, whose reference is the same percentiles
16.5-20.5 km below the ground (within the model's -20 km base), where CRESCENT alone is used, and as the
largest step per column.
The largest step per column has no reference of the same length: the maximum of n steps grows with n, and the
window has 32 cells against the reference's 16.
S10 records it in outputs/paper/numbers.json (model.roughness).

    pixi run python -m rainier3d.report.roughness data/processed/model.zarr
"""

from __future__ import annotations

import json
import sys

import numpy as np

import rainier3d.api as r3
from rainier3d.config.domain import load_domain


def roughness(store) -> dict:
    """Median and upper percentiles of |d ln Vs| at each interface (see the module docstring)."""
    tree = r3.open_model(store)
    g = r3.grid(tree, dx=250, dz=250, zmin=-20000, variables=("vs",))
    ok = g.air.values == 0
    lv = np.log(g.vs.values)
    z = g.z.values  # descending, cell centres
    elev = tree["surface"].to_dataset().elevation.interp(x=g.x, y=g.y).values  # (y, x)
    dz = np.abs(np.diff(lv, axis=0))  # between z[k] and z[k+1]
    zmid = 0.5 * (z[:-1] + z[1:])
    both = ok[:-1] & ok[1:]
    out = {}
    # L2/L3 level boundary at -6000 m
    k = int(np.argmin(np.abs(zmid + 6000)))
    out["l2_l3_step"] = {
        "median": float(np.median(dz[k][both[k]])),
        "p95": float(np.percentile(dz[k][both[k]], 95)),
    }
    # CVM -> CRESCENT: the steps in the blend window, without a pair of cells across a level boundary;
    # reference 16.5-20.5 km below the ground
    dom = load_domain()
    a, b = dom.cfg["fusion"]["regional_blend_m"]
    edges = [lev.z_bot for lev in dom.levels.values()][:-1]
    inner = np.all([np.abs(zmid - e) > np.abs(z[1] - z[0]) / 2 for e in edges], axis=0)[:, None, None]
    dbg = elev[None] - zmid[:, None, None]
    for name, (lo, hi) in {"cvm_crescent_step": (a, b), "vertical_step_16_20km_bg": (16500, 20500)}.items():
        win = (dbg > lo) & (dbg < hi) & both & inner
        d = dz[win]
        out[name] = {k: float(np.percentile(d, q)) for k, q in (("median", 50), ("p95", 95), ("p99", 99))}
    st = np.where((dbg > a) & (dbg < b) & both & inner, dz, 0.0).max(axis=0)
    st = st[st > 0]
    out["cvm_crescent_column_max"] = {"median": float(np.median(st)), "p95": float(np.percentile(st, 95))}
    # reference: typical vertical step away from interfaces, 7-9 km below the ground
    ref = dz[(dbg > 7000) & (dbg < 9000) & both]
    out["vertical_step_7_9km_bg"] = {"median": float(np.median(ref)), "p95": float(np.percentile(ref, 95))}
    # lateral steps 150-2000 m below the ground (walls of extruded units)
    dcell = elev[None] - z[:, None, None]
    for name, (a, b) in {"lateral_150_1000m": (150, 1000), "lateral_1000_2000m": (1000, 2000)}.items():
        m = (dcell >= a) & (dcell < b) & ok
        dx = np.abs(np.diff(lv, axis=2))[m[:, :, :-1] & m[:, :, 1:]]
        dy = np.abs(np.diff(lv, axis=1))[m[:, :-1, :] & m[:, 1:, :]]
        d = np.concatenate([dx, dy])
        out[name] = {
            "median": float(np.median(d)),
            "p95": float(np.percentile(d, 95)),
            "p99": float(np.percentile(d, 99)),
        }
    return out


def level_continuity(store) -> dict:
    """Per variable (vs, vs_geology, vs_regional): the median change of ln V from the bottom cell of L2 to the
    top cell of L3 at L3's columns, against what the gradient of L2's two bottom cells predicts over the gap
    between the two cell centres; a residual near zero means the levels agree, and a step on a uniform grid
    comes from the resampling."""
    tree = r3.open_model(store)
    return continuity(tree["L2"].to_dataset(), tree["L3"].to_dataset())


def continuity(l2, l3, variables=("vs", "vs_geology", "vs_regional")) -> dict:
    """``level_continuity`` on two level datasets, l2 above l3, each with z descending."""
    if not (l2.z[0] > l2.z[-1] and l2.z[-1] > l3.z[0]):
        raise ValueError("continuity needs z descending, with l2 above l3")
    z2, z2b, z3 = float(l2.z[-1]), float(l2.z[-2]), float(l3.z[0])
    out = {"gap_m": z2 - z3}
    for v in variables:
        a = np.log(l2[v].isel(z=[-2, -1]).interp(x=l3.x, y=l3.y).values)
        change = np.log(l3[v].isel(z=0).values) - a[1]
        pred = (a[1] - a[0]) / (z2b - z2) * (z2 - z3)
        ok = np.isfinite(change) & np.isfinite(pred)
        out[v] = {
            "change_median": float(np.median(change[ok])),
            "predicted_median": float(np.median(pred[ok])),
            "residual_median": float(np.median((change - pred)[ok])),
        }
    return out


if __name__ == "__main__":
    print(json.dumps(roughness(sys.argv[1]), indent=1))
