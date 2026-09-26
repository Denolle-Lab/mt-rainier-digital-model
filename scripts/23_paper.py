"""S23: build the paper, docs/paper/rainier3d_paper.md -> docs/paper/rainier3d_paper.{html,pdf} (committed).

  rainier3d_paper.html     one self-contained page (figures embedded, MathML equations, no scripts)
  rainier3d_paper.pdf      the same text in the Copernicus ESSD manuscript class (natbib + copernicus.bst)

Intermediate files (LaTeX source, logs, the Copernicus package) stay in outputs/paper/. SOURCE_DATE_EPOCH is
fixed, so the same text gives the same bytes on the same platform; the committed copy is the Linux CI build.

Figures are the committed PNGs of docs/paper/figures/ (made by S10, S16 and S21 from the model) and
docs/paper/workflow.dot, rendered here with Graphviz. Citations [@key] resolve through docs/references.bib
(pixi run bib), whose keys are the configs/sources.yaml keys. The Copernicus LaTeX package is downloaded
from Copernicus and checked against COPERNICUS_SHA256; it is not redistributed with this repository.
No model data are needed, so .github/workflows/paper.yml runs this on a clean checkout.

Usage: pixi run -e paper paper [-- --html-only | --pdf-only]
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
DOCS = REPO / "docs" / "paper"
SRC = DOCS / "rainier3d_paper.md"
TPL = DOCS / "templates"
BIB = REPO / "docs" / "references.bib"
OUT = REPO / "outputs" / "paper"
COPERNICUS_URL = "https://publications.copernicus.org/Copernicus_LaTeX_Package.zip"
COPERNICUS_SHA256 = "996038225515b56856769e7de478a7df5ef97e425e645147ea57dc72adfed4dd"  # package 7.16
COPERNICUS_FILES = ("copernicus.cls", "copernicus.cfg", "copernicus.bst", "pdfscreen.sty", "pdfscreencop.sty")

# text characters -> LaTeX for the 8-bit fonts of the class (also valid under pdfLaTeX + newunicodechar)
UNICODE = {
    "−": r"\ensuremath{-}",
    "ě": r"\v{e}",
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
    "⁴": r"\ensuremath{^4}",
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
    run(["dot", "-c"])  # register Graphviz output plugins (a freshly installed pixi environment has none)
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


def _braced(text: str, i: int) -> int:
    """Index just past the brace group that opens at text[i] == '{'."""
    depth = 0
    for j in range(i, len(text)):
        depth += {"{": 1, "}": -1}.get(text[j], 0)
        if depth == 0:
            return j + 1
    raise ValueError("unbalanced braces")


def longtables_to_floats(tex: str) -> str:
    """pandoc writes every table as a page-breaking longtable, which ignores floats already placed on its page
    and overruns it. Tables that fit on a page become table floats; long ones (appendix) stay longtables."""
    out, pos, begin = [], 0, "\\begin{longtable}[]"
    while (i := tex.find(begin, pos)) >= 0:
        j = _braced(tex, i + len(begin))
        spec = tex[i + len(begin) + 1 : j - 1]
        end = tex.index("\\end{longtable}", j)
        body = tex[j:end]
        if body.count("\\\\") > 18:  # a long table (appendix) keeps breaking across pages
            out.append(tex[pos : end + len("\\end{longtable}")])
            pos = end + len("\\end{longtable}")
            continue
        cap = ""
        if body.lstrip().startswith("\\caption"):
            c0 = body.index("\\caption")
            c1 = body.index("\\tabularnewline", c0)
            cap, body = body[c0:c1].strip(), body[c1 + len("\\tabularnewline") :]
        head = body[
            body.index("\\toprule\\noalign{}") + len("\\toprule\\noalign{}") : body.index(
                "\\midrule\\noalign{}"
            )
        ]
        rows = body[body.index("\\endlastfoot") + len("\\endlastfoot") :]
        out.append(tex[pos:i])
        top = "\\begin{table}[tbp]\n" + (cap + "\n" if cap else "") + "\\centering\n"
        tab = f"\\begin{{tabular}}{{{spec}}}\n\\toprule{head}\\midrule{rows.rstrip()}\n"
        tab += "\\bottomrule\n\\end{tabular}"
        out.append(top + tab + "\n\\end{table}")
        pos = end + len("\\end{longtable}")
    out.append(tex[pos:])
    return "".join(out)


def pandoc_common() -> list[str]:
    return [
        *("pandoc", SRC, "--from", "markdown+smart+lists_without_preceding_blankline"),
        *("--filter", "pandoc-crossref"),
        *("--metadata-file", TPL / "crossref.yaml", "--bibliography", BIB),
        *("--resource-path", f"{DOCS}:{REPO / 'docs'}"),
    ]


def html() -> Path:
    out = OUT / "rainier3d_paper.html"
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
    tex = OUT / "rainier3d_paper.tex"
    copernicus(OUT)
    shutil.copy(BIB, OUT / "references.bib")
    umap = "\n".join(f"\\newunicodechar{{{c}}}{{{v}}}" for c, v in UNICODE.items())
    run(
        [
            *pandoc_common(),
            *("--to", "latex", "--template", TPL / "essd.latex", "--natbib"),
            *("--lua-filter", TPL / "essd.lua", "--default-image-extension", "pdf"),
            *("--variable", f"unicode-map={umap}"),
            *("--variable", f"graphicspath={DOCS}", "--variable", f"graphicspath={REPO / 'docs'}", "-o", tex),
        ]
    )
    tex.write_text(longtables_to_floats(tex.read_text()))
    run(["tectonic", "-X", "compile", "--keep-logs", "--keep-intermediates", tex.name], cwd=OUT)
    return tex.with_suffix(".pdf")


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--html-only", action="store_true")
    ap.add_argument("--pdf-only", action="store_true")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    # fixed timestamp: the PDF bytes depend only on the text (its metadata dates read 1970, by design)
    os.environ["SOURCE_DATE_EPOCH"] = "0"
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
    made = [Path(shutil.copy(p, DOCS / p.name)) for p in made]  # the paper lives next to its source
    for p in made:
        log.info("wrote %s (%.1f MB)", p.relative_to(REPO), p.stat().st_size / 1e6)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
            f.write("### Report\n" + "".join(f"- {p.name}: {p.stat().st_size / 1e6:.1f} MB\n" for p in made))


if __name__ == "__main__":
    main()
