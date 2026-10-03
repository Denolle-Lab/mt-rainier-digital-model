"""S34: critical-zone response to the December 2025 storm at the stations ->
data/processed/cz_storm_<event>.zarr and outputs/cz/ (storm_summary.json, storm figure). Build step 3 of
docs/critical_zone.md.

At each site of S33 (rainier3d.cz.sites), the model's own column (the medium of S4) is wetted by the hourly
MRMS rain of the event (S29, data/processed/events/<event>.zarr) through the 1D Richards solver of
rainier3d.cz.richards, from the static water table (Ma et al. 2026) as initial and bottom condition. Every
few hours the column is rebuilt from the pressure-head profile and its Rayleigh phase velocity gives dv/v
relative to the start of the event, at the frequencies of configs/cz.yaml (richards.frequencies_hz). Rain
falls as rain everywhere (no snow yet), with no lateral flow, interception or evapotranspiration: the
placeholders of the build plan.

Usage: pixi run s34
"""

from __future__ import annotations

import json
import logging

import numpy as np
import xarray as xr
import yaml

from rainier3d.config.domain import REPO, load_domain
from rainier3d.cz import richards as RI
from rainier3d.cz import sites as CS
from rainier3d.cz import synthetics as SY
from rainier3d.io.store import write

log = logging.getLogger("s34")


def domain(fine: dict, base_m: float, cfg: dict) -> tuple[RI.Column, np.ndarray]:
    """The fine layers of the model column above base_m as a Richards column: van Genuchten parameters and
    permeability of the model (converted to hydraulic conductivity), and the water table of the model as the
    fixed head at the bottom, or free drainage when it lies deeper."""
    z, dz = fine["z"], fine["dz"]
    idx = np.flatnonzero(z + dz / 2 <= base_m)
    wt = float(z[0] - fine["head"][0])
    rp, md = cfg["rock_physics"], cfg["medium"]
    ksat = (
        10 ** fine["log10_permeability"][idx] * rp["water_density_kgm3"] * 9.81 / md["water_viscosity_pa_s"]
    )
    c = RI.Column(
        dz=dz[idx],
        z=z[idx],
        theta_r=fine["theta_r"][idx],
        theta_s=fine["theta_s"][idx],
        alpha=fine["alpha"][idx],
        n=fine["n"][idx],
        ksat=ksat,
        bottom_head=z[idx][-1] - wt if wt < z[idx][-1] else None,
    )
    return c, fine["head"][idx].copy()


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    dom = load_domain()
    cfg = yaml.safe_load((REPO / "configs" / "cz.yaml").read_text())
    rc = cfg["richards"]
    m = CS.model(dom)
    ev = xr.open_datatree(
        dom.path("processed") / "events" / f"{rc['event']}.zarr", engine="zarr", consolidated=False
    )
    rain = ev["rain"].to_dataset()["rain"].load()  # mm per hour, ending at each time stamp
    f = np.array(rc["frequencies_hz"], float)
    every = rc["output_every_h"]
    times = np.concatenate(
        [[rain.time.values[0] - np.timedelta64(1, "h")], rain.time.values[every - 1 :: every]]
    )
    S = CS.sites(dom, cfg)
    n, nt, nf = len(S), len(times), len(f)
    dvv = np.full((n, nt, nf), np.nan)
    sat_depth = np.full((n, nt), np.nan)
    totals = {k: np.full(n, np.nan) for k in ("rain", "infiltration", "runoff", "bottom", "storage_change")}
    status = []
    for i, s in enumerate(S):
        col0, fine = CS.site_column(m, s)
        if fine is None:
            status.append(col0)
            continue
        c, h0 = domain(fine, rc["base_m"], cfg)
        r = rain.sel(x=s["x"], y=s["y"], method="nearest").values.astype(float) / 1000 / 3600  # m/s
        try:
            H, tot = RI.run(c, h0, r, 3600.0, rc["dt_s"], rc["picard_tol_m"], rc["picard_max"], every)
        except RuntimeError as e:
            log.warning("%s: %s", s["id"], e)
            status.append("solver_failed")
            continue
        c0 = SY.phase_velocity(col0, f)
        for k, h in enumerate(H):
            dvv[i, k] = SY.phase_velocity(CS.site_column(m, s, head=h)[0], f) / c0 - 1
            wet = np.flatnonzero(h >= 0)
            sat_depth[i, k] = c.z[wet[0]] if wet.size else np.nan
        for key in totals:
            totals[key][i] = tot[key]
        status.append("ok")
        if i % 50 == 0:
            log.info("%d/%d %s rain %.0f mm", i, n, s["id"], 1000 * tot["rain"])
    ds = xr.Dataset(
        {
            "dvv": (("site", "time", "frequency"), dvv.astype("float32")),
            "saturated_depth": (("site", "time"), sat_depth.astype("float32")),
            **{f"{k}_m": ("site", v.astype("float32")) for k, v in totals.items()},
            "status": ("site", np.array(status)),
            "kind": ("site", np.array([s["kind"] for s in S])),
            "lon": ("site", np.array([s["lon"] for s in S])),
            "lat": ("site", np.array([s["lat"] for s in S])),
        },
        coords={"site": [s["id"] for s in S], "time": times, "frequency": f},
        attrs={
            "event": rc["event"],
            "synthetic": "yes: a simulation driven by observed rain; no seismic data enter it, and the nodes "
            "and the DAS were not recording during this event",
            "note": "Build step 3 of docs/critical_zone.md: placeholder layers and rock physics, no snow, "
            "lateral flow, interception or evapotranspiration; dv/v relative to the first time",
        },
    )
    write(ds, dom.path("processed") / f"cz_storm_{rc['event']}.zarr")
    out = dom.path("outputs") / "cz"
    out.mkdir(parents=True, exist_ok=True)
    summ = summarise(ds)
    (out / "storm_summary.json").write_text(json.dumps(summ, indent=1))
    figure(ds, rain, out / f"cz_storm_{rc['event']}.png")
    log.info("%s", json.dumps(summ, indent=1))


def summarise(ds: xr.Dataset) -> dict:
    ok = ds.status == "ok"
    out = {"status": {k: int((ds.status == k).sum()) for k in np.unique(ds.status.values)}}
    bal = (ds.infiltration_m - ds.bottom_m - ds.storage_change_m).where(ok)
    out["max_abs_mass_balance_error_mm"] = round(float(1000 * np.abs(bal).max()), 4)
    for kind in ("permanent", "node", "das"):
        d = ds.where(ok & (ds.kind == kind), drop=True)
        if not d.sizes.get("site"):
            continue
        out[kind] = {
            "sites": int(d.sizes["site"]),
            "rain_mm_p50": round(float(1000 * d.rain_m.median()), 0),
            "runoff_fraction_p50": round(float((d.runoff_m / d.rain_m).median()), 3),
            "min_dvv_pct_p50": {
                f"{f:g}": round(100 * float(d.dvv.sel(frequency=f).min("time").median()), 3)
                for f in d.frequency.values
            },
            "min_dvv_pct_p10": {
                f"{f:g}": round(100 * float(d.dvv.sel(frequency=f).min("time").quantile(0.1)), 3)
                for f in d.frequency.values
            },
        }
    return out


def figure(ds: xr.Dataset, rain: xr.DataArray, path):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ok = ds.status == "ok"
    fig, axs = plt.subplots(len(ds.frequency) + 1, 1, figsize=(8, 8), sharex=True, constrained_layout=True)
    axs[0].bar(rain.time.values, rain.mean(("y", "x")).values, width=1 / 24, color="0.4")
    axs[0].set_ylabel("rain, box mean\n(mm/h)")
    colors = {"permanent": "#d95926", "node": "#199e70", "das": "#157db3"}
    for ax, fq in zip(axs[1:], ds.frequency.values, strict=True):
        for kind, col in colors.items():
            d = ds.where(ok & (ds.kind == kind), drop=True)
            if not d.sizes.get("site"):
                continue
            v = 100 * d.dvv.sel(frequency=fq)
            ax.plot(d.time, v.median("site"), color=col, label=f"{kind} ({d.sizes['site']})")
            ax.fill_between(d.time.values, *v.quantile([0.1, 0.9], "site").values, color=col, alpha=0.15)
        ax.set_ylabel(f"dv/v at {fq:g} Hz (%)")
        ax.grid(alpha=0.3)
    axs[1].legend(fontsize=7, ncol=3)
    axs[0].set_title(
        "SYNTHETIC: simulated dv/v at station locations under the December 2025 storm rain (median, 10-90%);"
        " the nodes and DAS were not recording then",
        fontsize=8,
    )
    fig.savefig(path, dpi=160)
    plt.close(fig)


if __name__ == "__main__":
    main()
