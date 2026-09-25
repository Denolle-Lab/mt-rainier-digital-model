"""S0: SHA-256 manifest of the raw input cache (data/raw/) -> docs/data_manifest.csv, or a check against it.

Every stage caches what it downloads under data/raw/<source>/ and reads the cache on reruns. The committed
manifest records, for each cached file, its size and SHA-256, so a rebuilt cache can be compared with the one
the published model was built from. A live service (ComCat, NHDPlus, 3DEP) can return different bytes on a
later download; --check lists those files instead of failing silently.

Usage: pixi run manifest            write docs/data_manifest.csv from the local cache
       pixi run manifest -- --check compare the local cache with docs/data_manifest.csv
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RAW = REPO / "data" / "raw"
MANIFEST = REPO / "docs" / "data_manifest.csv"
SKIP = {".DS_Store"}


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def scan() -> list[dict]:
    rows = []
    for p in sorted(RAW.rglob("*")):
        if p.is_file() and p.name not in SKIP and not p.name.endswith(".part"):
            rel = p.relative_to(RAW).as_posix()
            if rel.startswith("canopy_storage/non-seismic_code/"):  # S28: working copy of vendored code
                continue
            rows.append(
                {"source": rel.split("/")[0], "path": rel, "bytes": p.stat().st_size, "sha256": sha256(p)}
            )
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="compare data/raw with the committed manifest")
    a = ap.parse_args()
    if not a.check:
        rows = scan()
        with open(MANIFEST, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["source", "path", "bytes", "sha256"], lineterminator="\n")
            w.writeheader()
            w.writerows(rows)
        total = sum(r["bytes"] for r in rows)
        print(f"{MANIFEST.relative_to(REPO)}: {len(rows)} files, {total / 1e9:.2f} GB")
        return 0
    with open(MANIFEST) as f:
        ref = {r["path"]: r for r in csv.DictReader(f)}
    have = {r["path"]: r for r in scan()}
    missing = sorted(set(ref) - set(have))
    changed = sorted(p for p in set(ref) & set(have) if ref[p]["sha256"] != have[p]["sha256"])
    extra = sorted(set(have) - set(ref))
    print(f"{len(ref) - len(missing) - len(changed)} of {len(ref)} files identical to the manifest")
    for label, items in (("missing", missing), ("different", changed), ("not in manifest", extra)):
        if items:
            print(f"{label} ({len(items)}): " + ", ".join(items[:20]) + (" ..." if len(items) > 20 else ""))
    return 1 if missing or changed else 0


if __name__ == "__main__":
    sys.exit(main())
