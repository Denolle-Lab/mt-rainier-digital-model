"""Hydrothermal alteration of the near-surface edifice from the 1996 helicopter EM survey used by Finn,
Sisson & Deszcz-Pan (2001, Nature 409): altered volcanic rock is conductive (clays), fresh lava and ice are
resistive.

Per EM frequency f (33 kHz, 4737 Hz, 4341 Hz, 837 Hz), with L_f the median log10 apparent resistivity of the
surveyed edifice at that frequency (mostly fresh rock; each frequency saturates at its own level, from
10^3.2 ohm-m at 837 Hz to 10^4.5 at 33 kHz, so a single absolute threshold is not usable):
  intensity   a_f = clip((L_f - start - log10 rho_a) / (full - start), 0, 1)
(start and full in decades below L_f; configs/units.yaml)
  depth       doi_f = min(doi_max, k * delta),  delta = 503 sqrt(rho_a / f) m (skin depth)
and in 3D, at depth d below the bedrock surface (the glacier bed where there is ice),
  a(x, y, d) = max_f a_f(x, y) * taper(d / doi_f(x, y)),  full to doi_f, linear to 0 at 1.25 doi_f,
restricted to the units listed in the configuration (the edifice lavas). Outside the survey the field is 0 and
``alt_coverage`` is 0.

This is the shallow part only (tens of metres at 33 kHz to ~150 m at 837 Hz, the limit given by Rystrom et al.
2000). Finn et al. (2001) also used the magnetic data and geology to model buried altered rock; that
modelling is not reproduced here. The terrain-correlated apparent magnetisation (``apparent_magnetization``)
is provided as an auxiliary map: a regression, in a moving Gaussian window, of the reduced-to-pole anomaly on
the anomaly that the local topography would produce if uniformly magnetised (1 A/m, vertical), at the flight
elevation.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import xarray as xr

from rainier3d.alteration import aerogeophysics as A

FREQS = ("33k", "4737", "4341", "837")


def em_fields(
    raw: Path, x: np.ndarray, y: np.ndarray, crs: str, cfg: dict, edifice: np.ndarray
) -> xr.Dataset:
    """Per-frequency intensity and depth of investigation on the model surface grid (x, y cell centres).
    ``edifice`` (y, x) marks the cells whose median sets each frequency's fresh-rock level."""
    d0, d1 = float(cfg["start_decades"]), float(cfg["full_decades"])
    out, cover, ref = {}, None, {}
    for f in FREQS:
        g = A.to_model_grid(A.read_grid(raw, f), x, y, crs).values
        ok = np.isfinite(g)
        cover = ok if cover is None else cover | ok
        ref[f] = float(np.nanmedian(g[ok & edifice]))
        a = np.clip((ref[f] - d0 - g) / (d1 - d0), 0.0, 1.0)
        skin = 503.0 * np.sqrt(10.0 ** np.where(ok, g, 0.0) / A.EM_FREQS[f])
        doi = np.minimum(float(cfg["doi_max_m"]), float(cfg["doi_skin_fraction"]) * skin)
        out[f"alt_a_{f}"] = (("y", "x"), np.where(ok, a, 0.0).astype(np.float32))
        out[f"alt_doi_{f}"] = (("y", "x"), np.where(ok, doi, 0.0).astype(np.float32))
        out[f"alt_log10_rho_{f}"] = (("y", "x"), np.where(ok, g, np.nan).astype(np.float32))
    out["alt_coverage"] = (("y", "x"), cover.astype(np.uint8))
    ds = xr.Dataset(out, coords={"y": y, "x": x}, attrs={"fresh_log10_rho": str(ref)})
    ds["alt_a_surface"] = xr.concat([ds[f"alt_a_{f}"] for f in FREQS], "f").max("f")
    for f in FREQS:
        ds[f"alt_a_{f}"].attrs = {
            "units": "1",
            "long_name": f"alteration intensity from {f} apparent resistivity",
        }
        ds[f"alt_doi_{f}"].attrs = {"units": "m", "long_name": f"depth of investigation at {f} below bedrock"}
    ds["alt_a_surface"].attrs = {
        "units": "1",
        "long_name": "alteration intensity of the surface rock (max over f)",
    }
    return ds


def taper(d: np.ndarray, doi: np.ndarray) -> np.ndarray:
    """1 above doi, linear to 0 at 1.25 doi, 0 below (and 0 where doi is 0)."""
    with np.errstate(divide="ignore", invalid="ignore"):
        t = np.clip((1.25 * doi - d) / (0.25 * doi), 0.0, 1.0)
    return np.where((doi > 0) & (d >= 0), t, 0.0)


def alteration_3d(fields: dict, d_rock: np.ndarray, allowed: np.ndarray) -> np.ndarray:
    """a(z, y, x) from 2-D per-frequency fields broadcast against d_rock (depth below the bedrock surface)."""
    a = np.zeros(np.broadcast_shapes(d_rock.shape, allowed.shape), np.float32)
    for f in FREQS:
        a = np.maximum(a, fields[f"alt_a_{f}"] * taper(d_rock, fields[f"alt_doi_{f}"]))
    return np.where(allowed, a, 0.0).astype(np.float32)


def apparent_magnetization(
    raw: Path, elevation: xr.DataArray, x: np.ndarray, y: np.ndarray, crs: str, sigma_m: float = 500.0
) -> tuple[np.ndarray, dict]:
    """Terrain-correlated apparent magnetisation (A/m) on (y, x); prisms from ``elevation`` padded by 3 km."""
    import harmonica as hm
    from pyproj import Transformer
    from scipy.interpolate import griddata
    from scipy.ndimage import gaussian_filter

    dx = float(x[1] - x[0])
    pad = 3000.0
    xp = np.arange(x[0] - pad, x[-1] + pad + 1, dx)
    yp = np.arange(y[0] - pad, y[-1] + pad + 1, dx)
    top = elevation.interp(x=xp, y=yp).values
    rp = A.to_model_grid(A.read_grid(raw, "rp"), x, y, crs).values
    fm = A.flight_mag(raw)
    fx, fy = Transformer.from_crs(A.NAD27_UTM10, crs, always_xy=True).transform(fm.x.values, fm.y.values)
    X, Y = np.meshgrid(x, y)
    h = griddata((fx, fy), fm.flelv.values, (X, Y), method="linear")
    h = np.where(np.isnan(h), griddata((fx, fy), fm.flelv.values, (X, Y), method="nearest"), h)
    h = np.maximum(h, elevation.interp(x=x, y=y).values + 20.0)  # keep the sensor outside the local prism
    XP, YP = np.meshgrid(xp, yp)
    pr = np.column_stack(
        [XP.ravel() - dx / 2, XP.ravel() + dx / 2, YP.ravel() - dx / 2, YP.ravel() + dx / 2,
         np.zeros(XP.size), np.maximum(top.ravel(), 1.0)]
    )  # fmt: skip
    n = len(pr)
    G = hm.prism_magnetic(
        (X.ravel(), Y.ravel(), h.ravel()), pr, (np.zeros(n), np.zeros(n), np.ones(n)), "b_u"
    )
    G = G.reshape(X.shape)
    ok = np.isfinite(rp)
    w = ok.astype(float)
    d = np.where(ok, rp, 0.0)
    s = sigma_m / dx

    def wmean(a):
        return gaussian_filter(a * w, s) / np.maximum(gaussian_filter(w, s), 1e-9)

    mg, md = wmean(G), wmean(d)
    M = (wmean(G * d) - mg * md) / np.maximum(wmean(G * G) - mg**2, 1e-9)
    M = np.where(gaussian_filter(w, s) > 0.5, M, np.nan)
    clear = h - elevation.interp(x=x, y=y).values
    info = {
        "window_sigma_m": sigma_m,
        "clearance_median_m": float(np.nanmedian(clear)),
        "corr_rtp_terrain": float(np.corrcoef(G[ok & np.isfinite(G)], rp[ok & np.isfinite(G)])[0, 1]),
    }
    return M.astype(np.float32), info
