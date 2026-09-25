"""S27: deposit a release on Zenodo as a new version of the software or the data record (docs/doi.md).

  software --tag vX.Y.Z             source archive of the tag (git archive), type software, BSD-3-Clause
  data --tag products-vX.Y.Z        the assets of that GitHub release (checked against its SHA256SUMS) and
                                    docs/products.md, type dataset, CC-BY 4.0; isDerivedFrom = every DOI in
                                    configs/sources.yaml, isCompiledBy = --software-doi

Authors and affiliations come from CITATION.cff. With --concept <record id> the deposit is a new version of
that record; without it, a new record. The deposit is left as an unpublished draft: review and publish it on
Zenodo, because a published DOI cannot be deleted. --dry-run prints the metadata and the files and contacts
nothing.

Usage: ZENODO_TOKEN=... pixi run python scripts/27_zenodo_deposit.py data --tag products-v1.0.0 [--sandbox]
       [--concept 1234567] [--software-doi 10.5281/zenodo.x] [--dry-run]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
GITHUB = "Denolle-Lab/mt-rainier-digital-model"
API = {"zenodo": "https://zenodo.org/api", "sandbox": "https://sandbox.zenodo.org/api"}


def creators() -> list[dict]:
    cff = yaml.safe_load((REPO / "CITATION.cff").read_text())
    out = []
    for a in cff["authors"]:
        c = {"name": f"{a['family-names']}, {a['given-names']}", "affiliation": a.get("affiliation", "")}
        if a.get("orcid"):
            c["orcid"] = a["orcid"].rsplit("/", 1)[-1]
        out.append(c)
    return out


def input_dois() -> list[dict]:
    reg = yaml.safe_load((REPO / "configs" / "sources.yaml").read_text())
    dois = sorted(
        {str(v[f]) for v in reg.values() if isinstance(v, dict) for f in ("doi", "data_doi") if v.get(f)}
    )
    return [{"identifier": d, "relation": "isDerivedFrom", "scheme": "doi"} for d in dois]


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def software(tag: str, work: Path) -> tuple[dict, list[Path]]:
    zp = work / f"mt-rainier-digital-model-{tag}.zip"
    subprocess.run(
        ["git", "archive", "--format=zip", f"--prefix=mt-rainier-digital-model-{tag}/", "-o", zp, tag],
        cwd=REPO,
        check=True,
    )
    meta = {
        "upload_type": "software",
        "title": f"rainier3d: pipeline, client and 3D viewer of a digital model of Mount Rainier ({tag})",
        "license": "bsd-3-clause",
        "description": "Source code of rainier3d: the deterministic pipeline that compiles the digital "
        "model of Mount Rainier from its original archives, the rainier3d command-line and Python client for "
        "the derived products, "
        "and the three-dimensional viewer (web/viewer/, MIT licence).",
        "related_identifiers": [
            {
                "identifier": f"https://github.com/{GITHUB}/tree/{tag}",
                "relation": "isSupplementTo",
                "scheme": "url",
            }
        ],
    }
    return meta, [zp]


def data(tag: str, work: Path, software_doi: str | None) -> tuple[dict, list[Path]]:
    subprocess.run(
        ["gh", "release", "download", tag, "--repo", GITHUB, "--dir", work, "--clobber"], check=True
    )
    sums = dict(
        reversed(line.split()) for line in (work / "SHA256SUMS").read_text().splitlines() if line.strip()
    )
    files = sorted(work / n for n in sums)
    bad = [p.name for p in files if sha256(p) != sums[p.name]]
    if bad:
        raise SystemExit(f"checksum mismatch after download: {bad}")
    (work / "products.md").write_text((REPO / "docs" / "products.md").read_text())
    rel = input_dois()
    if software_doi:
        rel.append({"identifier": software_doi, "relation": "isCompiledBy", "scheme": "doi"})
    meta = {
        "upload_type": "dataset",
        "title": "rainier3d derived products: a digital model of the subsurface and surface of Mount Rainier "
        f"({tag})",
        "license": "cc-by-4.0",
        "description": "Derived products of rainier3d: the fused seismic velocity, density and attenuation "
        "model, "
        "uniform grids for eikonal solvers, NonLinLoc and EMC, strain in the volume, edifice-load stress, "
        "hydrothermal alteration from the helicopter EM survey, the mass-movement catalogue and a GNSS "
        "snapshot. "
        "Usage: products.md. Inputs whose licence forbids redistribution are excluded.",
        "related_identifiers": rel,
    }
    return meta, [*files, work / "SHA256SUMS", work / "products.md"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("record", choices=["software", "data"])
    ap.add_argument("--tag", required=True)
    ap.add_argument("--concept", help="Zenodo record id to add a version to")
    ap.add_argument("--software-doi")
    ap.add_argument("--sandbox", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    work = REPO / "outputs" / "zenodo" / a.tag
    work.mkdir(parents=True, exist_ok=True)
    meta, files = software(a.tag, work) if a.record == "software" else data(a.tag, work, a.software_doi)
    meta |= {
        "creators": creators(),
        "version": a.tag,
        "keywords": [
            "Mount Rainier",
            "seismic velocity model",
            "digital model",
            "geodesy",
            "hydrothermal alteration",
        ],
        "notes": "Supported by the Jerome and Linda Paros Geohazard Center, University of Washington.",
    }
    print(json.dumps({"metadata": meta, "files": {p.name: p.stat().st_size for p in files}}, indent=1))
    if a.dry_run:
        return
    import requests

    base = API["sandbox" if a.sandbox else "zenodo"]
    auth = {"Authorization": f"Bearer {os.environ['ZENODO_TOKEN']}"}
    if a.concept:  # new version of an existing record; drop the files it inherits
        r = requests.post(
            f"{base}/deposit/depositions/{a.concept}/actions/newversion", headers=auth, timeout=60
        )
        r.raise_for_status()
        dep = requests.get(r.json()["links"]["latest_draft"], headers=auth, timeout=60).json()
        for f in dep.get("files", []):
            requests.delete(f["links"]["self"], headers=auth, timeout=60).raise_for_status()
    else:
        dep = requests.post(f"{base}/deposit/depositions", json={}, headers=auth, timeout=60)
        dep.raise_for_status()
        dep = dep.json()
    for p in files:
        with open(p, "rb") as fh:
            requests.put(
                f"{dep['links']['bucket']}/{p.name}", data=fh, headers=auth, timeout=3600
            ).raise_for_status()
    r = requests.put(dep["links"]["self"], json={"metadata": meta}, headers=auth, timeout=60)
    r.raise_for_status()
    print(f"draft {r.json()['id']}: {r.json()['links']['html']} (review and publish on Zenodo)")


if __name__ == "__main__":
    main()
