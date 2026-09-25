"""S23: build the report from docs/report/rainier3d.md -> outputs/report/ (HTML page and ESSD PDF).

  rainier3d_report.html   one self-contained page (figures embedded, MathML equations, no scripts)
  rainier3d_essd.tex/.pdf the same text in the Copernicus ESSD manuscript class (natbib + copernicus.bst)

Figures are the committed PNGs of docs/report/figures/ (made by S10, S16 and S21 from the model) and
docs/report/workflow.dot, rendered here with Graphviz. Citations [@key] resolve through docs/references.bib
(pixi run bib), whose keys are the configs/sources.yaml keys. The Copernicus LaTeX package is downloaded
from Copernicus and checked against COPERNICUS_SHA256; it is not redistributed with this repository.
No model data are needed, so .github/workflows/report.yml runs this on a clean checkout.

Usage: pixi run -e paper report [-- --html-only | --pdf-only]
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import os
import re
import shutil
import subprocess
import urllib.request
import zipfile
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
DOCS = REPO / "docs" / "report"
SRC = DOCS / "rainier3d.md"
TPL = DOCS / "templates"
BIB = REPO / "docs" / "references.bib"
OUT = REPO / "outputs" / "report"
COPERNICUS_URL = "https://publications.copernicus.org/Copernicus_LaTeX_Package.zip"
COPERNICUS_SHA256 = "996038225515b56856769e7de478a7df5ef97e425e645147ea57dc72adfed4dd"  # package 7.16
COPERNICUS_FILES = ("copernicus.cls", "copernicus.cfg", "copernicus.bst", "pdfscreen.sty", "pdfscreencop.sty")

# text characters -> LaTeX for the 8-bit fonts of the class (also valid under pdfLaTeX + newunicodechar)
UNICODE = {
    "−": r"\ensuremath{-}",
    "×": r"\ensuremath{\times}",
    "≥": r"\ensuremath{\geq}",
    "≤": r"\ensuremath{\leq}",
    "≈": r"\ensuremath{\approx}",
    "±": r"\ensuremath{\pm}",
    "°": r"\ensuremath{^\circ}",
    "′": r"\ensuremath{^{\prime}}",
    "″": r"\ensuremath{^{\prime\prime}}",
    "√": r"\ensuremath{\surd}",
    "∞": r"\ensuremath{\infty}",
    "→": r"\ensuremath{\rightarrow}",
    "ρ": r"\ensuremath{\rho}",
    "λ": r"\ensuremath{\lambda}",
    "σ": r"\ensuremath{\sigma}",
    "Δ": r"\ensuremath{\Delta}",
    "μ": r"\ensuremath{\mu}",
    "µ": r"\ensuremath{\mu}",
    "χ": r"\ensuremath{\chi}",
    "ν": r"\ensuremath{\nu}",
    "τ": r"\ensuremath{\tau}",
    "φ": r"\ensuremath{\phi}",
    "ε": r"\ensuremath{\varepsilon}",
    "α": r"\ensuremath{\alpha}",
    "Ω": r"\ensuremath{\Omega}",
    "⁸": r"\ensuremath{^8}",
    "²": r"\ensuremath{^2}",
    "³": r"\ensuremath{^3}",
    "¹": r"\ensuremath{^1}",
    "⁵": r"\ensuremath{^5}",
    "⁻": r"\ensuremath{^-}",
    "₀": r"\ensuremath{_0}",
    "₁": r"\ensuremath{_1}",
    "–": "--",
    "—": "---",
    "“": "``",
    "”": "''",
    "‘": "`",
    "’": "'",
    "…": r"\ldots{}",
    "·": r"\textperiodcentered{}",
    "é": r"\'e",
    "á": r"\'a",
    "è": r"\`e",
    "ö": '\\"o',
    "ü": '\\"u',
    "ä": '\\"a',
    "ç": r"\c{c}",
    "\u00a0": "~",
}

log = logging.getLogger("s23")


def run(cmd: list[str], cwd: Path | None = None) -> None:
    log.info("%s", " ".join(map(str, cmd)))
    subprocess.run(list(map(str, cmd)), cwd=cwd, check=True)


def workflow_figure() -> None:
    for fmt in ("svg", "pdf"):
        run(["dot", f"-T{fmt}", DOCS / "workflow.dot", "-o", DOCS / "figures" / f"fig0_workflow.{fmt}"])


def copernicus(dest: Path) -> None:
    """The Copernicus LaTeX package, downloaded once and checked; fails if Copernicus has changed it."""
    zpath = OUT / "copernicus_package.zip"
    if not zpath.exists():
        req = urllib.request.Request(COPERNICUS_URL, headers={"User-Agent": "rainier3d report build"})
        with urllib.request.urlopen(req, timeout=120) as r:
            zpath.write_bytes(r.read())
    sha = hashlib.sha256(zpath.read_bytes()).hexdigest()
    if sha != COPERNICUS_SHA256:
        zpath.unlink()
        raise SystemExit(
            f"Copernicus LaTeX package changed (sha256 {sha}); review it, then update COPERNICUS_SHA256 "
            f"in {__file__}"
        )
    with zipfile.ZipFile(zpath) as z:
        for name in COPERNICUS_FILES:
            (dest / name).write_bytes(z.read(name))


def check_unicode(text: str) -> None:
    missing = sorted({c for c in text if ord(c) > 127 and c not in UNICODE})
    if missing:
        raise SystemExit(
            f"characters without a LaTeX mapping in {SRC.name}: {' '.join(missing)} (add to UNICODE)"
        )


def pandoc_common() -> list[str]:
    return [
        *("pandoc", SRC, "--from", "markdown+smart+lists_without_preceding_blankline"),
        *("--filter", "pandoc-crossref"),
        *("--metadata-file", TPL / "crossref.yaml", "--bibliography", BIB),
        *("--resource-path", f"{DOCS}:{REPO / 'docs'}"),
    ]


def html() -> Path:
    out = OUT / "rainier3d_report.html"
    run(
        [
            *pandoc_common(),
            *("--to", "html5", "--standalone", "--template", TPL / "report.html", "--number-sections"),
            *("--citeproc", "--csl", TPL / "copernicus-publications.csl", "--mathml", "--embed-resources"),
            *("--toc", "--toc-depth", "2", "--default-image-extension", "svg", "--section-divs", "-o", out),
        ]
    )
    return out


def pdf() -> Path:
    tex = OUT / "rainier3d_essd.tex"
    copernicus(OUT)
    shutil.copy(BIB, OUT / "references.bib")
    umap = "\n".join(f"\\newunicodechar{{{c}}}{{{v}}}" for c, v in UNICODE.items() if c != " ")
    umap += "\n\\newunicodechar{ }{~}"
    run(
        [
            *pandoc_common(),
            *("--to", "latex", "--template", TPL / "essd.latex", "--natbib"),
            *("--lua-filter", TPL / "essd.lua", "--default-image-extension", "pdf"),
            *("--variable", f"unicode-map={umap}"),
            *("--variable", f"graphicspath={DOCS}", "--variable", f"graphicspath={REPO / 'docs'}", "-o", tex),
        ]
    )
    run(["tectonic", "-X", "compile", "--keep-logs", "--keep-intermediates", tex.name], cwd=OUT)
    return tex.with_suffix(".pdf")


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--html-only", action="store_true")
    ap.add_argument("--pdf-only", action="store_true")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    text = SRC.read_text()
    check_unicode(text + BIB.read_text())
    meta = yaml.safe_load(re.match(r"---\n(.*?)\n---\n", text, re.S).group(1))
    log.info("%s: %d words", meta["title"], len(re.sub(r"^---.*?---", "", text, flags=re.S).split()))
    workflow_figure()
    made = []
    if not a.pdf_only:
        made.append(html())
    if not a.html_only:
        made.append(pdf())
    for p in made:
        log.info("wrote %s (%.1f MB)", p.relative_to(REPO), p.stat().st_size / 1e6)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
            f.write("### Report\n" + "".join(f"- {p.name}: {p.stat().st_size / 1e6:.1f} MB\n" for p in made))


if __name__ == "__main__":
    main()
