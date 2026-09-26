"""S29: one hydrometeorological event (configs/events.yaml) -> data/processed/events/, outputs/events/,
the viewer.

Fetches (cached under data/raw/, see rainier3d.hydromet.events):
  mrms/                MRMS 1 h QPE, Pass 2, one GRIB2 file per hour of the window
  usgs_nwis/           USGS instantaneous discharge of every gauge in the domain box
  seis_hydro_2_sed/    virtual discharge and AR windows at the pinned commit

Writes:
  data/processed/events/<key>.zarr   DataTree: /rain (time, y, x; mm per hour, domain grid),
                                     /gauges and /virtual (site, time; m3/s, native sampling)
  outputs/events/<key>/peaks.csv     peak discharge and time of every gauge and virtual station
  outputs/events/<key>/rain.csv      domain-mean rain per hour (mm)
  outputs/events/<key>/summary.json  the numbers quoted in the report: totals, AR windows, rain by elevation
                                     band and on glaciers (needs --model or data/processed/model.zarr), lags
  docs/paper/figures/fig21_flood_event.png (with the model surface)
  <atlas>/events/<key>/rain.u8.bin, event.json and <atlas>/events/index.json, if the viewer bundle exists

This is the scaffold of the time-dependent model: the forcing and the river response are stored on the domain,
and nothing is coupled to them yet.

Usage: pixi run s29 [-- --event dec2025_ar --atlas web/viewer/site/public/atlas]
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import pandas as pd
import xarray as xr

from rainier3d.config.domain import REPO, load_domain
from rainier3d.hydromet import events as E
from rainier3d.io.store import provenance, write

FIG = REPO / "docs" / "paper" / "figures" / "fig21_flood_event.png"


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--event", default="dec2025_ar")
    ap.add_argument("--model", default=None, help="model.zarr for elevation and ice (default: processed)")
    ap.add_argument("--atlas", default=str(REPO / "web" / "viewer" / "site" / "public" / "atlas"))
    a = ap.parse_args()
    dom, ev = load_domain(), E.load_event(a.event)
    raw = dom.path("raw")

    rain = E.rain(dom, ev, raw)
    provenance(rain, [ev["rain"]["source"]], "precipitation", ev["rain"]["grid_m"])
    gauges = E.in_box(E.gauges(E.fetch_nwis(dom, ev, raw)), dom)
    files = E.fetch_seis_hydro(ev, raw)
    virtual = E.in_box(
        E.virtual_discharge(files, ev["virtual_discharge"]["min_nse_logq"], ev["start"], ev["end"]), dom
    )
    # a seismometer read as a river gauge is a virtual sensor: it must be in configs/virtual_sensors.yaml
    from rainier3d.sensors.virtual import unregistered

    missing = unregistered([str(c) for c in virtual.site.values])
    if missing:
        raise SystemExit(f"virtual sensors without an entry in configs/virtual_sensors.yaml: {missing}")
    for ds, key in ((gauges, ev["gauges"]["source"]), (virtual, ev["virtual_discharge"]["source"])):
        provenance(ds.discharge, [key], "river discharge", 0.0)

    tree = xr.DataTree.from_dict(
        {"/rain": rain.to_dataset(), "/gauges": gauges, "/virtual": virtual},
    )
    tree.attrs.update(
        {"event": ev["key"], "title": ev["title"], "start": ev["start"], "end": ev["end"], "crs": dom.crs}
    )
    store = write(tree, dom.path("processed") / "events" / f"{ev['key']}.zarr")
    logging.info("wrote %s", store.relative_to(REPO))

    out = dom.path("outputs") / "events" / ev["key"]
    out.mkdir(parents=True, exist_ok=True)
    pk = pd.concat([E.peaks(gauges).assign(kind="gauge"), E.peaks(virtual).assign(kind="virtual")])
    pk.to_csv(out / "peaks.csv", index=False)
    rain.mean(("y", "x")).to_series().round(2).rename("domain_mean_mm").to_csv(out / "rain.csv")
    mp = Path(a.model).expanduser() if a.model else dom.path("processed") / "model.zarr"
    surface = (
        xr.open_datatree(mp, engine="zarr", consolidated=False)["surface"].to_dataset()
        if mp.exists()
        else None
    )
    if surface is None:
        logging.info("no model at %s: summary without the elevation and glacier numbers", mp)
    summ = E.summary(rain, gauges, files["ar_windows"], surface)
    (out / "summary.json").write_text(json.dumps(summ, indent=1))
    if surface is not None:
        from rainier3d.report.figures import fig_flood_event

        fig_flood_event(surface, rain, gauges, virtual, files["ar_windows"], summ, FIG)
        logging.info("wrote %s", FIG.relative_to(REPO))
    total = rain.sum("time")
    logging.info(
        "rain: %d h, domain-mean total %.0f mm, cell maximum %.0f mm, hourly maximum %.1f mm",
        rain.sizes["time"],
        float(total.mean()),
        float(total.max()),
        float(rain.max()),
    )
    logging.info("peaks:\n%s", pk.to_string(index=False))

    atlas = Path(a.atlas).expanduser()
    if (atlas / "manifest.json").exists():
        from rainier3d.export.atlas import append_event

        r = append_event(atlas, dom, ev, rain, gauges, virtual, files["ar_windows"])
        logging.info("viewer: %s -> %s", r, atlas / "events" / ev["key"])
    else:
        logging.info("no viewer bundle at %s: run pixi run viewer-data and s11 first", atlas)


if __name__ == "__main__":
    main()
