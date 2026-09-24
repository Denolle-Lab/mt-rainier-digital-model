"""Eikonal solver benchmark against analytic travel times, on the rainier3d S9 grid size.

Solvers: fteikpy (2nd-order fast sweeping, used by S6), pykonal EikonalSolver (FMM, node source seeded with
analytic times in a 1-cell ball, the same seeding as denopick's GPU path) and pykonal PointSourceSolver
(spherical near-source grid), scikit-fmm as denopick's CPU path (zero level set on a 1.01-cell sphere, no
offset added) and the same with the sphere travel time added back.
Cases: homogeneous V, and V(z) = v0 + g z (analytic T = arccosh(1 + g^2 r^2 / (2 v_s v_r)) / g).
Receivers: 300 random points in the box (5 km from edges) + 60 surface points; errors in ms.
"""

import sys
import time

import numpy as np
import pykonal
import skfmm
from fteikpy import Eikonal3D
from scipy.interpolate import RegularGridInterpolator

DX = float(sys.argv[1]) if len(sys.argv) > 1 else 0.5
LX, LY, LZ = 70.0, 75.0, 24.0  # km; z down from the top of the box
nx, ny, nz = int(LX / DX) + 1, int(LY / DX) + 1, int(LZ / DX) + 1
x, y, z = np.arange(nx) * DX, np.arange(ny) * DX, np.arange(nz) * DX
X, Y, Z = np.meshgrid(x, y, z, indexing="ij")
SRC = np.array([41.37, 36.52, 11.23])  # off-grid hypocentre
rng = np.random.default_rng(0)
REC = np.r_[
    rng.uniform([5, 5, 0.5], [LX - 5, LY - 5, LZ - 2], (300, 3)),
    np.c_[rng.uniform(5, LX - 5, 60), rng.uniform(5, LY - 5, 60), np.zeros(60)],
]


def analytic(v0, g, pts):
    r = np.linalg.norm(pts - SRC, axis=1)
    if g == 0:
        return r / v0
    vs, vr = v0 + g * SRC[2], v0 + g * pts[:, 2]
    return np.arccosh(1 + g**2 * r**2 / (2 * vs * vr)) / g


def interp(T, pts):
    return RegularGridInterpolator((x, y, z), T)(pts)


def run_fteikpy(V):
    e = Eikonal3D(np.transpose(V, (2, 0, 1)), gridsize=(DX, DX, DX))  # (z, x, y)
    tt = e.solve(SRC[[2, 0, 1]], nsweep=2, return_gradient=False)
    return tt(REC[:, [2, 0, 1]])


def run_pykonal(V):
    s = pykonal.EikonalSolver(coord_sys="cartesian")
    s.velocity.min_coords = 0, 0, 0
    s.velocity.node_intervals = DX, DX, DX
    s.velocity.npts = nx, ny, nz
    s.velocity.values = V
    d = np.sqrt((X - SRC[0]) ** 2 + (Y - SRC[1]) ** 2 + (Z - SRC[2]) ** 2)
    for idx in np.argwhere(d <= 1.01 * DX):
        i = tuple(idx)
        s.traveltime.values[i] = d[i] / V[i]
        s.unknown[i] = False
        s.trial.push(*i)
    s.solve()
    return interp(s.traveltime.values, REC)


def run_pykonal_ps(V):
    s = pykonal.solver.PointSourceSolver(coord_sys="cartesian")
    s.velocity.min_coords = 0, 0, 0
    s.velocity.node_intervals = DX, DX, DX
    s.velocity.npts = nx, ny, nz
    s.velocity.values = V
    s.src_loc = SRC
    s.solve()
    return interp(s.traveltime.values, REC)


def run_skfmm(V, add_offset):
    d = np.sqrt((X - SRC[0]) ** 2 + (Y - SRC[1]) ** 2 + (Z - SRC[2]) ** 2)
    rad = 1.01 * DX
    T = skfmm.travel_time(d - rad, speed=V, dx=DX, order=2)
    T = np.asarray(T)
    if add_offset:  # time from the source to the sphere, at the source velocity
        vs = RegularGridInterpolator((x, y, z), V)(SRC[None])[0]
        T = T + rad / vs
    return interp(T, REC)


SOLVERS = {
    "fteikpy (2nd-order FSM)": run_fteikpy,
    "pykonal FMM, seeded ball": run_pykonal,
    "pykonal PointSourceSolver": run_pykonal_ps,
    "scikit-fmm, denopick CPU seeding": lambda V: run_skfmm(V, False),
    "scikit-fmm, offset added": lambda V: run_skfmm(V, True),
}

print(f"grid {nx}x{ny}x{nz} = {nx * ny * nz / 1e6:.2f} M nodes, dx = {DX} km")
for case, (v0, g) in {"homogeneous 6 km/s": (6.0, 0.0), "gradient 4 + 0.1 z km/s": (4.0, 0.1)}.items():
    V = (v0 + g * Z).astype(np.float64)
    ta = analytic(v0, g, REC)
    print(f"\n{case}")
    print(f"{'solver':36s} {'time s':>7s} {'mean ms':>8s} {'RMS ms':>7s} {'max|e| ms':>9s} {'dm RMS ms':>9s}")
    for name, fn in SOLVERS.items():
        try:
            fn(V)  # warm-up (numba JIT for fteikpy), then time a second solve
            t0 = time.perf_counter()
            tt = fn(V)
        except Exception as e:  # report and continue
            print(f"{name:36s} failed: {e}")
            continue
        dt = time.perf_counter() - t0
        e = (tt - ta) * 1e3
        print(
            f"{name:36s} {dt:7.2f} {e.mean():8.1f} {np.sqrt((e**2).mean()):7.1f} {np.abs(e).max():9.1f}"
            f" {np.sqrt(((e - e.mean()) ** 2).mean()):12.1f}"
        )

# S-P bias of the unshifted scikit-fmm seeding (Vp 6, Vs 6/sqrt(3)): origin time cannot absorb it
Vp = np.full(X.shape, 6.0)
Vs = Vp / np.sqrt(3)
sp = (run_skfmm(Vs, False) - run_skfmm(Vp, False)) - (
    analytic(6 / np.sqrt(3), 0, REC) - analytic(6.0, 0, REC)
)
print(
    f"\nS-P error, denopick CPU seeding, homogeneous: mean {sp.mean() * 1e3:.1f} ms "
    f"(predicted -1.01 dx (1/Vs - 1/Vp) = {-1.01 * DX * (np.sqrt(3) / 6 - 1 / 6) * 1e3:.1f} ms)"
)
