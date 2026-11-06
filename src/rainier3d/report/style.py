"""Print size of the paper figures: every text of a figure must be at least 11 pt when the figure is
printed at its width in the paper (`width=` of its Markdown image, as a fraction of the text width) on a
US-letter page with 1 in margins (6.5 in of text width).

`save` writes the figure and records in the PNG the print width and the smallest printed font size it reaches;
`check` reads them back for every figure of the paper and the supplement (tests/test_figures.py, S23).
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from rainier3d.config.domain import REPO

PAGE_WIDTH_IN = 6.5  # US letter, 8.5 in less two 1 in margins
MIN_FONT_PT = 11.0
PAPER = REPO / "docs" / "paper"
SOURCES = [PAPER / "rainier3d_paper.md", PAPER / "rainier3d_supplement.md"]
_IMG = re.compile(r"\]\(([^)\s]+\.png)\)\{#fig:[\w-]+(?:[^}]*?width=(\d+(?:\.\d+)?)%)?[^}]*\}")


def print_widths() -> dict[str, float]:
    """Printed width (in) of each PNG figure of the paper and supplement, keyed by path under docs/paper."""
    out = {}
    for src in SOURCES:
        for path, pct in _IMG.findall(src.read_text()):
            out[path] = PAGE_WIDTH_IN * float(pct or 100) / 100
    return out


def paper_key(path: Path) -> str | None:
    try:
        return Path(path).resolve().relative_to(PAPER.resolve()).as_posix()
    except ValueError:
        return None


def smallest_font(fig) -> float:
    """Smallest font size (pt, at the figure's own size) of the visible, non-empty texts of a figure."""
    from matplotlib.text import Text

    fig.canvas.draw()
    sizes = [
        t.get_fontsize()
        for t in fig.findobj(Text)
        if t.get_visible() and t.get_text().strip() and t.get_window_extent().width > 0
    ]
    return min(sizes) if sizes else float("inf")


def save(fig, path, **kw) -> None:
    """fig.savefig, and for a figure of the paper, record its print width and smallest printed font in the PNG
    (keys `rainier3d:print_width_in`, `rainier3d:min_font_pt`); warn below MIN_FONT_PT."""
    from PIL import Image, PngImagePlugin

    path = Path(path)
    fig.savefig(path, **kw)
    key = paper_key(path)
    width = print_widths().get(key) if key and path.suffix == ".png" else None
    if width is None:
        return
    with Image.open(path) as im:
        dpi = round(im.info.get("dpi", (kw.get("dpi") or fig.dpi,))[0], 2)  # PNG stores pixels per metre
        saved_in = im.size[0] / dpi
        info = PngImagePlugin.PngInfo()
        for k, v in im.text.items():
            info.add_text(k, v)
        pt = smallest_font(fig) * width / saved_in
        info.add_text("rainier3d:print_width_in", f"{width:.3f}")
        info.add_text("rainier3d:min_font_pt", f"{pt:.2f}")
        im.load()
        im.save(path, pnginfo=info, dpi=(dpi, dpi))
    if pt < MIN_FONT_PT:
        logging.warning(
            "%s: smallest font %.1f pt at %.2f in printed width (< %g pt)", key, pt, width, MIN_FONT_PT
        )


def check() -> dict[str, str | float]:
    """Smallest printed font of each paper figure, from its PNG; a string where it is not recorded."""
    from PIL import Image

    out = {}
    for key in print_widths():
        p = PAPER / key
        if not p.exists():
            out[key] = "missing"
            continue
        with Image.open(p) as im:
            v = im.text.get("rainier3d:min_font_pt")
        out[key] = float(v) if v else "not recorded (saved without rainier3d.report.style.save)"
    return out
