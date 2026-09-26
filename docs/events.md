# Events: hourly forcing and river response (S29)

S29 stores one storm on the model domain as observed forcing and river response. It is the scaffold of the
time-dependent part of the model: nothing in the model responds to the rain yet. The paper describes the
December 2025 event in Sect. "Toward a time-dependent model".

```bash
pixi run s29                                   # configs/events.yaml, event dec2025_ar
pixi run s29 -- --model ~/.cache/rainier3d/model/extracted/model.zarr   # elevation and glacier numbers from
                                               # the published model when data/processed/model.zarr is absent
```

## Inputs and caches

| Data | Service | Cache (`data/raw/`) | Registry key |
|---|---|---|---|
| MRMS MultiSensor QPE 1 h Pass 2, GRIB2 | `https://noaa-mrms-pds.s3.amazonaws.com/CONUS/<product>/<YYYYMMDD>/` (no login) | `mrms/<product>/<YYYYMMDD>/` (about 0.65 MB per hour) | `mrms_qpe` |
| USGS instantaneous discharge (00060) | `https://waterservices.usgs.gov/nwis/iv/?bBox=...` (redirects to `nwis.waterservices.usgs.gov`) | `usgs_nwis/<event>_00060.json` | `usgs_nwis_iv` |
| Virtual discharge, rating fits, stations, storm windows | `raw.githubusercontent.com/gaia-hazlab/seis-hydro-2-sed/<commit>/config/` | `seis_hydro_2_sed/<commit>/` | `seis_hydro_2_sed` |

GRIB2 needs GDAL's GRIB driver (`libgdal-grib` in `pixi.toml`). MRMS values below zero (−3: no coverage) are
no data. Each file holds the accumulation of the hour ending at its time stamp.

## Outputs

| File | Content |
|---|---|
| `data/processed/events/<key>.zarr` | DataTree: `/rain` (time, y, x) mm per hour on the domain grid at `grid_m`; `/gauges`, `/virtual` (site, time) m³/s at native sampling |
| `outputs/events/<key>/peaks.csv` | peak, peak time (first time reached), number of samples and last sample per gauge |
| `outputs/events/<key>/rain.csv` | domain-mean precipitation per hour |
| `outputs/events/<key>/summary.json` | totals, storm windows, precipitation by elevation band and on glacier cells, peak delays |
| `docs/paper/figures/fig21_flood_event.png` | the paper figure |
| `<atlas>/events/<key>/event.json`, `rain.u8.bin`, `<atlas>/events/index.json` | the viewer's Storms panel: uint8 frames on the overview box (0.25 mm steps, 255 = no data) |

## Adding an event

Add a block to `configs/events.yaml` with its window, the same `rain`, `gauges` and `virtual_discharge` entries
(or drop `virtual_discharge` where no rating exists), and run `pixi run s29 -- --event <key>`. The viewer
lists every event in `<atlas>/events/index.json` and opens the last one.

## Virtual sensors

The seismometers read as river gauges are virtual sensors: instruments repurposed to estimate what they were not
designed to measure. S29 stops if one of them has no entry in `configs/virtual_sensors.yaml`; the entry
(designed for, estimates, method, skill, source, used by) travels to the viewer (`model/sensors.json`
"virtual", and each virtual site of `event.json`), which labels the station on the map, in its tooltip, on its
card and in the Sensors legend. `rainier3d.export.atlas.tag_virtual_sensors(atlas)` updates an existing bundle.

## Rain drops in the viewer

Drops appear with a probability that follows the MRMS rate under them (all drops at 8 mm/h), and their width and
length grow with the rate up to 12 mm/h. Drop size is not observed: the rendering encodes intensity only. Rain
impacts are recorded by seismometers and geophones, so a drop-size estimate from seismic records would be
another virtual sensor and could drive the drop size directly (`uThick` in `RainEvent.js`).

## Forecasts (not fetched yet)

`forecasts: []` in `configs/events.yaml` reserves the place for AI and physics forecasts, stored with the same
(time, y, x) layout so they can be scored against MRMS by lead time.

| Model | Archive | Precipitation | Registry key |
|---|---|---|---|
| GraphCast (GFS or IFS initialised) | `s3://noaa-oar-mlwp-data/GRAP_v100_{GFS,IFS}/<YYYY>/<MMDD>/`, NetCDF, 0.25°, 6 h steps to 240 h | `apcp`, 6 h accumulation (m) | `lam_2023_graphcast`, `radford_2025_mlwp` |
| Pangu, FourCastNet v2, Aurora | same archive | none in the archive's variable list | `radford_2025_mlwp` |
| ECMWF AIFS single | `s3://ecmwf-forecasts/<YYYYMMDD>/<HH>z/aifs-single/0p25/oper/`, GRIB2 | `tp`, `cp`, `sf` | `lang_2024_aifs` |
| FuXi | GAIA pipeline (`gwl-space-time-smooth`, `deploy/tillicum-fuxi.yaml`), not run | daily `precip_mm` | `chen_2023_fuxi` |

At 0.25° the domain holds 4 × 6 cells, against a threefold precipitation gradient between the lowlands and
the summit in December 2025, so a comparison at the scale of the volcano needs downscaling.
