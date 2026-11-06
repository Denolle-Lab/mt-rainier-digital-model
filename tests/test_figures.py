import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402

from rainier3d.report import style  # noqa: E402


def test_every_paper_figure_prints_at_least_11_pt_on_letter():
    small = {k: v for k, v in style.check().items() if isinstance(v, str) or v < style.MIN_FONT_PT}
    assert not small, small


def test_save_records_the_printed_font_size(tmp_path, monkeypatch):
    monkeypatch.setattr(style, "PAPER", tmp_path)
    monkeypatch.setattr(style, "print_widths", lambda: {"f.png": 3.25})
    fig, ax = plt.subplots(figsize=(6.5, 2))
    ax.set_title("t", fontsize=20)
    ax.tick_params(labelsize=22)
    style.save(fig, tmp_path / "f.png", dpi=100)
    pt = style.check()["f.png"]
    assert 9 < pt < 11  # 20 pt at about half size


def test_workflow_diagram_prints_at_least_11_pt_on_letter():
    import re

    svg = (style.PAPER / "figures" / "fig0_workflow.svg").read_text()
    width = float(re.search(r'<svg width="([\d.]+)pt"', svg).group(1))
    fonts = [float(f) for f in re.findall(r'font-size="([\d.]+)"', svg)]
    scale = min(1.0, style.PAGE_WIDTH_IN * 72 / width)  # printed at the text width, never enlarged past 1
    assert min(fonts) * scale >= style.MIN_FONT_PT, (width, min(fonts))
