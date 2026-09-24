"""Build the static atlas bundle: python -m rainier.build --out ../site/public/atlas --cache cache"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

import numpy as np

from . import extent as E
from .quakes import build_quakes, check_quakes
from .stations import build_stations
from .summit import build_summit
from .terrain import build_overview

SIZE_LIMIT = 600_000_000
SUMMIT_RMS_LIMIT_M = 30.0
STEPS = ("terrain", "summit", "stations", "quakes")


def check_counts(st: dict) -> list[str]:
    errs = []
    n = sum(len(s["stations"]) for s in st["sites"])
    if n != st["counts"]["stations"]:
        errs.append(f"station count: counts say {st['counts']['stations']}, sites hold {n}")
    if len(st["sites"]) != st["counts"]["sites"]:
        errs.append(f"site count: counts say {st['counts']['sites']}, found {len(st['sites'])}")
    c = st["counts"]
    if "returned" in c and c["returned"] - c["excluded"] != c["stations"]:
        errs.append(f"stations don't reconcile: {c['returned']} returned − {c['excluded']} excluded ≠ {c['stations']} kept")
    unknown = {k for s in st["sites"] for k in s["kinds"]} - set(st["kinds"])
    if unknown:
        errs.append(f"unknown instrument kinds {sorted(unknown)}")
    return errs


def check_size(out_dir, limit: int = SIZE_LIMIT) -> list[str]:
    total = sum(p.stat().st_size for p in Path(out_dir).rglob("*") if p.is_file())
    return [f"bundle too large: {total:,} bytes (limit {limit:,})"] if total > limit else []


def sample(ov: np.ndarray, meta: dict, x: np.ndarray, z: np.ndarray) -> np.ndarray:
    """Bilinear sample of the overview grid (cell centers at x0 + (c + 0.5)·dx)."""
    fc = np.clip((x - meta["x0"]) / meta["dx"] - 0.5, 0, meta["cols"] - 1.001)
    fr = np.clip((z - meta["z0"]) / meta["dz"] - 0.5, 0, meta["rows"] - 1.001)
    c, r = fc.astype(int), fr.astype(int)
    tc, tr = fc - c, fr - r
    top = ov[r, c] * (1 - tc) + ov[r, c + 1] * tc
    bot = ov[r + 1, c] * (1 - tc) + ov[r + 1, c + 1] * tc
    return top * (1 - tr) + bot * tr


def check_summit_rms(heights_m, xs, zs, ov, meta) -> list[str]:
    rms = float(np.sqrt(np.mean((heights_m - sample(ov, meta, xs, zs)) ** 2)))
    return [f"summit disagrees with the overview: RMS {rms:.1f} m (limit {SUMMIT_RMS_LIMIT_M} m)"] if rms > SUMMIT_RMS_LIMIT_M else []


def summit_level0(out_dir, index: dict):
    """Assemble level 0 (dropping shared edges) with its cell-center coordinates in km."""
    t, lv = index["tile"], index["levels"][0]
    grid = np.zeros((lv["tiles_z"] * t, lv["tiles_x"] * t))
    for ty in range(lv["tiles_z"]):
        for tx in range(lv["tiles_x"]):
            q = np.fromfile(Path(out_dir) / "summit" / "0" / f"{ty}_{tx}.bin", "<u2").reshape(t + 1, t + 1)
            grid[ty * t:(ty + 1) * t, tx * t:(tx + 1) * t] = q[:t, :t] / 10.0
    p = index["patch"]
    xs, zs = np.meshgrid(p["west_km"] + (np.arange(grid.shape[1]) + 0.5) * lv["cell_x_km"],
                         p["north_km"] + (np.arange(grid.shape[0]) + 0.5) * lv["cell_z_km"])
    return grid, xs, zs


def validate(out_dir, terrain: dict, summit: dict, stations: dict, limit: int = SIZE_LIMIT) -> list[str]:
    errs = check_counts(stations) + check_size(out_dir, limit)
    ov = np.fromfile(Path(out_dir) / "terrain" / "overview.bin", "<i2").reshape(terrain["rows"], terrain["cols"]).astype(float)
    grid, xs, zs = summit_level0(out_dir, summit)
    errs += check_summit_rms(grid, xs, zs, ov, terrain)
    return errs


def _load(out: Path, name: str) -> dict:
    return json.loads((out / name).read_text())


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", required=True)
    ap.add_argument("--cache", required=True)
    ap.add_argument("--only", default=",".join(STEPS))
    ap.add_argument("--as-of", default=None)
    a = ap.parse_args(argv)
    out, only = Path(a.out), set(a.only.split(","))
    out.mkdir(parents=True, exist_ok=True)
    if "terrain" in only:
        build_overview(out, a.cache)
    if "summit" in only:
        build_summit(out, a.cache)
    if "stations" in only:
        st = build_stations(a.cache, as_of=a.as_of)
        errs = check_counts(st)
        if errs:   # refuse before writing, so a bad refresh can't replace the committed file
            print("\n".join(f"error: {e}" for e in errs), file=sys.stderr)
            return 1
        (out / "stations.json").write_text(json.dumps(st, indent=1))
    terrain, summit, stations = _load(out, "terrain/terrain.json"), _load(out, "summit/index.json"), _load(out, "stations.json")
    if "quakes" in only:
        ov = np.fromfile(out / "terrain" / "overview.bin", "<i2").reshape(terrain["rows"], terrain["cols"]).astype(float)
        ground = lambda x, z: float(sample(ov, terrain, np.array(x), np.array(z))) / 1000
        build_quakes(out, a.cache, ground)
    # quakes are optional in the bundle: check them when built now or already present, so --only without
    # quakes works on a fresh output directory
    have_quakes = "quakes" in only or (out / "quakes.json").exists()
    errs = validate(out, terrain, summit, stations) + (check_quakes(_load(out, "quakes.json")) if have_quakes else [])
    if errs:
        print("\n".join(f"error: {e}" for e in errs), file=sys.stderr)
        return 1
    size = sum(p.stat().st_size for p in out.rglob("*") if p.is_file())
    manifest = {
        "built": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "sizeBytes": size,
        "sources": [
            {"name": "USGS 3DEP elevation (overview and 1 m summit lidar)", "url": "https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer", "license": "public domain"},
            {"name": "USGS The National Map imagery (USGSImageryOnly)", "url": "https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryOnly/MapServer", "license": "public domain"},
            {"name": "EarthScope FDSN station service", "url": "https://service.earthscope.org/fdsnws/station/1/", "license": "open", "asOf": stations["asOf"]},
            {"name": "USGS ComCat earthquake catalog (PNSN)", "url": "https://earthquake.usgs.gov/fdsnws/event/1/", "license": "public domain"},
        ],
        "extent": {"overview": E.OVERVIEW._asdict(), "summit": E.SUMMIT._asdict()},
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1))
    c = stations["counts"]
    print(f"ok: {c['stations']} stations in {c['sites']} sites ({c['sitesOnMap']} sites on the map); bundle {size / 1e6:.0f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
