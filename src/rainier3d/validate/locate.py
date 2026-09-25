"""3D earthquake relocation and joint Vp-Vs calibration (S13, S14).

Travel-time fields: one pykonal PointSourceSolver solve per station and phase (reciprocity) on the S6 grid.
Location: L1 grid search over the grid nodes around the catalogue hypocentre, then Gauss-Newton with a Huber
loss on trilinearly interpolated times (the grid-search-then-refine approach of NonLinLoc, Lomax et al. 2000,
without the posterior pdf).
Velocity update: depth-dependent log-factors on Vp and Vs (the S12 parameterisation, now for both phases),
with Frechet derivatives from ray integrals through the same fields, and hypocentres and origin times removed
per event by parameter separation (Pavlis & Booker 1980). Iterating relocation and update is the
minimum-1D-model scheme of Kissling et al. (1994), applied as a perturbation to the 3D model.

Topography: cells more than ``skin`` above the DEM get the speed of sound in air, so rays cannot shortcut
through air at rock speed; the skin (rock velocity from the cell below) keeps every station, which lies within
+-70 m of the DEM, inside rock at the 500 m grid spacing. Hypocentres are bounded below the DEM.

Coordinates inside this module are (x, y, d), metres, with d = -z (NAVD88 elevation) positive down.
"""

from __future__ import annotations

import os
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd
from scipy.linalg import block_diag
from scipy.ndimage import map_coordinates
from scipy.optimize import least_squares

from rainier3d.validate.calibrate import second_difference

# Pick uncertainty per phase (s): the RMS of PNSN's own location residuals for these picks
# (outputs/pnsn_report.txt, rms_pnsn_reported), used to weight P against S.
SIGMA = {"P": 0.14, "S": 0.23}
HUBER_K = 1.5  # in units of sigma
REJECT_K = 5.0  # picks beyond this many sigma get zero weight
AIR_V = 343.0  # m/s, sound at 20 C; any value well below the slowest rock (~1500 m/s) acts the same
GROUND_TOL = 50.0  # m; hypocentres may sit this far above the DEM before the ground penalty acts


class Grid:
    """The S6 grid in (x, y, d) order: ``xs``, ``ys`` ascending, ``zs`` descending (so d ascending)."""

    def __init__(self, xs, ys, zs, dx):
        self.xs, self.ys, self.zs, self.dx = xs, ys, zs, float(dx)
        self.o = np.array([xs[0], ys[0], -zs[0]], float)
        self.shape = (xs.size, ys.size, zs.size)
        self.hi = self.o + self.dx * (np.array(self.shape) - 1)

    @staticmethod
    def xyd(a_zxy: np.ndarray) -> np.ndarray:
        """(nz, nx, ny) arrays of ``pnsn.model_on_grid`` -> (nx, ny, nd)."""
        return np.ascontiguousarray(np.transpose(a_zxy, (1, 2, 0)))

    def sample(self, f: np.ndarray, p: np.ndarray) -> np.ndarray:
        idx = ((np.atleast_2d(p) - self.o) / self.dx).T
        return map_coordinates(f, idx, order=1, mode="nearest", output=np.float64)

    def grad(self, f: np.ndarray, p: np.ndarray) -> np.ndarray:
        """Central differences of the trilinear interpolant, half a cell apart."""
        p = np.atleast_2d(p).astype(float)
        h = self.dx / 2
        out = np.empty_like(p)
        for k in range(3):
            e = np.zeros(3)
            e[k] = h
            out[:, k] = (self.sample(f, p + e) - self.sample(f, p - e)) / (2 * h)
        return out

    def sample2d(self, f_xy: np.ndarray, p: np.ndarray) -> np.ndarray:
        idx = ((np.atleast_2d(p)[:, :2] - self.o[:2]) / self.dx).T
        return map_coordinates(f_xy, idx, order=1, mode="nearest", output=np.float64)


def ground_on_grid(tree, grid: Grid) -> np.ndarray:
    """(nx, ny) DEM elevation (m NAVD88) at the grid nodes, from the model's /surface node."""
    e = tree["surface"].to_dataset()["elevation"]
    # edge nodes lie just outside the raster: sample them at the nearest raster edge
    xs = np.clip(grid.xs, float(e.x.min()), float(e.x.max()))
    ys = np.clip(grid.ys, float(e.y.min()), float(e.y.max()))
    g = e.interp(x=("gx", xs), y=("gy", ys)).transpose("gx", "gy").values.astype(float)
    return g


def with_topography(vel_zxy: np.ndarray, grid: Grid, ground: np.ndarray, skin_cells: int = 1) -> np.ndarray:
    """Air above ground + skin_cells * dx set to AIR_V; skin_cells < 0 keeps the rock-filled air of S6."""
    if skin_cells < 0:
        return vel_zxy
    air = grid.zs[:, None, None] > ground[None] + skin_cells * grid.dx
    return np.where(air, AIR_V, vel_zxy)


# ---------------------------------------------------------------- travel-time fields
def _field_one(args):
    import pykonal.solver

    vel_xyd, o, dx, src = args
    s = pykonal.solver.PointSourceSolver(coord_sys="cartesian")
    s.velocity.min_coords = o
    s.velocity.node_intervals = dx, dx, dx
    s.velocity.npts = vel_xyd.shape
    s.velocity.values = vel_xyd
    s.src_loc = np.asarray(src, dtype=float)
    s.solve()
    return s.traveltime.values.astype(np.float32)


def fields(vel_xyd: np.ndarray, grid: Grid, stations_xyd: np.ndarray, workers: int = 8) -> np.ndarray:
    """(nsta, nx, ny, nd) float32 travel-time fields, one per station (reciprocity)."""
    v = np.ascontiguousarray(vel_xyd, dtype=float)
    jobs = [(v, grid.o, grid.dx, tuple(s)) for s in stations_xyd]
    with ProcessPoolExecutor(max_workers=min(workers, os.cpu_count() or 1)) as ex:
        return np.stack(list(ex.map(_field_one, jobs)))


# ---------------------------------------------------------------- location
def _huber_w(rn: np.ndarray) -> np.ndarray:
    a = np.abs(rn)
    w = np.where(a <= HUBER_K, 1.0, HUBER_K / np.maximum(a, 1e-12))
    return np.where(a > REJECT_K, 0.0, w)


def locate_event(
    T: dict, grid: Grid, ph: np.ndarray, st: np.ndarray, t_obs: np.ndarray, prior, half=15000.0, ground=None
):
    """Hypocentre (x, y, d), origin-time shift t0 (s, relative to the catalogue origin) and residuals.

    ``T[phase]`` is (nsta, nx, ny, nd); ``ph``, ``st``, ``t_obs`` describe the picks of one event, with t_obs
    measured from the catalogue origin time. Grid search (L1, median origin time) within ``half`` m of the
    prior horizontally and over the full depth range, then Huber Gauss-Newton on interpolated times. With
    ``ground`` (nx, ny DEM elevation), the search excludes nodes above the ground and the refinement adds a
    stiff penalty row (1 sigma per 10 m) for hypocentres more than GROUND_TOL above it.
    """
    sig = np.array([SIGMA[p] for p in ph])
    i0, j0 = (np.floor((np.asarray(prior[:2]) - half - grid.o[:2]) / grid.dx)).astype(int)
    i1, j1 = (np.ceil((np.asarray(prior[:2]) + half - grid.o[:2]) / grid.dx)).astype(int) + 1
    i0, j0 = max(i0, 0), max(j0, 0)
    stack = np.stack([T[p][s, i0:i1, j0:j1, :] for p, s in zip(ph, st, strict=True)]).astype(np.float64)
    r = t_obs[:, None, None, None] - stack
    r -= np.median(r, axis=0, keepdims=True)
    mis = np.sum(np.abs(r) / sig[:, None, None, None], axis=0)
    if ground is not None:
        g_sub = ground[i0 : i0 + mis.shape[0], j0 : j0 + mis.shape[1]]
        mis = np.where(grid.zs[None, None, :] > g_sub[:, :, None], np.inf, mis)
    a, b, c = np.unravel_index(np.argmin(mis), mis.shape)
    p0 = grid.o + grid.dx * np.array([i0 + a, j0 + b, c])
    t00 = float(np.median(t_obs - stack[:, a, b, c]))

    def pred(q):
        return np.array([grid.sample(T[p][s], q[None, :3])[0] for p, s in zip(ph, st, strict=True)])

    def above(q):  # metres above the tolerated ground level (> 0 violates)
        return -q[2] - (grid.sample2d(ground, q[None])[0] + GROUND_TOL)

    def fun(q):
        r = (t_obs - q[3] - pred(q)) / sig
        return r if ground is None else np.r_[r, max(above(q), 0.0) / 10.0]

    def jac(q):
        g = np.stack([grid.grad(T[p][s], q[None, :3])[0] for p, s in zip(ph, st, strict=True)])
        J = -np.column_stack([g, np.ones(len(ph))]) / sig[:, None]
        if ground is None:
            return J
        row = np.array([0.0, 0.0, -0.1 if above(q) > 0 else 0.0, 0.0])
        return np.vstack([J, row])

    lo = np.r_[grid.o, -np.inf]
    hi = np.r_[grid.hi, np.inf]
    q0 = np.clip(np.r_[p0, t00], lo + 1e-6, hi - 1e-6)
    sol = least_squares(
        fun, q0, jac=jac, bounds=(lo, hi), loss="huber", f_scale=HUBER_K, x_scale=[1e3, 1e3, 1e3, 0.1]
    )
    q = sol.x
    res = t_obs - q[3] - pred(q)
    w = _huber_w(res / sig)
    J = jac(q)[: len(ph)] * np.sqrt(w)[:, None]
    dof = max(int((w > 0).sum()) - 4, 1)
    s2 = float(np.sum(w * (res / sig) ** 2) / dof)
    try:
        cov = np.linalg.inv(J.T @ J) * s2
    except np.linalg.LinAlgError:
        cov = np.full((4, 4), np.nan)
    return {
        "x": q[0],
        "y": q[1],
        "d": q[2],
        "t0": q[3],
        "sx": np.sqrt(cov[0, 0]),
        "sy": np.sqrt(cov[1, 1]),
        "sd": np.sqrt(cov[2, 2]),
        "st0": np.sqrt(cov[3, 3]),
        "res": res,
        "w": w,
        "grid_d": p0[2],
        "above_ground_m": np.nan if ground is None else float(above(q) + GROUND_TOL),
    }


def locate_all(
    T: dict, grid: Grid, picks: pd.DataFrame, events: pd.DataFrame, ground=None
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Relocate every event; returns the catalogue and the picks with ``res`` and ``w`` columns."""
    cat, parts = [], []
    keys = ("x", "y", "d", "t0", "sx", "sy", "sd", "st0", "above_ground_m")
    for e, g in picks.groupby("event", sort=False):
        ev = events.loc[e]
        out = locate_event(
            T, grid, g.phase.values, g.si.values, g.tt_obs.values, (ev.x, ev.y, ev.d), ground=ground
        )
        cat.append({"event": e, **{k: out[k] for k in keys}})
        parts.append(g.assign(res=out["res"], w=out["w"]))
    return pd.DataFrame(cat).set_index("event"), pd.concat(parts)


# ---------------------------------------------------------------- Frechet derivatives
def hat_weights(depth: np.ndarray, knots: np.ndarray) -> np.ndarray:
    """(n, K) weights of the piecewise-linear log-factor on its knots (constant beyond the ends)."""
    eye = np.eye(knots.size)
    d = np.clip(depth, knots[0], knots[-1])
    return np.stack([np.interp(d, knots, eye[k]) for k in range(knots.size)], axis=1)


def trace_rays(Tst: np.ndarray, grid: Grid, sta: np.ndarray, src: np.ndarray, step: float | None = None):
    """Rays from each source down grad T to the station: midpoints (m, 3), lengths (m,), ray index (m,), and a
    mask of rays that did not reach the station.

    The last two cells are closed with a straight segment, where the field is least accurate. A ray still
    running after the step budget (trapped where slow air meets rock, where grad T can turn back on itself) is
    closed with a straight segment from where it stopped, and flagged.
    """
    h = step or grid.dx / 4
    pos = np.array(src, float)
    active = np.ones(len(pos), bool)
    pts, lens, ids = [], [], []

    def close(i):
        seg = sta - pos[i]
        n = 8
        f = (np.arange(n) + 0.5) / n
        pts.append(pos[i] + f[:, None] * seg)
        lens.append(np.full(n, np.linalg.norm(seg) / n))
        ids.append(np.full(n, i))

    for _ in range(int(4 * (np.linalg.norm(grid.hi - grid.o) / h))):
        a = np.flatnonzero(active)
        if a.size == 0:
            break
        dist = np.linalg.norm(pos[a] - sta, axis=1)
        near = dist < 2 * grid.dx
        for i in a[near]:
            close(i)
        active[a[near]] = False
        a = a[~near]
        if a.size == 0:
            break
        g = grid.grad(Tst, pos[a])
        g /= np.maximum(np.linalg.norm(g, axis=1, keepdims=True), 1e-12)
        new = pos[a] - h * g
        pts.append(0.5 * (pos[a] + new))
        lens.append(np.full(a.size, h))
        ids.append(a)
        pos[a] = new
    failed = active.copy()
    for i in np.flatnonzero(failed):
        close(i)
    return np.concatenate(pts), np.concatenate(lens), np.concatenate(ids), failed


def ray_kernels(Tst, grid, sta, src, vel_xyd, taper_xyd, depth_xyd, knots):
    """dT/dm_k (n_src, K) for V = V0 exp(taper * m(depth)), the ray travel time (n_src,) as a check, and the
    mask of rays closed by a straight segment (see trace_rays)."""
    p, ln, ids, failed = trace_rays(Tst, grid, sta, src)
    s = 1.0 / grid.sample(vel_xyd, p)
    wt = grid.sample(taper_xyd, p)[:, None] * hat_weights(grid.sample(depth_xyd, p), knots)
    K = np.zeros((len(src), knots.size))
    np.add.at(K, ids, -(wt * (s * ln)[:, None]))
    t_ray = np.bincount(ids, weights=s * ln, minlength=len(src))
    return K, t_ray, failed


# ---------------------------------------------------------------- model update
def separated_system(picks: pd.DataFrame, cat: pd.DataFrame, T: dict, grid: Grid, K: np.ndarray, nk: int):
    """Per event: rows scaled by sqrt(w)/sigma, then projected on the null space of the hypocentre partials.

    ``K`` (n_picks, 2 nk) holds dT/dm for every pick (P columns first). Returns {event: (A', r')}.
    """
    out = {}
    for e, g in picks.groupby("event", sort=False):
        q = cat.loc[e, ["x", "y", "d"]].values.astype(float)
        H = np.column_stack(
            [
                np.stack([grid.grad(T[p][s], q[None])[0] for p, s in zip(g.phase, g.si, strict=True)]),
                np.ones(len(g)),
            ]
        )
        sc = np.sqrt(g.w.values) / np.array([SIGMA[p] for p in g.phase])
        keep = sc > 0
        if keep.sum() <= 5:
            continue
        H, A, r = (
            H[keep] * sc[keep, None],
            K[g.row.values][keep] * sc[keep, None],
            g.res.values[keep] * sc[keep],
        )
        Q, _ = np.linalg.qr(H, mode="complete")
        Q2 = Q[:, 4:]
        out[e] = (Q2.T @ A, Q2.T @ r)
    return out


def gn_update(system: dict, events, m: np.ndarray, lam_s: float, lam_d: float) -> np.ndarray:
    """One regularised Gauss-Newton step on the total log-factors m (P knots then S knots).

    Smoothing (second differences within each phase) and damping towards m = 0 are scaled by the mean
    diagonal of A'^T A', so the weights are relative to the data term.
    """
    A = np.vstack([system[e][0] for e in events if e in system])
    r = np.concatenate([system[e][1] for e in events if e in system])
    nk = m.size // 2
    D = second_difference(nk)
    DD = block_diag(D.T @ D, D.T @ D)
    N = A.T @ A
    sc = np.trace(N) / m.size
    L = sc * (lam_s * DD + lam_d * np.eye(m.size))
    return m + np.linalg.solve(N + L, A.T @ r - L @ m)


def linear_score(system: dict, events, dm: np.ndarray) -> float:
    """Normalised RMS of the separated residuals of ``events`` after a model change dm (linearised)."""
    num, n = 0.0, 0
    for e in events:
        if e in system:
            A, r = system[e]
            num += float(np.sum((r - A @ dm) ** 2))
            n += r.size
    return float(np.sqrt(num / max(n, 1)))


def residual_stats(picks: pd.DataFrame) -> dict:
    """RMS and median |r| per phase after relocation, over picks with non-zero weight, and rejection rate."""
    out = {}
    for ph, g in picks.groupby("phase"):
        k = g.w > 0
        out[ph] = {
            "n": int(k.sum()),
            "rms_s": float(np.sqrt(np.mean(g.res[k] ** 2))),
            "median_abs_s": float(np.median(np.abs(g.res[k]))),
            "rejected": int((~k).sum()),
        }
    return out


# ---------------------------------------------------------------- set-up shared by S13 and S14
def setup(dom, events_csv, min_picks: int = 6, min_p: int = 4):
    """Grid, picks (with station index ``si``, row index ``row``), station (x, y, d), events (prior x, y, d).

    Events need ``min_picks`` picks, ``min_p`` of them P, to leave degrees of freedom after the 4 hypocentral
    parameters. Catalogue depth is taken as km below sea level (so d = depth), as in S6; the relocation
    itself is in NAVD88 elevation and does not depend on that convention beyond the starting point.
    """
    from rainier3d.validate import pnsn

    vc = dom.cfg["validation"]
    picks, stations, ev = pnsn.prepare(dom, events_csv)
    xs, ys, zs = pnsn.grid_axes(dom, vc["dx"], vc["z_top"], vc["z_bot"])
    grid = Grid(xs, ys, zs, vc["dx"])
    sidx = {(n, s): i for i, (n, s) in enumerate(zip(stations.net, stations.sta, strict=True))}
    picks = picks.assign(si=[sidx[(n, s)] for n, s in zip(picks.net, picks.sta, strict=True)])
    n = picks.groupby("event").phase.agg(n="size", n_p=lambda s: (s == "P").sum())
    keep = n[(n.n >= min_picks) & (n.n_p >= min_p)].index
    picks = picks[picks.event.isin(keep)].reset_index(drop=True)
    picks["row"] = np.arange(len(picks))
    events = ev[ev.event.isin(keep)].assign(d=lambda e: -e.z).set_index("event")
    sta_xyd = np.column_stack([stations.x, stations.y, -stations.elev])
    return grid, picks, stations, sta_xyd, events


def kernels_all(T: dict, grid: Grid, picks, cat, sta_xyd, vel: dict, taper, depth, knots) -> tuple:
    """dT/dm for every pick (n_picks, 2 K; P knots then S knots), |t_ray - t_field| / t_field per pick, and
    the number of rays closed by a straight segment."""
    nk = knots.size
    K = np.zeros((len(picks), 2 * nk))
    rel = np.full(len(picks), np.nan)
    n_failed = 0
    for j, ph in enumerate(("P", "S")):
        for s, g in picks[picks.phase == ph].groupby("si"):
            src = cat.loc[g.event, ["x", "y", "d"]].values.astype(float)
            k, t_ray, failed = ray_kernels(T[ph][s], grid, sta_xyd[s], src, vel[ph], taper, depth, knots)
            n_failed += int(failed.sum())
            K[g.row.values, j * nk : (j + 1) * nk] = k
            t_f = grid.sample(T[ph][s], src)
            rel[g.row.values] = np.abs(t_ray - t_f) / np.maximum(t_f, 1e-6)
    return K, rel, n_failed
