"""S5: fuse the geology model with the regional model -> data/processed/model.zarr.

model.zarr is the master product: /surface, /soil (the S2 soil profiles) and /L1, /L2, /L3 with unit,
alteration, depth, the fused vp, vs, rho, qp, qs, and the two inputs (``*_geology``, ``*_regional``) for
comparison.
Vs and Vp/Vs are fused (Vp = Vs * Vp/Vs), then the magma-body anomaly is applied to the fused model.
The regional Vp and Vs are first multiplied by the static bias of configs/velocity_calibration.yaml
(S13); without that file, by the Vs-only factor of configs/vs_calibration.yaml (S12). The geology part
of the S13 calibration enters in S4. The level recipe is rainier3d.fusion.build, shared with S13.
Writes outputs/fusion_report.csv with the low-pass misfit per level for Vp and Vs.
"""

from __future__ import annotations

import argparse
import logging

import pandas as pd
import xarray as xr
import yaml

from rainier3d.config.domain import REPO, load_domain
from rainier3d.fusion import build, regional
from rainier3d.io.store import read, read_tree, write
from rainier3d.petro.table import perturbations


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default=None)
    ap.add_argument(
        "--no-vs-calibration",
        "--no-calibration",
        dest="no_calibration",
        action="store_true",
        help="ignore the velocity calibration (to build the base model of S12/S13)",
    )
    ap.add_argument("--properties", default="properties_geology.zarr", help="S4 store under data/processed")
    ap.add_argument("--out", default="model.zarr", help="store name under data/processed")
    a = ap.parse_args()
    dom = load_domain(a.profile)
    fc = dom.cfg["fusion"]
    cal_files = [REPO / "configs" / f for f in ("velocity_calibration.yaml", "vs_calibration.yaml")]
    cal_path = next((p for p in cal_files if p.exists()), None)
    cal = None if a.no_calibration or cal_path is None else yaml.safe_load(cal_path.read_text())
    geo = read_tree(dom.path("processed") / "geomodel.zarr")
    props = read_tree(dom.path("processed") / a.properties)
    cvm, cres = regional.load_cvm(dom), regional.load_crescent(dom)
    pert = perturbations()
    q = pert["q"]

    surf = geo["surface"].to_dataset()
    env = dom.path("processed") / "surface_layers.zarr"
    if env.exists():  # S2 environmental layers share the surface grid
        surf = surf.merge(read(env), compat="override", combine_attrs="drop_conflicts")
    nodes, report = {"/surface": surf}, []
    if "cz" in props:  # the S4 critical-zone columns on the L1 grid
        nodes["/cz"] = props["cz"].to_dataset()
    soil = dom.path("processed") / "soil_profile.zarr"
    if soil.exists():  # S2 soil profiles (SOLUS points, POLARIS layers), surface grid, depth below ground
        nodes["/soil"] = read(soil)
    for name, lev in dom.levels.items():
        g, p = geo[name].to_dataset(), props[name].to_dataset()
        reg = build.regional_level(lev, g["depth"].values, cvm, cres, cal, fc)
        out, rows = build.fuse_level(g, p, reg, lev, fc, q, name, magma=pert["magma_mush"])
        report += rows
        if cal is not None:
            out.attrs["vs_calibration"] = f"configs/{cal_path.name} ({cal['date']})"
        nodes[f"/{name}"] = out

    from rainier3d.io.attrs import CZ, LEVEL, describe

    for k, ds in nodes.items():  # units and descriptions of every variable (docs/velocity_model.md)
        if k in ("/L1", "/L2", "/L3"):
            describe(ds, LEVEL)
        elif k == "/cz":
            describe(ds, CZ)
    tree = xr.DataTree.from_dict(nodes)
    tree.attrs = {
        "crs": dom.crs,
        "vertical_datum": dom.vertical_datum,
        "domain": dom.name,
        "method": "M1: rule-based geology + petrophysics, fused with CVM v1.7 / CRESCENT Gen0",
    }
    write(tree, dom.path("processed") / a.out)
    rep = pd.DataFrame(report)
    stem = (
        "" if a.out == "model.zarr" else "_" + a.out.removesuffix(".zarr")
    )  # the invariant reads the default
    rep.to_csv(dom.path("outputs") / f"fusion_report{stem}.csv", index=False)
    logging.info("\n%s", rep.to_string(index=False, float_format=lambda v: f"{v:.4f}"))


if __name__ == "__main__":
    main()
