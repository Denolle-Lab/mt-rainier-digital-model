"""S11: model surface layers -> the 3D viewer in web/viewer/ (Derek Yao's rainier-seismic-atlas, merged here).

Reads model.zarr (/surface after S2 and S5) and the atlas manifest (for its overview lon/lat box), and writes
<atlas>/model/: layers.json, one RGBA drape texture and one value grid per layer, and streams.png.

Usage: pixi run s11 [-- --atlas web/viewer/site/public/atlas]
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from rainier3d.config.domain import REPO, load_domain
from rainier3d.export.atlas import export_layers
from rainier3d.io.store import read_tree
from rainier3d.surface import layers as L


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--atlas", default=str(REPO / "web" / "viewer" / "site" / "public" / "atlas"))
    a = ap.parse_args()
    atlas = Path(a.atlas).expanduser()
    dom = load_domain()
    manifest = json.loads((atlas / "manifest.json").read_text())
    tree = read_tree(dom.path("processed") / "model.zarr")
    hr = dom.path("raw") / "hydrology" / "nhdplus_hr_flowlines.gpkg"
    fl = L.fetch_flowlines_hr(dom) if hr.exists() else L.fetch_flowlines(dom)
    from rainier3d.surface.imagery import fetch_s2_composite

    meta = export_layers(tree, dom, manifest, atlas / "model", fl, imagery=fetch_s2_composite(dom))
    size = sum(p.stat().st_size for p in (atlas / "model").iterdir())
    logging.info(
        "wrote %d layers + streams to %s (%.1f MB)", len(meta["layers"]), atlas / "model", size / 1e6
    )
    for layer in meta["layers"]:
        logging.info("  %-20s %s", layer["key"], layer["label"])


if __name__ == "__main__":
    main()
