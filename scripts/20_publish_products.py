"""S20: package the derived products for download (maintainers): outputs/products/ and the package catalog.

  model         model.zarr (levels L1-L3 and /surface) without the variables whose provenance includes a
                source marked `redistribute_derived: false` in configs/sources.yaml
  gnss          outputs/gnss/ (velocities, strain series, summary) and data/processed/gnss/strain_grid.nc
  edifice_load  data/processed/edifice_load.zarr

Each archive gets its SHA-256; the catalog shipped in the package (src/rainier3d/products.json) is updated
with version, url, size and checksum. With --upload the archives become assets of GitHub release <tag>.

Usage: pixi run python scripts/20_publish_products.py --tag products-v1 [--upload]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import shutil
import subprocess
import zipfile
from pathlib import Path

import xarray as xr
import yaml

from rainier3d.config.domain import REPO, load_domain

REPOSITORY = "Denolle-Lab/mt-rainier-digital-model"
CATALOG = REPO / "src" / "rainier3d" / "products.json"


def restricted_keys() -> set[str]:
    reg = yaml.safe_load((REPO / "configs" / "sources.yaml").read_text())
    return {k for k, v in reg.items() if isinstance(v, dict) and v.get("redistribute_derived") is False}


def zip_dir(src: Path, dst: Path, arcroot: str) -> Path:
    dst.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_STORED) as z:  # zarr chunks are already compressed
        for p in sorted(src.rglob("*")):
            if p.is_file():
                z.write(p, f"{arcroot}/{p.relative_to(src)}")
    return dst


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True, help="release tag, e.g. products-v1")
    ap.add_argument("--upload", action="store_true")
    a = ap.parse_args()
    dom = load_domain()
    out = dom.path("outputs") / "products"
    tmp = out / "staging"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    bad = restricted_keys()
    catalog = json.loads(CATALOG.read_text())
    built = {}

    # model: drop variables built from sources that may not be redistributed
    tree = xr.open_datatree(dom.path("processed") / "model.zarr", engine="zarr", consolidated=False)
    nodes, dropped = {}, []
    for name in ("surface", "L1", "L2", "L3"):
        ds = tree[name].to_dataset()
        drop = [v for v in ds.data_vars if set(str(ds[v].attrs.get("gaia:source_keys", "")).split(",")) & bad]
        dropped += [f"{name}/{v}" for v in drop]
        nodes[f"/{name}"] = ds.drop_vars(drop)
    t = xr.DataTree.from_dict(nodes)
    t.attrs = dict(tree.attrs) | {"excluded_variables": ", ".join(dropped), "license": "CC-BY-4.0 (derived)"}
    t.to_zarr(tmp / "model.zarr", mode="w", consolidated=False)
    built["model"] = (zip_dir(tmp / "model.zarr", out / "rainier3d_model.zarr.zip", "model.zarr"), dropped)

    g = tmp / "gnss"
    g.mkdir()
    for p in [
        *(dom.path("outputs") / "gnss").glob("*.csv"),
        dom.path("outputs") / "gnss" / "summary.json",
        dom.path("processed") / "gnss" / "strain_grid.nc",
    ]:
        if p.exists():
            shutil.copy(p, g / p.name)
    built["gnss"] = (zip_dir(g, out / "rainier3d_gnss.zip", "gnss"), [])
    el = dom.path("processed") / "edifice_load.zarr"
    if el.exists():
        built["edifice_load"] = (
            zip_dir(el, out / "rainier3d_edifice_load.zarr.zip", "edifice_load.zarr"),
            [],
        )

    for key, (path, dropped) in built.items():
        e = catalog["products"][key]
        e |= {
            "version": a.tag,
            "file": path.name,
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
            "url": f"https://github.com/{REPOSITORY}/releases/download/{a.tag}/{path.name}",
            "excluded": dropped,
        }
        logging.info(
            "%s: %s, %.1f MB, excluded %s", key, path.name, path.stat().st_size / 1e6, dropped or "none"
        )
    CATALOG.write_text(json.dumps(catalog, indent=2) + "\n")
    if a.upload:
        files = [str(p) for p, _ in built.values()]
        subprocess.run(
            [
                "gh",
                "release",
                "create",
                a.tag,
                *files,
                "--repo",
                REPOSITORY,
                "--title",
                f"rainier3d derived products ({a.tag})",
                "--notes",
                "Derived products for `rainier3d fetch` / `rainier3d export`. Checksums are in "
                "src/rainier3d/products.json. Licence and attribution: docs/data_policy.md.",
            ],
            check=True,
        )
    logging.info("catalog updated: %s", CATALOG)


if __name__ == "__main__":
    main()
