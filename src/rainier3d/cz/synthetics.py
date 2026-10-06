"""Seismic synthetics of a critical-zone column: fundamental-mode Rayleigh phase velocity, its depth
sensitivity to Vs, dv/v for water-table scenarios, and a quarter-wavelength resonance (disba, BSD-3)."""

from __future__ import annotations

import numpy as np
from disba import PhaseDispersion, PhaseSensitivity
from disba._exception import DispersionError


def _model(col: dict) -> np.ndarray:
    """disba units: thickness km (0 for the half-space), vp, vs km/s, density g/cm3."""
    return np.column_stack([col["thickness"] / 1e3, col["vp"] / 1e3, col["vs"] / 1e3, col["rho"] / 1e3])


def phase_velocity(col: dict, freqs) -> np.ndarray:
    """Rayleigh fundamental-mode phase velocity (m/s) at each frequency; NaN where it cannot be computed."""
    f = np.asarray(freqs, float)
    order = np.argsort(1 / f)
    out = np.full(f.size, np.nan)
    try:
        r = PhaseDispersion(*_model(col).T)(1 / f[order], mode=0, wave="rayleigh")
    except DispersionError:
        return out
    got = dict(zip(np.round(r.period, 9), r.velocity * 1e3, strict=True))
    for i in order:
        out[i] = got.get(round(1 / f[i], 9), np.nan)
    return out


def kernel_depths(col: dict, freqs, fractions) -> np.ndarray:
    """(freq, fraction): depth (m) above which the given share of the |dc/dVs| sensitivity lies."""
    m = _model(col)
    ps = PhaseSensitivity(*m.T)
    out = np.full((len(freqs), len(fractions)), np.nan)
    bottom = col["top"] + col["thickness"]
    for i, f in enumerate(freqs):
        try:
            k = np.abs(ps(1 / f, mode=0, wave="rayleigh", parameter="velocity_s").kernel)
        except DispersionError:
            continue
        c = np.cumsum(k) / k.sum()
        for j, q in enumerate(fractions):
            out[i, j] = bottom[min(np.searchsorted(c, q), len(c) - 1)]
    return out


def quarter_wavelength_f0(col: dict) -> float:
    """Resonance of the layers above fresh rock: 1 / (4 sum h / Vs)."""
    z4 = col["boundaries"][3]
    above = col["top"] < z4
    h = np.minimum(col["top"][above] + col["thickness"][above], z4) - col["top"][above]
    return float(1 / (4 * np.sum(h / col["vs"][above])))


def stack(fine: dict, l1_depth, l1_vp, l1_vs, l1_rho) -> dict:
    """A layered column for disba: the fine critical-zone column of the model
    (rainier3d.cz.level.Context.column) and, below its base, the model's L1 cells (depth of the cell centres
    below the column top, m/s, kg/m3); the deepest cell is the half-space."""
    base = float(np.sum(fine["dz"]))
    l1_depth = np.asarray(l1_depth, float)
    keep = np.isfinite(l1_vs) & (l1_depth > base)
    o = np.argsort(l1_depth[keep])
    dc = l1_depth[keep][o]
    tops_deep = np.concatenate([[base], 0.5 * (dc[:-1] + dc[1:])]) if dc.size else np.array([])
    top = np.concatenate([np.append(0.0, np.cumsum(fine["dz"]))[:-1], tops_deep])
    thick = np.append(np.diff(top), 0.0)
    return {
        "top": top,
        "thickness": thick,
        "vp": np.concatenate([fine["vp"], np.asarray(l1_vp, float)[keep][o]]),
        "vs": np.concatenate([fine["vs"], np.asarray(l1_vs, float)[keep][o]]),
        "rho": np.concatenate([fine["rho"], np.asarray(l1_rho, float)[keep][o]]),
        "boundaries": tuple(float(np.asarray(b)) for b in fine["boundaries"]),
    }
