"""S11: model surface layers -> the 3D viewer in web/viewer/ (Derek Yao's rainier-seismic-atlas, merged here).

Reads model.zarr (/surface after S2 and S5) and the atlas manifest (for its overview lon/lat box), and writes
<atlas>/model/: layers.json, one RGBA drape texture and one value grid per layer, and streams.png.

With --layers KEY[,KEY], only those surface layers are rewritten and merged into the bundle's existing
layers.json (other layers and the sensors are kept as published); the subsurface volume is always rewritten.

Usage: pixi run s11 [-- --atlas web/viewer/site/public/atlas]
       pixi run s11 -- --layers alteration_surface,apparent_magnetization
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from rainier3d.config.domain import REPO, load_domain
from rainier3d.export.atlas import export_layers, export_sensors, export_volume
from rainier3d.io.store import read_tree
from rainier3d.surface import layers as L


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--atlas", default=str(REPO / "web" / "viewer" / "site" / "public" / "atlas"))
    ap.add_argument("--layers", default="", help="comma-separated layer keys to update in an existing bundle")
    a = ap.parse_args()
    atlas = Path(a.atlas).expanduser()
    dom = load_domain()
    manifest = json.loads((atlas / "manifest.json").read_text())
    tree = read_tree(dom.path("processed") / "model.zarr")
    hr = dom.path("raw") / "hydrology" / "nhdplus_hr_flowlines.gpkg"
    fl = L.fetch_flowlines_hr(dom) if hr.exists() else L.fetch_flowlines(dom)
    from rainier3d.surface.imagery import fetch_s2_composite

    if a.layers:
        keys = [k.strip() for k in a.layers.split(",") if k.strip()]
        meta = merge_layers(tree, dom, manifest, atlas / "model", fl, keys)
    else:
        meta = export_layers(tree, dom, manifest, atlas / "model", fl, imagery=fetch_s2_composite(dom))
        sen = export_sensors(atlas, REPO / "web" / "atlas" / "data")  # S8 inventory
        logging.info(
            "sensors: %d sites, DAS %d segments (%d channels)",
            len(sen["sites"]),
            len(sen["das"]["segments"]),
            sen["das"]["channels"],
        )
    vol = export_volume(tree, dom, atlas)
    g = vol["grid"]
    logging.info(
        "volume %d x %d x %d cells (%s), scene->grid fit error %.3f cells",
        g["nx"],
        g["ny"],
        g["nz"],
        ", ".join(vol["vars"]),
        vol["uv_poly"]["max_error_cells"],
    )
    size = sum(p.stat().st_size for p in (atlas / "model").rglob("*") if p.is_file())
    logging.info(
        "wrote %d layers + streams to %s (%.1f MB)", len(meta["layers"]), atlas / "model", size / 1e6
    )
    for layer in meta["layers"]:
        logging.info("  %-20s %s", layer["key"], layer["label"])


def merge_layers(tree, dom, manifest, model_dir: Path, flowlines, keys: list[str]) -> dict:
    """Export all layers to a scratch directory, then copy ``keys`` into the bundle."""
    import shutil
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        new = export_layers(tree, dom, manifest, Path(tmp), flowlines)
        meta = json.loads((model_dir / "layers.json").read_text())
        have = [layer["key"] for layer in meta["layers"]]
        for layer in new["layers"]:
            if layer["key"] not in keys:
                continue
            for f in (layer["texture"], layer["values"]["file"]):
                shutil.copy(Path(tmp) / f, model_dir / f)
            if layer["key"] in have:
                meta["layers"][have.index(layer["key"])] = layer
            else:
                meta["layers"].append(layer)
            logging.info("updated layer %s", layer["key"])
        missing = set(keys) - {layer["key"] for layer in new["layers"]}
        if missing:
            raise SystemExit(f"no such layers in this model: {sorted(missing)}")
    (model_dir / "layers.json").write_text(json.dumps(meta, indent=1))
    return meta


if __name__ == "__main__":
    main()
