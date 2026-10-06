"""S32: rebuild the platform (the 3D viewer bundle and the atlas data) from scratch (configs/platform.yaml).

Deletes every derived file of the platform, then runs, in order, with the data freeze ``as_of``:

  stage        copy the machine-local inputs into data/raw/ once (DAS table, KMZ overlays, Synoptic stations)
  viewer-data  terrain, summit, stations and earthquakes (web/viewer/data, cache in data/raw/viewer_cache)
  s8           sensor inventory, DAS, events and overlays (web/atlas/data)
  s11          model layers, sensors, canopy, terrain geometry, magnetisation, mass movements, volume
  s26          relocated earthquakes, from outputs/catalog (the relocation itself is not rerun)
  s29          storm events, from their raw caches (no paper figure)
  check        no 2025 node under its old spreadsheet id; stations and manifest dated as_of
  bundle       SHA256SUMS of the bundle and a byte-reproducible tarball (fixed order, owner and mtime)

The model products (data/processed/model.zarr and the other S2-S30 stores, outputs/catalog) are read, never
rebuilt: a missing one stops the rebuild instead of giving a smaller bundle (--allow-missing to build anyway).
Writes outputs/platform/build.json with the steps run and the bundle checksum.

Usage: pixi run platform [-- --allow-missing]
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import logging
import shutil
import subprocess
import sys
import tarfile
from datetime import UTC, datetime
from pathlib import Path

from rainier3d.config.domain import REPO, load_domain
from rainier3d.config.platform import as_of, config, local_input

log = logging.getLogger("s32")


def run(args: list[str], cwd: Path = REPO) -> None:
    log.info("$ %s", " ".join(args))
    subprocess.run([sys.executable, *args], cwd=cwd, check=True)


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def tarball(src: Path, dst: Path, mtime: int) -> None:
    """tar.gz of ``src`` whose bytes depend only on the files: sorted entries, owner 0, fixed mtime, and no
    file name or time in the gzip header."""
    dst.parent.mkdir(parents=True, exist_ok=True)

    def norm(ti: tarfile.TarInfo) -> tarfile.TarInfo:
        ti.uid = ti.gid = 0
        ti.uname = ti.gname = ""
        ti.mtime = mtime
        ti.mode = 0o755 if ti.isdir() else 0o644
        return ti

    with open(dst, "wb") as raw, gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0) as gz:
        with tarfile.open(fileobj=gz, mode="w", format=tarfile.PAX_FORMAT) as tar:
            for p in [src, *sorted(src.rglob("*"))]:
                tar.add(p, arcname=str(p.relative_to(src.parent)), recursive=False, filter=norm)


def check(atlas: Path, day: str) -> list[str]:
    errs = []
    sensors = json.loads((atlas / "model" / "sensors.json").read_text())
    old = [s["id"] for s in sensors["sites"] if s["id"].startswith("node-")]
    if old:
        errs.append(f"{len(old)} sensors keep the spreadsheet node ids (e.g. {old[0]})")
    st = json.loads((atlas / "stations.json").read_text())
    if st.get("asOf") != day:
        errs.append(f"stations.json asOf {st.get('asOf')} != {day}")
    man = json.loads((atlas / "manifest.json").read_text())
    if man.get("built") != day:
        errs.append(f"manifest.json built {man.get('built')} != {day}")
    return errs


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--allow-missing", action="store_true", help="build without missing model products")
    a = ap.parse_args()
    dom, cfg, day = load_domain(), config(), as_of()
    v = cfg["viewer"]
    atlas = REPO / v["atlas"]

    need = {"model.zarr": dom.path("processed") / "model.zarr"}
    optional = {
        "relocated catalogue": dom.path("outputs") / "catalog" / "catalog_relocated.csv",
        "canopy layers": dom.path("processed") / "surface_canopy.zarr",
        "terrain geometry": dom.path("processed") / "terrain_geometry.zarr",
        "mass movements": dom.path("outputs") / "mass_movements",
        "3D strain": dom.path("processed") / "strain_3d.zarr",
        "apparent magnetisation (S36)": dom.path("processed") / "packwood_magnetics.zarr",
    }
    missing = [k for k, p in {**need, **optional}.items() if not p.exists()]
    if [k for k in missing if k in need] or (missing and not a.allow_missing):
        raise SystemExit(f"model products missing: {missing}; build them first (or --allow-missing)")

    for key in cfg["local_inputs"]:  # stage
        log.info("local input %s -> %s", key, local_input(key, dom.path("raw")))
    for d in v["derived"]:
        shutil.rmtree(REPO / d, ignore_errors=True)
        log.info("deleted %s", d)

    viewer_data = REPO / "web" / "viewer" / "data"
    run(
        ["-m", "rainier.build", "--out", str(atlas), "--cache", str(REPO / v["cache"]), "--as-of", day],
        viewer_data,
    )
    run(["scripts/08_atlas.py"])
    run(["scripts/11_seismic_atlas.py", "--atlas", str(atlas)])
    steps = ["stage", "viewer-data", "s8", "s11"]
    if "relocated catalogue" not in missing:
        run(["scripts/26_relocate_catalog.py", "--viewer-only", "--viewer", str(atlas)])
        steps.append("s26")
    for ev in v["events"]:
        run(["scripts/29_flood_event.py", "--event", ev, "--no-figure", "--atlas", str(atlas)])
        steps.append(f"s29:{ev}")

    errs = check(atlas, day)
    if errs:
        raise SystemExit("platform check failed:\n" + "\n".join(errs))
    files = sorted(p for p in atlas.rglob("*") if p.is_file() and p.name != "SHA256SUMS")
    (atlas / "SHA256SUMS").write_text("".join(f"{sha256(p)}  {p.relative_to(atlas)}\n" for p in files))
    mtime = int(datetime.fromisoformat(day).replace(tzinfo=UTC).timestamp())  # same in every timezone
    tarball(atlas, REPO / v["bundle"], mtime)
    out = dom.path("outputs") / "platform"
    out.mkdir(parents=True, exist_ok=True)
    rec = {
        "as_of": day,
        "steps": steps,
        "missing_products": missing,
        "files": len(files),
        "bytes": sum(p.stat().st_size for p in files),
        "bundle": v["bundle"],
        "bundle_sha256": sha256(REPO / v["bundle"]),
    }
    (out / "build.json").write_text(json.dumps(rec, indent=1))
    log.info("platform rebuilt: %s", json.dumps(rec))


if __name__ == "__main__":
    main()
