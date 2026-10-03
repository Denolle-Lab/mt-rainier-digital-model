"""S33: critical-zone columns and seismic synthetics at the stations -> data/processed/cz_synthetics.zarr and
outputs/cz/ (summary.json, figures). Build step 1 of docs/critical_zone.md.

Sites: the operating permanent seismic and strong-motion stations, the 2025 node array (Z5) and every Nth
channel of the Paradise-Nisqually DAS fibre (configs/cz.yaml). At each site the column is the model's own:
the fine critical-zone column of the medium of S4 (rainier3d.cz.level) above the model's L1 cells, and
rainier3d.cz.synthetics gives the Rayleigh phase velocity at 1-40 Hz, the depths holding 50% and 90% of its
sensitivity to Vs, the quarter-wavelength resonance, and dv/v for the water table 1 m shallower and 1 m
deeper. Glacier sites are listed but not computed.

Usage: pixi run s33
"""

from __future__ import annotations

import json
import logging

import numpy as np
import xarray as xr
import yaml

from rainier3d.config.domain import REPO, load_domain
from rainier3d.cz import sites as CS
from rainier3d.cz import synthetics as SY
from rainier3d.io.store import write

log = logging.getLogger("s33")


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    dom = load_domain()
    cfg = yaml.safe_load((REPO / "configs" / "cz.yaml").read_text())
    m = CS.model(dom)
    sy = cfg["synthetics"]
    f, fr, shifts = np.array(sy["frequencies_hz"], float), sy["kernel_fractions"], sy["water_table_shift_m"]
    S = CS.sites(dom, cfg)
    depth = m.cz.z
    n, nf, nz = len(S), len(f), len(depth)
    A = {
        k: np.full((n, nz), np.nan)
        for k in ("vs", "vp", "rho", "saturation", "sigma_eff", "weathering_index")
    }
    c0 = np.full((n, nf), np.nan)
    dvv = np.full((len(shifts), n, nf), np.nan)
    kd = np.full((n, nf, len(fr)), np.nan)
    meta = {
        k: np.full(n, np.nan)
        for k in ("f0_qwl", "water_table", "z_soil", "z_cover", "z_weathered", "z_fractured")
    }
    status = []
    for i, s in enumerate(S):
        col, fine = CS.site_column(m, s)
        if fine is None:
            status.append(col)
            continue
        for k in A:
            A[k][i] = fine[k]
        c0[i] = SY.phase_velocity(col, f)
        for j, sh in enumerate(shifts):
            dvv[j, i] = SY.phase_velocity(CS.site_column(m, s, water_table_shift=sh)[0], f) / c0[i] - 1
        kd[i] = SY.kernel_depths(col, f, fr)
        meta["f0_qwl"][i] = SY.quarter_wavelength_f0(col)
        meta["water_table"][i] = float(fine["z"][0] - fine["head"][0])
        for k, v in zip(("z_soil", "z_cover", "z_weathered", "z_fractured"), col["boundaries"], strict=True):
            meta[k][i] = v
        status.append("rock" if meta["z_soil"][i] == 0 else "ok")
    ds = xr.Dataset(
        {
            **{k: (("site", "depth"), v.astype("float32")) for k, v in A.items()},
            "phase_velocity": (("site", "frequency"), c0.astype("float32")),
            "dvv_water_table": (("shift", "site", "frequency"), dvv.astype("float32")),
            "kernel_depth": (("site", "frequency", "fraction"), kd.astype("float32")),
            **{k: ("site", v.astype("float32")) for k, v in meta.items()},
            "status": ("site", np.array(status)),
            "kind": ("site", np.array([s["kind"] for s in S])),
            "lon": ("site", np.array([s["lon"] for s in S])),
            "lat": ("site", np.array([s["lat"] for s in S])),
        },
        coords={
            "site": [s["id"] for s in S],
            "depth": depth,
            "frequency": f,
            "shift": shifts,
            "fraction": fr,
        },
        attrs={
            "synthetic": "yes: forward-modelled from the rainier3d model (its critical-zone columns and L1) "
            "at the station, node and DAS locations; no seismic data enter it",
            "note": "Build step 1 of docs/critical_zone.md, on the medium of S4 (configs/cz.yaml medium); "
            "placeholder parameters",
            "units": "vs, vp m/s; rho kg/m3; sigma_eff Pa; depth m below ground (layer centres); "
            "dvv fraction",
        },
    )
    write(ds, dom.path("processed") / "cz_synthetics.zarr")
    summary = summarise(ds)
    out = dom.path("outputs") / "cz"
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps(summary, indent=1))
    figure(ds, out / "cz_synthetics.png")
    log.info("%s", json.dumps(summary, indent=1))


def summarise(ds: xr.Dataset) -> dict:
    ok = ds.status.isin(["ok", "rock"])
    out = {"sites": {k: int((ds.kind == k).sum()) for k in ("permanent", "node", "das")}}
    out["status"] = {k: int((ds.status == k).sum()) for k in np.unique(ds.status.values)}
    for kind in ("permanent", "node", "das"):
        m = ok & (ds.kind == kind)
        if not m.any():
            continue
        d = ds.where(m, drop=True)
        out[kind] = {
            "f0_qwl_hz_p50": round(float(d.f0_qwl.median()), 2),
            "depth50_m_p50": {
                f"{f:g}": round(float(d.kernel_depth.sel(frequency=f, fraction=0.5).median()), 1)
                for f in d.frequency.values
            },
            "dvv_pct_wt_shallower_1m_p50": {
                f"{f:g}": round(100 * float(d.dvv_water_table.sel(shift=-1.0, frequency=f).median()), 3)
                for f in d.frequency.values
            },
        }
    return out


def figure(ds: xr.Dataset, path):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ok = ds.status.isin(["ok", "rock"])
    fig, axs = plt.subplots(1, 3, figsize=(11, 3.6), constrained_layout=True)
    colors = {"permanent": "#d95926", "node": "#199e70", "das": "#157db3"}
    for kind, col in colors.items():
        d = ds.where(ok & (ds.kind == kind), drop=True)
        if not d.sizes.get("site"):
            continue
        f = d.frequency.values
        lab = f"{kind} ({d.sizes['site']})"
        axs[0].plot(f, d.phase_velocity.median("site"), color=col, label=lab)
        axs[0].fill_between(f, *d.phase_velocity.quantile([0.1, 0.9], "site").values, color=col, alpha=0.15)
        axs[1].plot(f, d.kernel_depth.sel(fraction=0.5).median("site"), color=col, label=lab)
        axs[2].plot(f, 100 * d.dvv_water_table.sel(shift=-1.0).median("site"), color=col, label=lab)
        axs[2].fill_between(
            f,
            *(100 * d.dvv_water_table.sel(shift=-1.0).quantile([0.1, 0.9], "site")).values,
            color=col,
            alpha=0.15,
        )
    axs[0].set(
        xscale="log",
        yscale="log",
        xlabel="frequency (Hz)",
        ylabel="Rayleigh phase velocity (m/s)",
        title="(a) SYNTHETIC dispersion, median and 10-90%",
    )
    axs[1].set(
        xscale="log",
        yscale="log",
        xlabel="frequency (Hz)",
        ylabel="depth above which 50% of Vs sensitivity (m)",
        title="(b) depth sampled",
    )
    axs[1].invert_yaxis()
    axs[2].set(
        xscale="log", xlabel="frequency (Hz)", ylabel="dv/v (%)", title="(c) water table 1 m shallower"
    )
    for ax in axs:
        ax.grid(alpha=0.3)
        ax.legend(fontsize=7)
    fig.savefig(path, dpi=160)
    plt.close(fig)


if __name__ == "__main__":
    main()
