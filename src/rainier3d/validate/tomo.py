"""Local-earthquake tomography (S37): ln Vp and ln Vs perturbations of the fused model on a coarse node grid.

    V = V_model * exp(w(d_bed) m(x, y, d)),   m trilinear between nodes, one field per phase

The forward model and the location are those of S13 (rainier3d.validate.locate): pykonal fields per station
on the S6 grid with air above the DEM, relocation below the ground, rays down grad T. The perturbation is
applied to rock only (air keeps its speed), so dT/dm = -integral of s w_k dl over the rock part of each ray,
with w_k the trilinear weight of node k. Hypocentres and origin times are removed per event by projecting each
event's rows on the complement of its hypocentre partials (Pavlis & Booker 1980). The regularised system

    [ A' ; sqrt(lam_s) L ; sqrt(lam_d) I ] dm = [ r' ; -sqrt(lam_s) L m ; -sqrt(lam_d) m ]

(L: second differences along x, y and d within each phase) is solved by LSQR, as in SIMUL-type tomography
(Thurber 1983) with the damping and smoothing scaled by the mean squared column norm of A'.

w(d_bed) (``cz_taper``) is 0 in the top ``z0`` m below the ground or the glacier bed, the critical-zone
columns of S4, and rises linearly to 1 at ``z1`` m: the tomography leaves the critical zone, built from rock
physics, as it is.

Coordinates are (x, y, d) metres, d = -z positive down, as in rainier3d.validate.locate.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import scipy.sparse as sp
from scipy.sparse.linalg import lsqr

from rainier3d.validate.locate import AIR_V, SIGMA, Grid, trace_rays


class Nodes:
    """Node grid of the perturbation: axes ``xs``, ``ys``, ``ds`` (ascending, metres); m beyond the ends is
    that of the end nodes."""

    def __init__(self, xs, ys, ds):
        self.axes = [np.asarray(a, float) for a in (xs, ys, ds)]
        self.shape = tuple(a.size for a in self.axes)
        self.n = int(np.prod(self.shape))

    @staticmethod
    def _axis(ax: np.ndarray, p: np.ndarray):
        i = np.clip(np.searchsorted(ax, p) - 1, 0, ax.size - 2)
        t = np.clip((p - ax[i]) / (ax[i + 1] - ax[i]), 0.0, 1.0)
        return i, t

    def weights(self, p: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """(n_points, 8) node indices and trilinear weights of points p (n, 3)."""
        (ix, tx), (iy, ty), (iz, tz) = (self._axis(a, p[:, k]) for k, a in enumerate(self.axes))
        idx, w = [], []
        for a in (0, 1):
            for b in (0, 1):
                for c in (0, 1):
                    idx.append(np.ravel_multi_index((ix + a, iy + b, iz + c), self.shape))
                    w.append((tx if a else 1 - tx) * (ty if b else 1 - ty) * (tz if c else 1 - tz))
        return np.stack(idx, 1), np.stack(w, 1)

    def _axis_matrix(self, k: int, g: np.ndarray) -> np.ndarray:
        i, t = self._axis(self.axes[k], g)
        W = np.zeros((g.size, self.axes[k].size))
        W[np.arange(g.size), i] = 1 - t
        W[np.arange(g.size), i + 1] += t
        return W

    def on_grid(self, m: np.ndarray, grid: Grid) -> np.ndarray:
        """Node field m (n,) at the nodes of the S6 grid, (nx, ny, nd)."""
        Wx, Wy, Wd = (self._axis_matrix(k, g) for k, g in enumerate((grid.xs, grid.ys, -grid.zs)))
        return np.einsum("ai,bj,ck,ijk->abc", Wx, Wy, Wd, m.reshape(self.shape), optimize=True)

    def second_differences(self) -> sp.csr_matrix:
        """Stacked second-difference operators along x, y and d (rows: interior triples of each axis), with
        the coefficients h1 h2 f'' of uneven spacing (1, -2, 1 when even), so linear fields cost nothing."""
        ops = []
        eye = [sp.identity(s, format="csr") for s in self.shape]
        for k, s in enumerate(self.shape):
            if s < 3:
                continue
            h = np.diff(self.axes[k])
            h1, h2 = h[:-1], h[1:]
            D = sp.diags(
                [2 * h2 / (h1 + h2), -2.0 * np.ones(s - 2), 2 * h1 / (h1 + h2)], [0, 1, 2], shape=(s - 2, s)
            )
            D = D.tocsr()
            mats = [eye[0], eye[1], eye[2]]
            mats[k] = D
            ops.append(sp.kron(sp.kron(mats[0], mats[1]), mats[2], format="csr"))
        return sp.vstack(ops, format="csr")


def kernels(
    T: dict,
    grid: Grid,
    picks: pd.DataFrame,
    cat: pd.DataFrame,
    sta_xyd,
    vel: dict,
    nodes: Nodes,
    density: bool = False,
    keep_rows=(),
    taper_xyd=None,
):
    """dT/dm (n_picks, 2 n; P nodes then S nodes) as a sparse matrix, the derivative weight sum per node
    (2 n,: ray length in metres weighted by the trilinear weights) and the number of rays closed straight.

    ``density``: also the ray density on the eikonal grid, per phase: ray length (m) and number of distinct
    rays in each cell (nearest node), rock only. ``keep_rows``: pick rows whose ray paths are returned (for
    figures), as {row: (n, 3) points from the source to the station}. ``taper_xyd``: the weight of the
    perturbation on the eikonal grid (``cz_taper``), which multiplies the kernels and the derivative weight
    sum at every ray point."""
    rows, cols, vals = [], [], []
    dws = np.zeros(2 * nodes.n)
    n_failed = 0
    dens = {ph: {"length": np.zeros(grid.shape), "rays": np.zeros(grid.shape)} for ph in ("P", "S")}
    keep, paths = set(keep_rows), {}
    for j, ph in enumerate(("P", "S")):
        for s, g in picks[picks.phase == ph].groupby("si"):
            src = cat.loc[g.event, ["x", "y", "d"]].values.astype(float)
            p, ln, ids, failed = trace_rays(T[ph][s], grid, sta_xyd[s], src)
            n_failed += int(failed.sum())
            for i in np.flatnonzero(np.isin(g.row.values, list(keep))) if keep else ():
                paths[int(g.row.values[i])] = np.vstack([src[i], p[ids == i], sta_xyd[s]])
            v = grid.sample(vel[ph], p)
            rock = v > 1.01 * AIR_V  # the perturbation acts on rock only
            p, ln, ids, v = p[rock], ln[rock], ids[rock], v[rock]
            if density:
                c = np.clip(np.rint((p - grid.o) / grid.dx).astype(int), 0, np.array(grid.shape) - 1)
                lin = np.ravel_multi_index(c.T, grid.shape)
                np.add.at(dens[ph]["length"].reshape(-1), lin, ln)
                u = np.unique(lin.astype(np.int64) * len(src) + ids)  # one count per ray and cell
                np.add.at(dens[ph]["rays"].reshape(-1), u // len(src), 1.0)
            k, w = nodes.weights(p)
            if taper_xyd is not None:
                w = w * grid.sample(taper_xyd, p)[:, None]
            rows.append(np.repeat(g.row.values[ids], 8))
            cols.append((k + j * nodes.n).ravel())
            vals.append((-(ln / v)[:, None] * w).ravel())
            np.add.at(dws, (k + j * nodes.n).ravel(), (ln[:, None] * w).ravel())
    K = sp.coo_matrix(
        (np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=(len(picks), 2 * nodes.n)
    ).tocsr()
    if density or keep:
        return K, dws, n_failed, dens, paths
    return K, dws, n_failed


def fields_timed(vel_xyd: np.ndarray, grid: Grid, stations_xyd: np.ndarray, limit_s=None, workers: int = 8):
    """``locate.fields`` with a time limit (s) on the whole set: past it the workers are stopped and
    TimeoutError is raised, rather than a stalled solve holding the inversion."""
    import os
    from concurrent.futures import ProcessPoolExecutor, wait

    from rainier3d.validate.locate import _field_one

    v = np.ascontiguousarray(vel_xyd, dtype=float)
    ex = ProcessPoolExecutor(max_workers=min(workers, os.cpu_count() or 1))
    futs = [ex.submit(_field_one, (v, grid.o, grid.dx, tuple(s))) for s in stations_xyd]
    done, pending = wait(futs, timeout=limit_s)
    if pending:
        for p in list(getattr(ex, "_processes", {}).values()):
            p.terminate()
        ex.shutdown(wait=False, cancel_futures=True)
        raise TimeoutError(f"{len(pending)} of {len(futs)} eikonal solves unfinished after {limit_s:.0f} s")
    ex.shutdown()
    return np.stack([f.result() for f in futs])


def cz_taper(depth_below_bed, z0: float, z1: float):
    """Weight of the perturbation: 0 in the critical zone (less than z0 below the ground or the glacier bed),
    rising linearly to 1 at z1, so that the critical-zone columns and their petrophysics stay as built."""
    return np.clip((np.asarray(depth_below_bed, float) - z0) / max(z1 - z0, 1e-9), 0.0, 1.0)


def model_on_grid_slowness(tree, var: str, grid: Grid, phase: str) -> np.ndarray:
    """(nz, nx, ny) velocity of the model on the eikonal grid, as ``pnsn.model_on_grid`` but with each node in
    the depth range of L1 taking the slowness average of the L1 cells (rock only) whose centres lie within
    half a node spacing of it, so that thin layers (the critical zone) keep their vertical travel time on a
    grid coarser than 50 m. Horizontally the L1 cell nearest to the node is used."""
    from rainier3d.validate import pnsn

    xs, ys, zs = grid.xs, grid.ys, grid.zs
    out = pnsn.model_on_grid(tree, var, xs, ys, zs, phase)
    l1 = tree["L1"].to_dataset()
    zc, dzl = l1.z.values, float(l1.attrs["dz"])
    v = l1[var].sel(x=xs, y=ys, method="nearest").transpose("z", "x", "y").values  # (nzl, nx, ny)
    slow = np.where(np.isfinite(v) & (v > 0), 1.0 / np.where(v > 0, v, 1.0), 0.0)
    rock = (np.isfinite(v) & (v > 0)).astype(float)
    top, bot = zc.max() + dzl / 2, zc.min() - dzl / 2
    for kz, z in enumerate(zs):
        if not (bot <= z <= top) or grid.dx <= dzl:
            continue
        sel = np.abs(zc - z) < grid.dx / 2
        n = rock[sel].sum(0)
        avg = np.where(n > 0, slow[sel].sum(0) / np.maximum(n, 1), np.nan)
        out[kz] = np.where(np.isfinite(avg), 1.0 / np.where(np.isfinite(avg), avg, 1.0), out[kz])
    return out


def separated(picks: pd.DataFrame, cat: pd.DataFrame, T: dict, grid: Grid, K: sp.csr_matrix):
    """Rows scaled by sqrt(w)/sigma and projected, event by event, on the complement of the hypocentre and
    origin-time partials: (A' sparse, r', event of each row). ||P (r - A m)|| equals the Q2 form of S13."""
    blocks, rs, evs = [], [], []
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
        H = H[keep] * sc[keep, None]
        Ae = K[g.row.values[keep]].multiply(sc[keep, None]).tocsc()
        used = np.flatnonzero(np.diff(Ae.indptr))
        Ad = Ae[:, used].toarray()
        Q1, _ = np.linalg.qr(H)
        Ad = Ad - Q1 @ (Q1.T @ Ad)
        r = g.res.values[keep] * sc[keep]
        r = r - Q1 @ (Q1.T @ r)
        blk = sp.csr_matrix(Ad)
        blk = sp.csr_matrix((blk.data, used[blk.indices], blk.indptr), shape=(Ad.shape[0], K.shape[1]))
        blocks.append(blk)
        rs.append(r)
        evs.append(np.full(r.size, e, dtype=object))
    return sp.vstack(blocks, format="csr"), np.concatenate(rs), np.concatenate(evs)


def regularised_step(A, r, m, L, lam_s: float, lam_d: float, iter_lim: int = 400) -> np.ndarray:
    """Model change dm minimising ||A dm - r||^2 + lam_s ||L (m + dm)||^2 + lam_d ||m + dm||^2, with lam_s and
    lam_d relative to the mean squared column norm of A over the columns rays reach."""
    cn = np.asarray(A.multiply(A).sum(0)).ravel()
    sc = float(np.mean(cn[cn > 0])) if (cn > 0).any() else 1.0
    a_s, a_d = np.sqrt(lam_s * sc), np.sqrt(lam_d * sc)
    M = sp.vstack([A, a_s * L, a_d * sp.identity(m.size, format="csr")], format="csr")
    b = np.concatenate([r, -a_s * (L @ m), -a_d * m])
    return lsqr(M, b, atol=1e-6, btol=1e-6, iter_lim=iter_lim)[0]


def score(A, r, rows: np.ndarray, dm: np.ndarray) -> float:
    """Normalised RMS of the separated residuals in ``rows`` after the model change dm (linearised)."""
    e = r[rows] - A[rows] @ dm
    return float(np.sqrt(np.mean(e**2))) if rows.any() else float("nan")


def checkerboard(nodes: Nodes, cell_m: float, amp: float, phase_sign=(1.0, -1.0)) -> np.ndarray:
    """+-amp pattern on the nodes (P then S), alternating every ``cell_m`` along x, y and d; S of opposite
    sign so that P and S leakage shows."""
    ix, iy, iz = np.meshgrid(*[np.floor(a / cell_m).astype(int) for a in nodes.axes], indexing="ij")
    pat = amp * np.where((ix + iy + iz) % 2 == 0, 1.0, -1.0).ravel()
    return np.concatenate([phase_sign[0] * pat, phase_sign[1] * pat])
