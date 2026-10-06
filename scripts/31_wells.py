"""S31: wells and boreholes in the model box -> data/processed/wells.csv and outputs/wells/summary.json.

Fetches (once, frozen at as_of in configs/wells.yaml) the Washington Department of Ecology well reports, the
USGS groundwater levels and the Washington Geological Survey subsurface database into data/raw/wells/, builds
one table of depth to water and depth to bedrock (m below ground), and compares it with the gridded water
tables, soil thickness and depth to bedrock of /surface in model.zarr (S2, S5).

Usage: pixi run s31"""

from __future__ import annotations

import json
import logging

from rainier3d.config.domain import load_domain
from rainier3d.hydromet import wells as W
from rainier3d.io.store import read_tree


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    dom = load_domain()
    cfg = W.config()
    eco = W.fetch_ecology(dom, cfg)
    nwis = W.fetch_nwis(dom, cfg)
    wgs = W.wgs_tables(dom, W.fetch_wgs(dom, cfg), cfg)
    t = W.well_table(dom, cfg, eco, nwis, wgs)
    p = dom.path("processed") / "wells.csv"
    t.to_csv(p, index=False, float_format="%.3f")
    surf = read_tree(dom.path("processed") / "model.zarr")["surface"].to_dataset()
    summ = W.compare(t, surf, cfg)
    out = dom.path("outputs") / "wells"
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps(summ, indent=1))
    logging.info("wrote %s (%d rows) and %s\n%s", p, len(t), out / "summary.json", json.dumps(summ, indent=1))


if __name__ == "__main__":
    main()
