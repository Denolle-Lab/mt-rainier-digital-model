"""Roughness of the velocity model: steps of ln Vs between neighbouring cells of a uniform 250 m grid.

Measures the interfaces that are not geology: the L2/L3 level boundary at -6 km, the change from CVM v1.7 to
CRESCENT (a switch at 9.9 km below the ground, or the blend window of rainier3d.fusion.regional), and the
lateral steps of extruded map units 150-2000 m below the ground, against the ordinary vertical step at 7-9 km
below the ground. The CVM-to-CRESCENT measure is, per column, the largest step 6-16.5 km below the ground, so
that it sees the steepest part of a blend and not only the 9.9 km point; its reference is the same statistic
16.5-20.5 km below the ground (within the model's -20 km base), where CRESCENT alone is used.
S10 records it in outputs/paper/numbers.json (model.roughness).

    pixi run python -m rainier3d.report.roughness data/processed/model.zarr
"""

from __future__ import annotations

import json
import sys

import numpy as np

import rainier3d.api as r3


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
    # CVM -> CRESCENT: per column, the largest step 6-16.5 km below the ground; reference 16.5-20.5 km
    dbg = elev[None] - zmid[:, None, None]
    for name, (a, b) in {"cvm_crescent_step": (6000, 16500), "column_max_16_20km_bg": (16500, 20500)}.items():
        st = np.where((dbg > a) & (dbg < b) & both, dz, 0.0).max(axis=0)
        st = st[st > 0]
        out[name] = {"median": float(np.median(st)), "p95": float(np.percentile(st, 95))}
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


if __name__ == "__main__":
    print(json.dumps(roughness(sys.argv[1]), indent=1))
