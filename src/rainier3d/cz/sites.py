"""Sites of the critical-zone synthetics (S33, S34; configs/cz.yaml) and the model column at each: the fine
critical-zone column of the model (rainier3d.cz.level) above its L1 cells."""

from __future__ import annotations

from types import SimpleNamespace

import xarray as xr
import yaml

from rainier3d.config.domain import REPO
from rainier3d.config.platform import local_input
from rainier3d.cz import synthetics as SY
from rainier3d.cz.level import context_from_disk
from rainier3d.export.atlas import is_temporary
from rainier3d.io.store import read_tree
from rainier3d.petro.table import perturbations, petro_table
from rainier3d.sensors import inventory as inv


def sites(dom, cfg) -> list[dict]:
    from pyproj import Transformer

    tf = Transformer.from_crs("EPSG:4326", dom.crs, always_xy=True)
    out = []
    fams = set(cfg["sites"]["permanent"]["families"])
    for s in inv.inventory(dom):
        if not s["in_model_domain"]:
            continue
        sens = s["sensors"]
        if s["id"].startswith(cfg["sites"]["nodes"]["network"] + "."):
            kind = "node"
        elif (
            s["source"].startswith("FDSN")
            and not is_temporary(s["id"], s["source"])
            and any(x.get("status") == "operating" and x.get("family") in fams for x in sens)
        ):
            kind = "permanent"
        else:
            continue
        out.append({"id": s["id"], "kind": kind, "lon": s["lon"], "lat": s["lat"]})
    das = inv.das_channels(local_input("das_channels", dom.path("raw")))
    for _, r in das.iloc[:: cfg["sites"]["das_every"]].iterrows():
        out.append(
            {"id": f"DAS.{int(r.Channel):04d}", "kind": "das", "lon": float(r.lon), "lat": float(r.lat)}
        )
    for s in out:
        s["x"], s["y"] = tf.transform(s["lon"], s["lat"])
    return sorted(out, key=lambda s: (s["kind"], s["id"]))


def model(dom) -> SimpleNamespace:
    """The critical-zone context and the L1 levels the synthetics are taken from: the geology model's L1
    (units, alteration) for the fine columns, and the fused L1 of model.zarr below them."""
    geo = read_tree(dom.path("processed") / "geomodel.zarr")
    cal_path = REPO / "configs" / "velocity_calibration.yaml"
    cal = yaml.safe_load(cal_path.read_text()) if cal_path.exists() else {}
    fused = xr.open_datatree(dom.path("processed") / "model.zarr", engine="zarr", consolidated=False)
    return SimpleNamespace(
        cz=context_from_disk(dom, geo),
        level=geo["L1"].to_dataset().load(),
        L1=fused["L1"].to_dataset()[["vp", "vs", "rho", "depth"]].load(),
        table=petro_table(),
        pert=perturbations(),
        geo_cal=cal.get("geology"),
    )


def site_column(m: SimpleNamespace, site: dict, head=None, water_table_shift: float = 0.0, override=None):
    """(disba column, fine column) at the site, or ("glacier", None) under ice. ``water_table_shift`` (m,
    positive deeper) moves the hydrostatic head; ``head`` replaces it over the top layers."""
    c = m.cz.column(m.level, site["x"], site["y"], m.table, m.pert, m.geo_cal, override=override)
    if c["ice_thickness"] > 0:
        return "glacier", None
    if head is not None or water_table_shift:
        wt = float(c["z"][0] - c["head"][0])  # the scenario water table stays at or below the ground
        h = c["z"] - max(wt + water_table_shift, 0.0) if head is None else head
        c = m.cz.column(m.level, site["x"], site["y"], m.table, m.pert, m.geo_cal, head=h, override=override)
    j, i = c["column_index"]
    L = m.L1.isel(y=j, x=i)
    col = SY.stack(c, L.depth.values, L.vp.values, L.vs.values, L.rho.values)
    return col, c
