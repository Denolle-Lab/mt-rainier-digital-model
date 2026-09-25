"""S20: package the derived products for download (maintainers): outputs/products/ and the package catalog.

  model         model.zarr (levels L1-L3 and /surface) without the variables whose provenance includes a
                source marked `redistribute_derived: false` in configs/sources.yaml
  gnss          outputs/gnss/ (velocities, strain series, summary), data/processed/gnss/strain_grid.nc and
                the download record (data/raw/gnss/manifest.csv, data/processed/gnss/fetch.json)
  edifice_load  data/processed/edifice_load.zarr
  strain_3d     data/processed/strain_3d.zarr (S24: GNSS strain rate and edifice-load strain in the volume)

Each archive gets its SHA-256; the catalog shipped in the package (src/rainier3d/products.json) is updated
with version, url, size and checksum. With --upload the archives become assets of GitHub release <tag>.

--rolling is for products refreshed on a schedule (catalog entries with "rolling": true, i.e. gnss): the
archive, a <file>.sha256 checksum file and a dated copy <stem>_<as_of>.zip are uploaded to the release <tag>
(created if needed, assets replaced), and the catalog entry keeps its rolling URL.

Usage: pixi run python scripts/20_publish_products.py --tag products-v1 [--upload]
       pixi run -e gnss gnss-publish --tag gnss-latest --rolling --upload     (weekly workflow)
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
from rainier3d.io import store

REPOSITORY = "Denolle-Lab/mt-rainier-digital-model"
CATALOG = REPO / "src" / "rainier3d" / "products.json"


def restricted_keys() -> set[str]:
    reg = yaml.safe_load((REPO / "configs" / "sources.yaml").read_text())
    return {k for k, v in reg.items() if isinstance(v, dict) and v.get("redistribute_derived") is False}


def zip_dir(src: Path, dst: Path, arcroot: str) -> Path:
    dst.parent.mkdir(parents=True, exist_ok=True)
    # fixed timestamps and sorted entries: the archive (and its checksum) depends only on the file contents
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_STORED) as z:  # zarr chunks are already compressed
        for p in sorted(src.rglob("*")):
            if p.is_file():
                info = zipfile.ZipInfo(f"{arcroot}/{p.relative_to(src)}", date_time=(1980, 1, 1, 0, 0, 0))
                info.external_attr = 0o644 << 16
                with open(p, "rb") as f, z.open(info, "w") as w:
                    shutil.copyfileobj(f, w, 1 << 20)
    return dst


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def package_model(dom, tmp: Path, out: Path, bad: set[str]):
    tree = xr.open_datatree(dom.path("processed") / "model.zarr", engine="zarr", consolidated=False)
    nodes, dropped = {}, []
    for name in ("surface", "L1", "L2", "L3"):
        ds = tree[name].to_dataset()
        drop = [v for v in ds.data_vars if set(str(ds[v].attrs.get("gaia:source_keys", "")).split(",")) & bad]
        dropped += [f"{name}/{v}" for v in drop]
        nodes[f"/{name}"] = ds.drop_vars(drop)
    t = xr.DataTree.from_dict(nodes)
    t.attrs = dict(tree.attrs) | {"excluded_variables": ", ".join(dropped), "license": "CC-BY-4.0 (derived)"}
    store.write(t, tmp / "model.zarr")
    return zip_dir(tmp / "model.zarr", out / "rainier3d_model.zarr.zip", "model.zarr"), dropped


def package_gnss(dom, tmp: Path, out: Path):
    g = tmp / "gnss"
    g.mkdir()
    for p in [
        *(dom.path("outputs") / "gnss").glob("*.csv"),
        dom.path("outputs") / "gnss" / "summary.json",
        dom.path("outputs") / "gnss" / "strain_3d_summary.json",
        dom.path("processed") / "gnss" / "strain_grid.nc",
        dom.path("processed") / "gnss" / "fetch.json",
        dom.path("raw") / "gnss" / "manifest.csv",
    ]:
        if p.exists():
            shutil.copy(p, g / p.name)
    return zip_dir(g, out / "rainier3d_gnss.zip", "gnss"), []


def gh(*args, check=True):
    return subprocess.run(["gh", *args, "--repo", REPOSITORY], check=check, capture_output=True, text=True)


def upload_rolling(tag: str, files: list[Path]):
    """Replace the assets of release <tag>, creating it (not marked latest) if it does not exist yet."""
    if gh("release", "view", tag, check=False).returncode != 0:
        notes = (
            "Refreshed by .github/workflows/gnss-weekly.yml. The unsuffixed archive is the latest; "
            "dated copies are kept for reproducibility. Licence and attribution: docs/data_policy.md."
        )
        title = f"rainier3d {tag} (refreshed weekly)"
        gh("release", "create", tag, "--latest=false", "--title", title, "--notes", notes)
    gh("release", "upload", tag, *map(str, files), "--clobber")


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True, help="release tag, e.g. products-v1")
    ap.add_argument("--upload", action="store_true")
    ap.add_argument(
        "--only", nargs="+", choices=["model", "gnss", "edifice_load", "strain_3d"], help="default: all"
    )
    ap.add_argument("--rolling", action="store_true", help="replace the assets of an existing release")
    a = ap.parse_args()
    dom = load_domain()
    out = dom.path("outputs") / "products"
    tmp = out / "staging"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    bad = restricted_keys()
    catalog = json.loads(CATALOG.read_text())
    built = {}

    only = set(a.only or ["model", "gnss", "edifice_load", "strain_3d"])

    # model: drop variables built from sources that may not be redistributed
    if "model" in only:
        built["model"] = package_model(dom, tmp, out, bad)
    if "gnss" in only:
        built["gnss"] = package_gnss(dom, tmp, out)
    s3 = dom.path("processed") / "strain_3d.zarr"
    if "strain_3d" in only and s3.exists():
        built["strain_3d"] = (zip_dir(s3, out / "rainier3d_strain_3d.zarr.zip", "strain_3d.zarr"), [])
    el = dom.path("processed") / "edifice_load.zarr"
    if "edifice_load" in only and el.exists():
        built["edifice_load"] = (
            zip_dir(el, out / "rainier3d_edifice_load.zarr.zip", "edifice_load.zarr"),
            [],
        )

    for key, (path, dropped) in built.items():
        e = catalog["products"][key]
        if e.get("rolling"):
            continue  # the catalog points at the rolling release; its checksum is in <file>.sha256
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
    if a.rolling:
        files = []
        for key, (path, _) in built.items():
            if not catalog["products"][key].get("rolling"):
                raise SystemExit(f"--rolling: product {key!r} is not marked rolling in the catalog")
            as_of = json.loads((dom.path("processed") / "gnss" / "fetch.json").read_text())["as_of"]
            dated = path.with_name(f"{path.stem}_{as_of}{path.suffix}")
            shutil.copy(path, dated)
            side = path.with_name(path.name + ".sha256")
            side.write_text(f"{sha256(path)}  {path.name}\n")
            files += [path, side, dated]
            logging.info("%s: %s (%.1f MB), as_of %s", key, path.name, path.stat().st_size / 1e6, as_of)
        if a.upload:
            upload_rolling(a.tag, files)
            logging.info("uploaded %d files to release %s", len(files), a.tag)
        return
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
