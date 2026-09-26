"""Events: hourly rain, river gauges and seismic virtual discharge for one storm (configs/events.yaml).

Sources, as data/raw/ cache folder -> configs/sources.yaml key:
  mrms/<product>/<YYYYMMDD>/  mrms_qpe          MRMS 1 h QPE (Pass 2), CONUS GRIB2 on a 0.01 deg grid
  usgs_nwis/                  usgs_nwis_iv      USGS instantaneous discharge of every gauge in the domain box
  seis_hydro_2_sed/<commit>/  seis_hydro_2_sed  virtual discharge, its rating fits, station tables, AR windows

MRMS files are named by the end of their accumulation hour, so frame t holds the rain of (t - 1 h, t]. The
rain is stored on the domain grid (UTM 10N, cell centres from the domain bounds at `grid_m`), rows south to
north like every surface array of the model. Missing MRMS hours become NaN frames and are reported.
"""

from __future__ import annotations

import gzip
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
import requests
import xarray as xr
import yaml
from affine import Affine
from rasterio.warp import Resampling, reproject
from rasterio.windows import from_bounds

from rainier3d.config.domain import REPO, Domain

log = logging.getLogger(__name__)

CONFIG = REPO / "configs" / "events.yaml"
CFS_TO_M3S = 0.028316846592  # 1 ft3/s in m3/s (exact international foot)
NWIS = "https://nwis.waterservices.usgs.gov/nwis/iv/"
RAW_GITHUB = "https://raw.githubusercontent.com"


def load_event(key: str, config: Path = CONFIG) -> dict:
    ev = yaml.safe_load(Path(config).read_text())["events"][key]
    return {"key": key, **ev}


def hours(ev: dict) -> pd.DatetimeIndex:
    """End times of the hourly frames: start + 1 h ... end (UTC)."""
    return pd.date_range(pd.Timestamp(ev["start"]) + pd.Timedelta("1h"), pd.Timestamp(ev["end"]), freq="1h")


# ---- rain: MRMS ----
def mrms_path(t: pd.Timestamp, product: str, raw: Path) -> Path:
    return raw / "mrms" / product / f"{t:%Y%m%d}" / f"MRMS_{product}_{t:%Y%m%d-%H%M%S}.grib2"


def fetch_mrms(t: pd.Timestamp, rain: dict, raw: Path) -> Path | None:
    """Download and unzip one hourly file into the cache; None when the archive has no file for that hour."""
    p = mrms_path(t, rain["product"], raw)
    if p.exists():
        return p
    url = f"{rain['bucket']}/{rain['product']}/{t:%Y%m%d}/{p.name}.gz"
    r = requests.get(url, timeout=120)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(gzip.decompress(r.content))
    return p


def rain_grid(dom: Domain, grid_m: float) -> tuple[Affine, int, int]:
    """Transform (north-up) and size of the rain grid: the domain bounds at grid_m."""
    x0, y0, x1, y1 = dom.bounds
    nx, ny = int(round((x1 - x0) / grid_m)), int(round((y1 - y0) / grid_m))
    if not (np.isclose(nx * grid_m, x1 - x0) and np.isclose(ny * grid_m, y1 - y0)):
        raise ValueError(f"domain extent is not a whole number of {grid_m} m cells")
    return Affine(grid_m, 0, x0, 0, -grid_m, y1), nx, ny


def mrms_on_domain(path: Path, dom: Domain, grid_m: float) -> np.ndarray:
    """One MRMS file -> mm on the domain grid (rows south to north). Negative MRMS codes (-3: no coverage) are
    NaN; cells are the area average of the 0.01 deg source cells."""
    lon0, lat0, lon1, lat1 = dom.bbox_4326
    with rasterio.open(path) as s:
        w = (
            from_bounds(lon0 - 0.05, lat0 - 0.05, lon1 + 0.05, lat1 + 0.05, s.transform)
            .round_offsets()
            .round_lengths()
        )
        a = s.read(1, window=w).astype("float32")
        src_t = s.window_transform(w)
    a[a < 0] = np.nan
    t, nx, ny = rain_grid(dom, grid_m)
    out = np.full((ny, nx), np.nan, "float32")
    reproject(
        a,
        out,
        src_transform=src_t,
        src_crs="EPSG:4326",  # MRMS lat/lon grid; its GRIB spheroid shifts it by far less than a cell
        src_nodata=np.nan,
        dst_transform=t,
        dst_crs=dom.crs,
        dst_nodata=np.nan,
        resampling=Resampling.average,
    )
    return out[::-1]


def rain(dom: Domain, ev: dict, raw: Path) -> xr.DataArray:
    """Hourly rain (mm per hour) on the domain grid, dims (time, y, x)."""
    cfg, times = ev["rain"], hours(ev)
    t, nx, ny = rain_grid(dom, cfg["grid_m"])
    frames, missing = [], []
    for ti in times:
        p = fetch_mrms(ti, cfg, raw)
        if p is None:
            missing.append(ti)
            frames.append(np.full((ny, nx), np.nan, "float32"))
        else:
            frames.append(mrms_on_domain(p, dom, cfg["grid_m"]))
    if missing:
        log.warning(
            "MRMS: %d of %d hours missing: %s", len(missing), len(times), [str(m) for m in missing[:5]]
        )
    x = t.c + cfg["grid_m"] * (np.arange(nx) + 0.5)
    y = dom.bounds[1] + cfg["grid_m"] * (np.arange(ny) + 0.5)
    da = xr.DataArray(
        np.stack(frames),
        dims=("time", "y", "x"),
        coords={"time": times.tz_localize(None), "y": y, "x": x},
        name="rain",
        attrs={"units": "mm", "long_name": "rain in the hour ending at time (MRMS 1 h QPE, Pass 2)"},
    )
    return da


# ---- river gauges: USGS NWIS ----
def fetch_nwis(dom: Domain, ev: dict, raw: Path) -> dict:
    """Instantaneous discharge of every gauge in the domain box; the JSON response is cached per event."""
    p = raw / "usgs_nwis" / f"{ev['key']}_{ev['gauges']['parameter']}.json"
    if p.exists():
        return json.loads(p.read_text())
    lon0, lat0, lon1, lat1 = dom.bbox_4326
    params = {
        "format": "json",
        "bBox": f"{lon0:.6f},{lat0:.6f},{lon1:.6f},{lat1:.6f}",
        "parameterCd": ev["gauges"]["parameter"],
        "startDT": pd.Timestamp(ev["start"]).strftime("%Y-%m-%dT%H:%MZ"),
        "endDT": pd.Timestamp(ev["end"]).strftime("%Y-%m-%dT%H:%MZ"),
    }
    r = requests.get(NWIS, params=params, timeout=120)
    r.raise_for_status()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(r.text)
    return r.json()


def gauges(doc: dict) -> xr.Dataset:
    """NWIS JSON -> discharge (m3/s), dims (site, time) on the union of the reported times (15 min)."""
    series, meta = {}, []
    for ts in doc["value"]["timeSeries"]:
        si = ts["sourceInfo"]
        site = si["siteCode"][0]["value"]
        nodata = float(ts["variable"].get("noDataValue", -999999))
        vals = [v for v in ts["values"][0]["value"] if float(v["value"]) != nodata]
        if not vals:
            continue
        t = pd.to_datetime([v["dateTime"] for v in vals], utc=True).tz_localize(None)
        q = np.array([float(v["value"]) for v in vals]) * CFS_TO_M3S
        series[site] = pd.Series(q, index=t).groupby(level=0).mean()
        g = si["geoLocation"]["geogLocation"]
        meta.append((site, si["siteName"], float(g["latitude"]), float(g["longitude"])))
    df = pd.DataFrame(series).sort_index()
    sites = [m[0] for m in meta]
    return xr.Dataset(
        {"discharge": (("time", "site"), df[sites].to_numpy("float32"), {"units": "m3/s"})},
        coords={
            "time": df.index.to_numpy(),
            "site": sites,
            "name": ("site", [m[1] for m in meta]),
            "lat": ("site", [m[2] for m in meta]),
            "lon": ("site", [m[3] for m in meta]),
        },
    ).transpose("site", "time")


# ---- seismic virtual discharge: seis-hydro-2-sed ----
def fetch_seis_hydro(ev: dict, raw: Path) -> dict[str, object]:
    """The event files of seis-hydro-2-sed at the pinned commit (raw.githubusercontent.com), cached."""
    cfg = ev["virtual_discharge"]
    out = {}
    for f in cfg["files"]:
        p = raw / "seis_hydro_2_sed" / cfg["commit"][:12] / Path(f).name
        if not p.exists():
            r = requests.get(f"{RAW_GITHUB}/{cfg['repo']}/{cfg['commit']}/{f}", timeout=120)
            r.raise_for_status()
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(r.content)
        out[Path(f).stem] = json.loads(p.read_text())
    return out


def virtual_discharge(files: dict, min_nse: float, start, end) -> xr.Dataset:
    """Virtual discharge (m3/s) of the stations whose rating reproduces their gauge (NSE of log Q >= min_nse),
    dims (site, time), cut to the event window."""
    fit = {f["station"]: f for f in files["virtual_q_fit"]}
    where = {f"CC.{s['sta']}": s for s in files["cc_stations"]} | {
        f"UW.{s['sta']}": s for s in files["uw_stations"]
    }
    keep = [
        k for k in files["virtual_q"] if fit.get(k, {}).get("nse_logQ", -np.inf) >= min_nse and k in where
    ]
    series = {}
    for k in keep:
        v = files["virtual_q"][k]
        t = pd.to_datetime(v["time"], utc=True).tz_localize(None)
        series[k] = pd.Series(np.array(v["q_seis"], "float64"), index=t)
    df = pd.DataFrame(series).sort_index()
    df = df[
        (df.index >= pd.Timestamp(start).tz_localize(None))
        & (df.index <= pd.Timestamp(end).tz_localize(None))
    ]
    return xr.Dataset(
        {"discharge": (("time", "site"), df[keep].to_numpy("float32"), {"units": "m3/s"})},
        coords={
            "time": df.index.to_numpy(),
            "site": keep,
            "name": ("site", [where[k].get("site", k) for k in keep]),
            "lat": ("site", [float(where[k]["lat"]) for k in keep]),
            "lon": ("site", [float(where[k]["lon"]) for k in keep]),
            "nse_logq": ("site", [float(fit[k]["nse_logQ"]) for k in keep]),
        },
    ).transpose("site", "time")


def in_box(ds: xr.Dataset, dom: Domain) -> xr.Dataset:
    lon0, lat0, lon1, lat1 = dom.bbox_4326
    m = (ds.lon >= lon0) & (ds.lon <= lon1) & (ds.lat >= lat0) & (ds.lat <= lat1)
    return ds.isel(site=np.flatnonzero(m.values))


def peaks(ds: xr.Dataset) -> pd.DataFrame:
    """Peak discharge and its time (the first time it is reached), the number of samples and the last one."""
    q = ds.discharge.values
    rows = []
    for i, s in enumerate(ds.site.values):
        ok = np.isfinite(q[i])
        j = int(np.nanargmax(q[i]))
        rows.append(
            {
                "site": s,
                "name": str(ds.name.values[i]),
                "peak_m3s": round(float(q[i, j]), 1),
                "peak_time_utc": pd.Timestamp(ds.time.values[j]).strftime("%Y-%m-%d %H:%M"),
                "n_samples": int(ok.sum()),
                "last_utc": pd.Timestamp(ds.time.values[np.flatnonzero(ok)[-1]]).strftime("%Y-%m-%d %H:%M"),
            }
        )
    return pd.DataFrame(rows)


ELEV_BANDS = (0, 500, 1000, 1500, 2000, 3000, 5000)  # m, for the rain-elevation table of the summary


def summary(rain: xr.DataArray, gauges: xr.Dataset, windows: list[dict], surface: xr.Dataset | None) -> dict:
    """Event numbers quoted in the report: rain totals and timing, rain by elevation band and on glaciers
    (when the model's surface is given), and the time from the domain-mean rain maximum to each gauge peak."""
    total = rain.sum("time", min_count=1)
    mean_h = rain.mean(("y", "x"))
    k = int(np.nanargmax(total.values))
    iy, ix = np.unravel_index(k, total.shape)
    t_max = pd.Timestamp(rain.time.values[int(np.nanargmax(mean_h.values))])
    out = {
        "hours": int(rain.sizes["time"]),
        "mrms_coverage": round(float(np.isfinite(rain.values).mean()), 3),
        "domain_mean_total_mm": round(float(total.mean()), 1),
        "max_cell_total_mm": round(float(total.values[iy, ix]), 1),
        "max_cell_xy_m": [float(rain.x[ix]), float(rain.y[iy])],
        "max_hourly_mm": round(float(np.nanmax(rain.values)), 1),
        "max_domain_mean_mm_h": round(float(np.nanmax(mean_h.values)), 2),
        "max_domain_mean_time_utc": t_max.strftime("%Y-%m-%d %H:%M"),
        "windows": [],
    }
    for w in windows:
        a = pd.Timestamp(w["start"]).tz_convert(None)
        b = pd.Timestamp(w["end"]).tz_convert(None)
        sel = (rain.time > np.datetime64(a)) & (rain.time <= np.datetime64(b))
        out["windows"].append(
            {
                "label": w["label"],
                "hours": int(sel.sum()),
                "domain_mean_mm": round(float(mean_h[sel].sum()), 1),
            }
        )
    if surface is not None:
        g = rain.x[1] - rain.x[0]
        el = surface["elevation"].coarsen(x=int(g / 100), y=int(g / 100), boundary="trim").mean()
        el = el.interp(x=rain.x, y=rain.y, method="nearest")
        bands = []
        for lo, hi in zip(ELEV_BANDS[:-1], ELEV_BANDS[1:], strict=True):
            m = (el >= lo) & (el < hi) & np.isfinite(total)
            if int(m.sum()):
                bands.append(
                    {
                        "band_m": [lo, hi],
                        "cells": int(m.sum()),
                        "mean_total_mm": round(float(total.where(m).mean()), 1),
                    }
                )
        out["elevation_bands"] = bands
        if "ice_thickness" in surface:
            ice = (
                (surface["ice_thickness"].fillna(0) > 0)
                .coarsen(x=int(g / 100), y=int(g / 100), boundary="trim")
                .mean()
            )
            ice = ice.interp(x=rain.x, y=rain.y, method="nearest")
            m = (ice >= 0.5) & np.isfinite(total)
            out["glacier_cells"] = int(m.sum())
            out["glacier_mean_total_mm"] = round(float(total.where(m).mean()), 1) if int(m.sum()) else None
    lags = []
    for i, s in enumerate(gauges.site.values):
        q = gauges.discharge.values[i]
        tp = pd.Timestamp(gauges.time.values[int(np.nanargmax(q))])
        lags.append({"site": str(s), "hours_after_rain_max": round((tp - t_max) / pd.Timedelta("1h"), 2)})
    out["gauge_peak_lags"] = lags
    return out
