"""Relocate a PNSN catalogue with NonLinLoc (Lomax et al. 2000) in rainier3d grids (S26).

NonLinLoc is an external program (github.com/alomax/NonLinLoc, GPL-3): set RAINIER3D_NLL_BIN to the directory
holding Grid2Time and NLLoc (default ~/.local/nonlinloc). Grids use TRANS NONE: x, y in UTM 10N km, z in km
positive down (below sea level), as written by rainier3d.export.grids.write_nll.

Topography: LOCTOPO_SURFACE with an ASCII GMT grid of the ground elevation in km on the same x, y km frame
(NLLoc compares -z with it when TRANS is NONE, NLLocLib.c isAboveTopo), so no hypocentre is placed in the air.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

NLL_BIN = Path(os.environ.get("RAINIER3D_NLL_BIN", Path.home() / ".local" / "nonlinloc"))
SIGMA = {"P": 0.14, "S": 0.23}  # s, the pick uncertainty of S13/S14 (PNSN's own location RMS for these data)


def run(prog: str, control: Path, log: Path) -> None:
    with open(log, "w") as f:
        r = subprocess.run(
            [str(NLL_BIN / prog), str(control)], stdout=f, stderr=subprocess.STDOUT, cwd=control.parent
        )
    if r.returncode != 0:
        raise RuntimeError(f"{prog} failed ({r.returncode}); see {log}")


def run_parallel(prog: str, controls: dict, logs: dict) -> None:
    """Run one ``prog`` per control file at the same time; raise if any fails."""
    procs = {}
    for k, control in controls.items():
        f = open(logs[k], "w")
        procs[k] = (subprocess.Popen([str(NLL_BIN / prog), str(control)], stdout=f, stderr=subprocess.STDOUT,
                                     cwd=control.parent), f)  # fmt: skip
    failed = []
    for k, (p, f) in procs.items():
        if p.wait() != 0:
            failed.append(k)
        f.close()
    if failed:
        raise RuntimeError(f"{prog} failed for {failed}; see {[str(logs[k]) for k in failed]}")


def write_topo_grd(elev_m: np.ndarray, x_m: np.ndarray, y_m: np.ndarray, path: Path) -> Path:
    """ASCII GMT grd (gridline registration) of the ground elevation, x/y/z in km, top row first."""
    xk, yk, z = x_m / 1e3, y_m / 1e3, elev_m / 1e3
    order = np.argsort(yk)[::-1]  # scanlines from y_max down
    z = np.nan_to_num(z[order], nan=float(np.nanmin(z)))
    dx, dy = float(np.diff(xk).mean()), float(np.diff(yk).mean())
    name = path.name
    lines = [
        f"{name}: Title: rainier3d ground elevation (km)",
        f"{name}: Command: rainier3d.catalog.nll.write_topo_grd",
        f"{name}: Remark: DEM on the model surface grid, UTM 10N km",
        f"{name}: Normal node registration used",
        f"{name}: grdfile format # 0",
        f"{name}: x_min: {xk.min():.4f} x_max: {xk.max():.4f} x_inc: {dx:.4f} name: km nx: {xk.size}",
        f"{name}: y_min: {yk.min():.4f} y_max: {yk.max():.4f} y_inc: {dy:.4f} name: km ny: {yk.size}",
        f"{name}: z_min: {np.nanmin(z):.4f} z_max: {np.nanmax(z):.4f} name: km",
        f"{name}: scale_factor: 1 add_offset: 0",
    ]
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
        np.savetxt(f, z, fmt="%.4f")
    return path


def write_obs(picks: pd.DataFrame, path: Path) -> Path:
    """NLLOC_OBS file: one block per event; Gaussian errors SIGMA by phase."""
    with open(path, "w") as f:
        for _, g in picks.groupby("event", sort=False):
            f.write(f"PUBLIC_ID {g.event.iloc[0]}\n")
            for r in g.itertuples():
                t = pd.Timestamp(r.pick_time)
                sec = t.second + t.microsecond / 1e6
                f.write(
                    f"{r.sta:<6s} ?    ?    ? {r.phase:<6s} ? {t:%Y%m%d} {t:%H%M} {sec:7.4f} "
                    f"GAU {SIGMA[r.phase]:9.2e} -1.00e+00 -1.00e+00 -1.00e+00\n"
                )
            f.write("\n")
    return path


def grid2time_control(model_prefix: Path, time_prefix: Path, phase: str, stations: pd.DataFrame, path: Path):
    lines = [
        "CONTROL 1 54321",
        "TRANS NONE",
        f"GTFILES {model_prefix} {time_prefix} {phase}",
        "GTMODE GRID3D ANGLES_NO",
        "GT_PLFD 1.0e-3 0",
    ]
    lines += [
        f"GTSRCE {r.sta} XYZ {r.x / 1e3:.4f} {r.y / 1e3:.4f} {-r.elev / 1e3:.4f} 0.0"
        for r in stations.itertuples()
    ]
    path.write_text("\n".join(lines) + "\n")
    return path


def nlloc_control(obs: Path, time_prefix: Path, out_prefix: Path, grid: dict, topo: Path | None, path: Path):
    """grid: nx, ny, nz, x0, y0, z0 (km), d (km) of the search volume (must lie inside the time grids)."""
    g = grid
    lines = [
        "CONTROL 1 54321",
        "TRANS NONE",
        f"LOCFILES {obs} NLLOC_OBS {time_prefix} {out_prefix}",
        "LOCHYPOUT SAVE_NLLOC_ALL NLL_FORMAT_VER_2",
        "LOCSEARCH OCT 10 10 6 0.01 30000 10000 0 1",
        f"LOCGRID {g['nx']} {g['ny']} {g['nz']} {g['x0']} {g['y0']} {g['z0']} {g['d']} {g['d']} {g['d']} "
        "PROB_DENSITY SAVE",
        "LOCMETH EDT_OT_WT 9999.0 4 -1 -1 -1 -1 0 1",
        "LOCGAU 0.1 0.0",
        "LOCGAU2 0.02 0.05 0.5",
        "LOCPHASEID P P p Pg Pn",
        "LOCPHASEID S S s Sg Sn",
        "LOCQUAL2ERR 0.1 0.5 1.0 2.0 99999.9",
        "LOCANGLES ANGLES_NO 5",
        "LOCPHSTAT 9999.0 -1 9999.0 1.0 1.0 9999.9 -9999.9 9999.9",
    ]
    if topo is not None:
        lines.append(f"LOCTOPO_SURFACE {topo} 0")
    path.write_text("\n".join(lines) + "\n")
    return path


def read_hyp(path: Path) -> pd.DataFrame:
    """Parse a NonLinLoc summary .hyp (all events): location, origin time, quality, uncertainty (all km)."""
    rows, cur = [], None
    for line in Path(path).read_text().splitlines():
        t = line.split()
        if not t:
            continue
        if t[0] == "NLLOC":
            cur = {"event": None, "status": " ".join(t[2:])}
        elif cur is None:
            continue
        elif t[0] == "SIGNATURE" or t[0] == "COMMENT":
            continue
        elif t[0] == "PUBLIC_ID":
            cur["event"] = t[1]
        elif t[0] == "HYPOCENTER":
            cur.update(x_km=float(t[2]), y_km=float(t[4]), z_km=float(t[6]))
        elif t[0] == "GEOGRAPHIC":
            cur.update(ot=f"{t[2]}-{t[3]}-{t[4]}T{t[5]}:{t[6]}:{float(t[7]):09.6f}")
        elif t[0] == "QUALITY":
            q = dict(zip(t[1::2], t[2::2], strict=False))
            cur.update(rms=float(q["RMS"]), nphs=int(q["Nphs"]), gap=float(q["Gap"]), dist=float(q["Dist"]))
        elif t[0] == "QML_OriginUncertainty":
            q = dict(zip(t[1::2], t[2::2], strict=False))
            cur.update(
                h_unc_max_km=float(q.get("maxHorUnc", "nan")), h_unc_min_km=float(q.get("minHorUnc", "nan"))
            )
        elif t[0] == "STATISTICS":
            q = dict(zip(t[1::2], t[2::2], strict=False))
            # covariance keys: CovXX, then XY XZ YY YZ ZZ (km^2 with TRANS NONE)
            cur.update(z_sd_km=float(np.sqrt(float(q["ZZ"]))), x_sd_km=float(np.sqrt(float(q["CovXX"]))))
        elif t[0] == "END_NLLOC":
            rows.append(cur)
            cur = None
    return pd.DataFrame(rows)
