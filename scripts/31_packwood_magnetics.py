"""S31: terrain-correlated apparent magnetisation of the 2022 Packwood aeromagnetic survey (Blakely et al.
2024) merged with that of the 1996 helicopter survey of the edifice (S22), with glacier ice counted as rock
(as S22) and with it left out.

Reads:
  Packwood survey   ScienceBase item of configs/magnetics.yaml, cached in data/raw/packwood_aeromag/: the
                    total-field anomaly grid and the flight lines (drape surface, 760 MB CSV)
  1996 survey       data/raw/rainier_aerogeophysics/ (rainier3d.alteration.aerogeophysics.fetch, as S22)
  model surface     elevation, ice thickness (IceBoost v2) and the S22 field of model.zarr, or --model PATH

Writes:
  data/processed/packwood_magnetics.zarr   on the model surface grid: the 2022 anomaly and its reduction to
                                           the pole, the drape surface, the apparent magnetisation of each
                                           survey (ice as rock, ice excluded), the 1996 weight and the two
                                           merged fields
  outputs/magnetics/summary.json           field direction, registration, clearances, overlap agreement
  <atlas>/model/<layer>.webp, .u16.bin and layers.json entries (group "Geology"), if the viewer bundle exists

Parameters: configs/magnetics.yaml. Method: rainier3d.alteration.packwood (2022, merge) and
rainier3d.alteration.finn2001 (1996).

Usage: pixi run s31
       pixi run s31 -- --model ~/.cache/rainier3d/model/extracted/model.zarr
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from pathlib import Path

import numpy as np
import xarray as xr
import yaml
from pyproj import Transformer

from rainier3d.alteration import aerogeophysics as A
from rainier3d.alteration import finn2001 as F
from rainier3d.alteration import packwood as P
from rainier3d.config.domain import REPO, load_domain
from rainier3d.io.store import provenance, read_tree, write

CONFIG = REPO / "configs" / "magnetics.yaml"
SRC_1996 = ["rystrom_2000", "finn_2001", "usgs_3dep"]
SRC_2022 = ["blakely_2024", "igrf13", "usgs_3dep"]
SRC_MERGED = ["rystrom_2000", "finn_2001", "blakely_2024", "igrf13", "usgs_3dep"]


def pct(a, q=(1, 10, 50, 90, 99)):
    return [round(float(v), 2) for v in np.nanpercentile(a, q)]


def agreement(a, b):
    ok = np.isfinite(a) & np.isfinite(b)
    return {"cells": int(ok.sum()), "corr": round(float(np.corrcoef(a[ok], b[ok])[0, 1]), 3),
            "median_2022_minus_1996": round(float(np.median(a[ok] - b[ok])), 3)}  # fmt: skip


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="", help="model.zarr with the surface elevation and ice_thickness")
    ap.add_argument("--atlas", default=str(REPO / "web" / "viewer" / "site" / "public" / "atlas"))
    a = ap.parse_args()
    dom, cfg = load_domain(), yaml.safe_load(CONFIG.read_text())
    x, y, dx = dom.x, dom.y, dom.surface_res_m
    model = Path(a.model).expanduser() if a.model else dom.path("processed") / "model.zarr"
    s = read_tree(model)["surface"].to_dataset()
    if not (np.allclose(s.x, x) and np.allclose(s.y, y)):
        raise SystemExit(f"{model}: surface grid differs from the domain")
    E = s["elevation"]
    bed = E - s["ice_thickness"].fillna(0.0)
    summary = {"model": str(model), "config": json.loads(json.dumps(cfg))}

    # ---- 2022 Packwood survey ----
    t0 = time.time()
    sv, fd, am = cfg["survey"], cfg["field"], cfg["apparent_magnetization"]
    raw = P.fetch(dom.path("raw") / "packwood_aeromag", sv["sciencebase_item"], sv["files"])
    tmi_n = P.read_grid(raw / P.GRID)
    inc, dec, pad = fd["inclination_deg"], fd["declination_deg"], cfg["rtp"]["pad_fraction"]
    rtp_n = P.reduce_to_pole(tmi_n, inc, dec, pad)
    tmi, rtp = P.onto(tmi_n, x, y), P.onto(rtp_n, x, y)
    flipped = P.onto(P.reduce_to_pole(tmi_n.copy(data=tmi_n.values[::-1]), inc, dec, pad), x, y)
    reg = {"as_read": P.highpass_corr(rtp, E.values), "flipped_ns": P.highpass_corr(flipped, E.values)}
    logging.info("2022 registration, corr(high-passed RTP, topography): %s", reg)
    if reg["as_read"] < cfg["registration"]["min_corr"] or reg["as_read"] <= reg["flipped_ns"]:
        raise SystemExit(f"the 2022 grid looks mis-registered: {reg}")
    drape = P.sensor_elevation(raw / P.LINES, x, y, cfg["drape"]["csv_step"])
    drape = np.where(np.isfinite(tmi), drape, np.nan)
    h = np.maximum(drape, E.values + am["sensor_floor_m"])
    h = np.nan_to_num(h, nan=np.nanmax(h))  # only cells with data are evaluated
    m22 = {}
    for case, top in (("ice", E.values), ("icefree", bed.values)):
        G = P.terrain_effect(top, x, y, h, np.isfinite(rtp), am["reach_m"])
        m22[case] = P.local_slope(rtp, G, dx, am["window_sigma_m"])
    clear = drape - E.values
    summary["2022"] = {
        "coverage_of_domain": round(float(np.isfinite(tmi).mean()), 3),
        "registration_corr": {k: round(v, 3) for k, v in reg.items()},
        "clearance_m_p10_50_90": pct(clear, (10, 50, 90)),
        "seconds": round(time.time() - t0),
    }
    logging.info("2022 survey: %s", summary["2022"])

    # ---- 1996 helicopter survey, as S22 ----
    raw96 = A.fetch(dom.path("raw") / "rainier_aerogeophysics")
    em = A.read_grid(raw96, "33k")  # the survey footprint as S22 takes it, so the 1996 field is the S22 one
    cx, cy = Transformer.from_crs(A.NAD27_UTM10, dom.crs, always_xy=True).transform(
        [float(em.x.min()), float(em.x.max())], [float(em.y.min()), float(em.y.max())]
    )
    ix = (x >= min(cx) - 200) & (x <= max(cx) + 200)
    iy = (y >= min(cy) - 200) & (y <= max(cy) + 200)
    m96, info96 = {}, {}
    for case, top in (("ice", None), ("icefree", bed)):
        sub, info96[case] = F.apparent_magnetization(raw96, E, x[ix], y[iy], dom.crs, top=top)
        m96[case] = np.full(E.shape, np.nan)
        m96[case][np.ix_(iy, ix)] = sub
    summary["1996"] = {"magnetization": info96}
    if "apparent_magnetization" in s:  # the S22 field: ice-as-rock 1996 must reproduce it
        summary["1996"]["max_abs_diff_vs_model_s22_field"] = float(
            np.nanmax(np.abs(m96["ice"] - s["apparent_magnetization"].values))
        )

    # ---- merge ----
    merged, w = P.blend(m96["ice"], m22["ice"])
    merged_icefree, _ = P.blend(m96["icefree"], m22["icefree"])
    ring = np.isfinite(m96["ice"]) & np.isfinite(m22["ice"])
    summary["overlap"] = {
        "cells": int(ring.sum()),
        "ice_as_rock": agreement(m22["ice"], m96["ice"]),
        "ice_excluded": agreement(m22["icefree"], m96["icefree"]),
    }
    summary["percentiles_1_10_50_90_99"] = {
        "merged": pct(merged),
        "merged_icefree": pct(merged_icefree),
        "icefree_minus_ice_where_ice_gt_10m": pct((merged_icefree - merged)[s["ice_thickness"].values > 10]),
    }

    def var(v, name, keys, units, long_name):
        da = xr.DataArray(v.astype("float32"), coords={"y": y, "x": x}, dims=("y", "x"), name=name,
                          attrs={"units": units, "long_name": long_name})  # fmt: skip
        return provenance(da, keys, name, dx)

    ice_note = "glacier ice (IceBoost v2) left out of the magnetised terrain"
    ds = xr.Dataset(
        {
            "tmi_2022": var(tmi, "tmi_2022", ["blakely_2024"], "nT", "2022 total-field anomaly (MAGRES)"),
            "rtp_2022": var(
                rtp, "rtp_2022", ["blakely_2024", "igrf13"], "nT", "2022 anomaly reduced to the pole"
            ),
            "drape_2022": var(
                drape,
                "drape_2022",
                ["blakely_2024"],
                "m",
                "2022 drape surface, m above mean sea level (channel DRAPE)",
            ),
            "apparent_magnetization_2022": var(
                m22["ice"], "apparent_magnetization_2022", SRC_2022, "A/m", "2022 survey, ice as rock"
            ),
            "apparent_magnetization_2022_icefree": var(
                m22["icefree"],
                "apparent_magnetization_2022_icefree",
                SRC_2022 + ["iceboost_v2"],
                "A/m",
                f"2022 survey, {ice_note}",
            ),
            "apparent_magnetization_1996": var(
                m96["ice"],
                "apparent_magnetization_1996",
                SRC_1996,
                "A/m",
                "1996 survey, ice as rock (the S22 field)",
            ),
            "apparent_magnetization_1996_icefree": var(
                m96["icefree"],
                "apparent_magnetization_1996_icefree",
                SRC_1996 + ["iceboost_v2"],
                "A/m",
                f"1996 survey, {ice_note}",
            ),
            "weight_1996": var(
                w,
                "weight_1996",
                ["rystrom_2000", "blakely_2024"],
                "1",
                "weight of the 1996 field in the merge",
            ),
            "apparent_magnetization_merged": var(
                merged,
                "apparent_magnetization_merged",
                SRC_MERGED,
                "A/m",
                "1996 and 2022 surveys merged, ice as rock",
            ),
            "apparent_magnetization_merged_icefree": var(
                merged_icefree,
                "apparent_magnetization_merged_icefree",
                SRC_MERGED + ["iceboost_v2"],
                "A/m",
                f"1996 and 2022 surveys merged, {ice_note}",
            ),
        },  # fmt: skip
        attrs={
            "crs": dom.crs,
            "window_sigma_m_1996": info96["ice"]["window_sigma_m"],
            "window_sigma_m_2022": float(am["window_sigma_m"]),
            "summary": json.dumps(summary),
        },
    )
    store = write(ds, dom.path("processed") / "packwood_magnetics.zarr")
    out = dom.path("outputs") / "magnetics"
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps(summary, indent=1))
    logging.info("%s; summary: %s", store, json.dumps({k: v for k, v in summary.items() if k != "config"}))

    atlas = Path(a.atlas).expanduser()
    if (atlas / "model" / "layers.json").exists():
        from rainier3d.export.atlas import append_magnetization_layers

        keys = append_magnetization_layers(atlas, dom, ds, cfg["viewer"])
        logging.info("viewer: %s -> %s", ", ".join(keys), atlas / "model")
    else:
        logging.info("no viewer bundle at %s: run pixi run viewer-data and s11 first", atlas)


if __name__ == "__main__":
    main()
