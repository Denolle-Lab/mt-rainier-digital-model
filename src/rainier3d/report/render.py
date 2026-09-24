"""Markdown report -> one self-contained HTML page.

Math: $$...$$ (display) and \\(...\\) (inline) are protected from Markdown and typeset by KaTeX.
```mermaid blocks become Mermaid diagrams. <img src="figures/..."> is inlined as base64, so the page
is a single file that can be linked or copied anywhere. {{REFERENCES}} is replaced by the reference
list built from DOI content negotiation (references_resolved.json), with hand fixes where the
registry record is malformed.
"""

from __future__ import annotations

import base64
import html
import json
import re
from pathlib import Path

import markdown

# registry records with malformed author strings: corrected from the publications themselves
FIXES = {
    "10.1007/s000240050012": "Watters, R. J., Zimbelman, D. R., Bowman, S. D., & Crowley, J. K. (2000). Rock mass "
    "strength assessment and significance to edifice stability, Mount Rainier and Mount Hood, Cascade Range "
    "volcanoes. <i>Pure and Applied Geophysics</i>, 157(6–8), 957–976. https://doi.org/10.1007/s000240050012",
    "10.7265/N5-RGI-60": "RGI Consortium. (2017). <i>Randolph Glacier Inventory – A dataset of global glacier "
    "outlines, Version 6.0</i> [Dataset]. NSIDC. https://doi.org/10.7265/N5-RGI-60",
    "10.5066/P14HJ3IC": "Wirth Moriarty, E., Grant, A. R., Stone, I. P., Stephenson, W. J., & Frankel, A. D. (2025). "
    "<i>Data for a 3-D seismic velocity model for Cascadia with shallow soils & topography, version 1.7</i> "
    "[Dataset]. U.S. Geological Survey. https://doi.org/10.5066/P14HJ3IC",
}
# not DOI-registered; cited by URL
EXTRA = [
    "Washington Geological Survey. (n.d.). <i>Surface geology of Washington, 1:100,000 (GeMS)</i> [Feature service]. "
    "Washington State Department of Natural Resources. Retrieved 23 September 2026 from https://gis.dnr.wa.gov/site1/rest/services/Public_Geology/"
    "100K_Surface_Geology_WA_GeMS/FeatureServer",
    "Maffezzoli, N., et al. (2025). <i>IceBoost v2.0 per-glacier ice thickness, RGI 6.0 region 02</i> [Dataset, "
    "produced 5 November 2025]. OGGM data server. https://cluster.klima.uni-bremen.de/~oggm/ice_thickness/iceboost_v2/",
    "Pacific Northwest Seismic Network. (2003). <i>Quarterly Report 2003-A</i> (regional 1D velocity models). "
    "https://assets.pnsn.org/legacy_reports/Sum03/Quarterly2003A.pdf",
    "U.S. Geological Survey. <i>3D Elevation Program (3DEP)</i>. https://www.usgs.gov/3d-elevation-program",
    "U.S. Geological Survey. <i>ComCat earthquake catalog, FDSN event web service</i> (PNSN network 'uw', origins "
    "and phase data). https://earthquake.usgs.gov/fdsnws/event/1/",
    "Luu, K. <i>fteikpy: accurate eikonal solver for Python</i> (v2.4.0) [Software]. https://github.com/keurfonluu/fteikpy",
]

CSS = """
:root { --bg:#fcfcfb; --fg:#1b1b1a; --muted:#5c5b57; --line:#e3e2dc; --accent:#2a78d6; --code:#f3f2ee; --tbl:#f7f6f2; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --bg:#161615; --fg:#ecebe6; --muted:#a8a69c; --line:#34332f; --accent:#6aa6ee; --code:#22211f; --tbl:#1d1c1a; } }
:root[data-theme="dark"] { --bg:#161615; --fg:#ecebe6; --muted:#a8a69c; --line:#34332f; --accent:#6aa6ee; --code:#22211f; --tbl:#1d1c1a; }
* { box-sizing: border-box; }
html { background: var(--bg); }
body { margin: 0; background: var(--bg); color: var(--fg); font: 16.5px/1.62 "Source Serif 4", Georgia, serif;
  -webkit-font-smoothing: antialiased; }
main { max-width: 820px; margin: 0 auto; padding: 56px 20px 96px; }
header.title { border-bottom: 1px solid var(--line); padding-bottom: 22px; margin-bottom: 26px; }
header.title .kicker { font: 600 12px/1 Inter, system-ui, sans-serif; letter-spacing: .09em; text-transform: uppercase;
  color: var(--accent); }
h1 { font: 700 34px/1.18 Inter, system-ui, sans-serif; letter-spacing: -.015em; margin: 12px 0 10px; }
.byline { font: 14px/1.5 Inter, system-ui, sans-serif; color: var(--muted); }
h2 { font: 650 23px/1.3 Inter, system-ui, sans-serif; margin: 46px 0 12px; letter-spacing: -.01em; }
h3 { font: 650 17.5px/1.35 Inter, system-ui, sans-serif; margin: 30px 0 8px; }
p, li { hyphens: auto; }
a { color: var(--accent); text-decoration-thickness: 1px; text-underline-offset: 2px; overflow-wrap: anywhere; }
.abstract { background: var(--tbl); border-left: 3px solid var(--accent); padding: 14px 18px; margin: 18px 0 8px; }
.abstract p { margin: .4em 0; }
.toc { font: 14px/1.6 Inter, system-ui, sans-serif; border: 1px solid var(--line); border-radius: 8px;
  padding: 12px 18px; margin: 24px 0; }
.toc ul { margin: 4px 0; padding-left: 18px; }
figure { margin: 26px 0; }
figure img { width: 100%; height: auto; border-radius: 4px; background: #fff; }
figcaption { font: 13.5px/1.5 Inter, system-ui, sans-serif; color: var(--muted); margin-top: 8px; }
figcaption b { color: var(--fg); }
table { width: 100%; border-collapse: collapse; font: 13.5px/1.45 Inter, system-ui, sans-serif; margin: 16px 0;
  display: block; overflow-x: auto; }
th, td { padding: 6px 10px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; }
th { background: var(--tbl); font-weight: 600; }
td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
code { font: 13.5px/1.4 "JetBrains Mono", ui-monospace, monospace; background: var(--code); padding: 1px 5px;
  border-radius: 4px; }
pre { background: var(--code); padding: 14px 16px; border-radius: 6px; overflow-x: auto; }
pre code { background: none; padding: 0; }
pre.mermaid { background: none; text-align: center; }
.katex-display { overflow-x: auto; overflow-y: hidden; padding: 4px 0; }
.refs p { padding-left: 2em; text-indent: -2em; margin: .45em 0; font-size: 14.5px; }
.note { font: 13.5px/1.5 Inter, system-ui, sans-serif; color: var(--muted); }
footer { border-top: 1px solid var(--line); margin-top: 48px; padding-top: 14px; font: 13px/1.5 Inter, system-ui,
  sans-serif; color: var(--muted); }
@media (max-width: 640px) { body { font-size: 15.5px; } h1 { font-size: 27px; } main { padding-top: 32px; } }
@media print { .toc { display: none; } main { max-width: none; } a { color: inherit; } }
"""

HEAD = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title><meta name="description" content="{description}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;650;700&family=JetBrains+Mono&family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;1,8..60,400&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css">
<style>{css}</style></head><body><main>
"""

TAIL = """</main>
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js"></script>
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/contrib/auto-render.min.js"
  onload="renderMathInElement(document.body,{delimiters:[{left:'$$',right:'$$',display:true},{left:'\\\\(',right:'\\\\)',display:false}]});"></script>
<script type="module">
import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs";
const dark = matchMedia("(prefers-color-scheme: dark)").matches && document.documentElement.dataset.theme !== "light";
mermaid.initialize({ startOnLoad: true, theme: dark ? "dark" : "neutral", fontFamily: "Inter, system-ui, sans-serif" });
</script></body></html>
"""


def _cited(ref: str, text: str) -> bool:
    """A reference is listed only if its first author (or its parenthesised short name) appears in the text."""
    plain = re.sub(r"<[^>]+>", "", ref)
    head = plain.split("(")[0]
    first = head.split(",")[0].split(".")[0].strip()
    keys = {first, first.split()[0] if first else "", *re.findall(r"\(([A-Z]{2,})\)", plain)}
    return any(k and k in text for k in keys)


def references(resolved_json: Path, text: str) -> str:
    data = json.loads(resolved_json.read_text())
    items = []
    for doi, txt in data.items():
        t = FIXES.get(doi, txt)
        if not t or not _cited(t, text):
            continue
        t = t.replace("&amp;", "&").replace("<scp>", "").replace("</scp>", "").replace("Portico. ", "")
        items.append(t)
    items += EXTRA
    items.sort(key=lambda s: re.sub(r"<[^>]+>", "", s).lower())
    out = []
    for t in items:
        t = re.sub(
            r"(https?://\S+?)(\.?)$", lambda m: f'<a href="{m.group(1)}">{m.group(1)}</a>{m.group(2)}', t
        )
        out.append(f"<p>{t}</p>")
    return '<div class="refs">\n' + "\n".join(out) + "\n</div>"


def render(md_path: Path, out_path: Path, refs_json: Path, title: str, description: str) -> Path:
    src = md_path.read_text()
    src = src.replace("{{REFERENCES}}", references(refs_json, src))
    store = []

    def keep(m):
        store.append(m.group(0))
        return f"@@MATH{len(store) - 1}@@"

    src = re.sub(r"\$\$.+?\$\$", keep, src, flags=re.S)
    src = re.sub(r"\\\(.+?\\\)", keep, src, flags=re.S)
    src = re.sub(
        r"```mermaid\n(.+?)```",
        lambda m: f'<pre class="mermaid">\n{html.escape(m.group(1))}</pre>',
        src,
        flags=re.S,
    )
    body = markdown.markdown(
        src,
        extensions=["extra", "toc", "sane_lists"],
        extension_configs={"toc": {"toc_depth": "2-2", "title": "Contents"}},
    )
    for i, s in enumerate(store):
        body = body.replace(f"@@MATH{i}@@", html.escape(s, quote=False))

    def inline(m):
        p = md_path.parent / m.group(1)
        b64 = base64.b64encode(p.read_bytes()).decode()
        return f'src="data:image/png;base64,{b64}"'

    body = re.sub(r'src="(figures/[^"]+\.png)"', inline, body)
    body = re.sub(r"<p>\[TOC\]</p>", "", body)
    page = HEAD.format(title=html.escape(title), description=html.escape(description), css=CSS) + body + TAIL
    out_path.write_text(page)
    return out_path
