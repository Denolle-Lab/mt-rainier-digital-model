"""Station velocities with MIDAS (Blewitt et al., 2016, JGR 121, doi:10.1002/2015JB012552).

MIDAS takes the median of slopes between data pairs one year apart (so seasonal signals cancel and steps
affect few pairs), removes pairs beyond 2 scaled MADs of that median, and takes the median again. Its
uncertainty is 1.2533 * 1.4826 * MAD / sqrt(N/4), the formula of the paper."""

from __future__ import annotations

import numpy as np


def midas(
    t: np.ndarray, x: np.ndarray, tol: float = 0.001, steps: np.ndarray | None = None
) -> tuple[float, float, int]:
    """Velocity (units of x per year), its sigma, and the number of pairs. ``t`` in decimal years, sorted.

    Pairs are made forward and backward in time (the 'no-steps' pair selection of the paper); a pair that
    spans a known step is skipped.
    """
    t, x = np.asarray(t, float), np.asarray(x, float)
    ok = np.isfinite(t) & np.isfinite(x)
    t, x = t[ok], x[ok]
    steps = np.asarray([] if steps is None else steps, float)
    slopes = []
    for direction in (1, -1):
        idx = np.arange(t.size)[::direction]
        tt = t[idx]
        j = 0
        for i in range(tt.size):
            target = tt[i] + direction * 1.0
            while j < tt.size and direction * (tt[j] - target) < -tol:
                j += 1
            if j >= tt.size:
                break
            if abs(tt[j] - target) <= tol:
                a, b = idx[i], idx[j]
                lo, hi = sorted((t[a], t[b]))
                if not np.any((steps > lo) & (steps <= hi)):
                    slopes.append((x[b] - x[a]) / (t[b] - t[a]))
    s = np.asarray(slopes)
    if s.size < 10:
        return np.nan, np.nan, int(s.size)
    med = np.median(s)
    mad = 1.4826 * np.median(np.abs(s - med))
    s = s[np.abs(s - med) < 2 * mad] if mad > 0 else s
    med = np.median(s)
    mad = 1.4826 * np.median(np.abs(s - med))
    sig = 1.2533 * mad / np.sqrt(s.size / 4)
    return float(med), float(sig), int(s.size)


def trajectory(t, x, steps=(), t_ref: float = 2015.0, n_iter: int = 5, k: float = 1.345):
    """Robust (Huber IRLS) fit x(t) = a + b (t - t_ref) + annual + semiannual + sum_j c_j H(t - t_j).

    Returns the coefficients (``a``, ``b``, ``ann_s``, ``ann_c``, ``semi_s``, ``semi_c``, ``steps``) and
    ``corrected``: x with the fitted steps removed and the model value at t_ref subtracted, so series of
    different lengths share one reference epoch.
    """
    t, x = np.asarray(t, float), np.asarray(x, float)
    steps = [s for s in np.atleast_1d(np.asarray(steps, float)) if t.min() < s < t.max()]
    w2 = 2 * np.pi * t
    cols = [np.ones_like(t), t - t_ref, np.sin(w2), np.cos(w2), np.sin(2 * w2), np.cos(2 * w2)]
    cols += [(t >= s).astype(float) for s in steps]
    A = np.column_stack(cols)
    w = np.ones_like(t)
    p = np.zeros(A.shape[1])
    for _ in range(n_iter):
        p, *_ = np.linalg.lstsq(A * w[:, None], x * w, rcond=None)
        r = x - A @ p
        s = 1.4826 * np.median(np.abs(r - np.median(r))) or 1e-9
        u = np.abs(r) / (k * s)
        w = np.sqrt(np.where(u <= 1, 1.0, 1.0 / u))
    step_part = A[:, 6:] @ p[6:] if steps else 0.0
    ref = p[0] + p[2] * np.sin(2 * np.pi * t_ref) + p[3] * np.cos(2 * np.pi * t_ref)
    ref += p[4] * np.sin(4 * np.pi * t_ref) + p[5] * np.cos(4 * np.pi * t_ref)
    return {
        "a": p[0],
        "b": p[1],
        "ann_s": p[2],
        "ann_c": p[3],
        "semi_s": p[4],
        "semi_c": p[5],
        "steps": dict(zip(steps, p[6:], strict=True)),
        "corrected": x - step_part - ref,
        "residual": x - A @ p,  # trend, seasonal terms and steps removed: transients and noise
        "rms": float(np.sqrt(np.mean((x - A @ p) ** 2))),
    }
