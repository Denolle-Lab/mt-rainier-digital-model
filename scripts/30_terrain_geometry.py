"""S30: terrain geometry that controls surface instability, after the specification of S. Han (2026).

Reads:
  3DEP elevation     rainier3d.surface.dem.fetch_3dep at 30 m (cache data/raw/dem/3dep_30m_<domain>.tif),
                     or --dem PATH
  ice thickness      the surface node of model.zarr (IceBoost v2, 100 m), or --model PATH
  mass movements     outputs/mass_movements/events.gpkg and flows.gpkg of S24, or --mass-movements DIR

Writes:
  data/processed/terrain_geometry.zarr   elevation, ice_thickness, bedrock_elevation, surface_slope,
                                         bedrock_slope, local_relief, valley_depth on the 30 m grid
  outputs/terrain/mass_movement_terrain.csv   the four layers at the mass movements against the whole grid
  outputs/terrain/summary.json           grid, radii, inputs and layer percentiles of this run
  docs/paper/figures/fig22_terrain_geometry.png
  <atlas>/model/<layer>.webp, .u16.bin and layers.json entries (group "Terrain geometry"), if the viewer
  bundle exists

Parameters: configs/terrain.yaml. Operators: rainier3d.surface.terrain.

Usage: pixi run s30
       pixi run s30 -- --model ~/.cache/rainier3d/model/extracted/model.zarr --mass-movements <dir>
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from pathlib import Path

import geopandas as gpd
import numpy as np
import rioxarray  # noqa: F401  (registers .rio)
import xarray as xr
from scipy.ndimage import binary_dilation

from rainier3d.config.domain import REPO, load_domain
from rainier3d.io.store import read_tree, write
from rainier3d.surface import terrain as T
from rainier3d.surface.dem import fetch_3dep
from rainier3d.surface.mass_movements import EVENT_CLASSES, FLOW_CLASSES

FIG = REPO / "docs" / "paper" / "figures" / "fig22_terrain_geometry.png"


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--dem", default="", help="3DEP GeoTIFF (default: fetch_3dep cache)")
    ap.add_argument("--model", default="", help="model.zarr with the surface ice_thickness")
    ap.add_argument("--mass-movements", default="", help="directory with S24 events.gpkg and flows.gpkg")
    ap.add_argument("--atlas", default=str(REPO / "web" / "viewer" / "site" / "public" / "atlas"))
    ap.add_argument("--no-figure", action="store_true")
    a = ap.parse_args()
    dom, cfg = load_domain(), T.load_config()
    res = float(cfg["grid"]["res_m"])

    t0 = time.time()
    if a.dem:
        src_dem = xr.open_dataarray(Path(a.dem).expanduser(), engine="rasterio").squeeze("band", drop=True)
    else:
        src_dem = fetch_3dep(dom, int(cfg["elevation"]["fetch_res_m"]))
    z = T.dem_on(dom, src_dem, res)
    model = Path(a.model).expanduser() if a.model else dom.path("processed") / "model.zarr"
    ice = read_tree(model)["surface"].to_dataset()["ice_thickness"]
    ds = T.build(dom, z, ice, cfg)
    ds.attrs |= {"dem": str(a.dem or "fetch_3dep"), "ice_source_store": str(model)}
    store = write(ds.chunk({"y": 500, "x": 500}), dom.path("processed") / "terrain_geometry.zarr")
    logging.info(
        "%s: %d x %d cells of %g m in %.0f s", store, ds.sizes["x"], ds.sizes["y"], res, time.time() - t0
    )

    out = dom.path("outputs") / "terrain"
    out.mkdir(parents=True, exist_ok=True)
    pct = {
        k: [round(float(v), 1) for v in np.nanpercentile(ds[k].values, [10, 50, 90, 99])]
        for k in (*T.LAYERS, "ice_thickness")
    }
    glacier = ds["ice_thickness"].values > cfg["ice"]["outline_m"]
    # off ice: no ice in the cell or its 8 neighbours, which the central-difference stencil reaches
    off_ice = ~binary_dilation(ds["ice_thickness"].values > 0, np.ones((3, 3), bool))
    summary = {
        "grid": {
            "res_m": res,
            "nx": ds.sizes["x"],
            "ny": ds.sizes["y"],
            "crs": dom.crs,
            "x0": float(ds.x[0] - res / 2),
            "y0": float(ds.y[0] - res / 2),
        },
        "radii_m": {
            "local_relief": ds.attrs["local_relief_radius_m"],
            "valley_depth": ds.attrs["valley_depth_radius_m"],
        },
        "inputs": {"dem": ds.attrs["dem"], "model": str(model)},
        "percentiles_10_50_90_99": pct,
        "ice_over_outline_km2": round(float(glacier.sum()) * res * res / 1e6, 1),
        "max_abs_slope_difference_off_ice_deg": float(
            np.abs(ds["surface_slope"] - ds["bedrock_slope"]).values[off_ice].max()
        ),
    }

    mm = Path(a.mass_movements).expanduser() if a.mass_movements else dom.path("outputs") / "mass_movements"
    if (mm / "events.gpkg").exists() and (mm / "flows.gpkg").exists():
        events, flows = gpd.read_file(mm / "events.gpkg"), gpd.read_file(mm / "flows.gpkg")
        th = {k: float(cfg["thresholds"][k]) for k in T.LAYERS}
        tab, off = T.compare(
            ds, events.to_crs(dom.crs), flows.to_crs(dom.crs), th, EVENT_CLASSES, FLOW_CLASSES
        )
        tab.to_csv(out / "mass_movement_terrain.csv", index=False)
        summary["mass_movements"] = {"dir": str(mm), "events": len(events), "events_off_grid": off}
        logging.info(
            "mass movements vs terrain (%d events off the grid):\n%s", off, tab.to_string(index=False)
        )
    else:
        logging.info("no S24 catalogue at %s: comparison skipped", mm)
    (out / "summary.json").write_text(json.dumps(summary, indent=1))
    logging.info("summary: %s", json.dumps(summary))

    if not a.no_figure:
        from rainier3d.report.figures import fig_terrain_geometry

        logging.info("figure %s", fig_terrain_geometry(ds, dom, cfg, FIG).relative_to(REPO))

    atlas = Path(a.atlas).expanduser()
    if (atlas / "model" / "layers.json").exists():
        from rainier3d.export.atlas import append_terrain_layers

        logging.info("viewer: %s -> %s", ", ".join(append_terrain_layers(atlas, dom, ds)), atlas / "model")
    else:
        logging.info("no viewer bundle at %s: run pixi run viewer-data and s11 first", atlas)


if __name__ == "__main__":
    main()
