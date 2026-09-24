# rainier3d: a virtual 3D Earth model of Mount Rainier

This is an open, Python-native model of Mount Rainier National Park and the West Rainier Seismic
Zone (WRSZ). It has two parts:

- **Surface layers:** DEM, geology, glaciers. Ecology, soil and hydrology come in M2.
- **A meshed volume:** Vp, Vs, density and Q, from the DEM down to 20 km below sea level.

The volume is built from mapped geology through rock-physics rules. It keeps the long
wavelengths of the regional Cascadia model and is checked against PNSN travel times.

Status: **M1 skeleton**. Every stage runs end to end at coarse resolution. Most rock-physics and
geometry numbers are placeholders, marked `m1_placeholder` in `configs/`.

## Pipeline

| Stage | Script | Product (`data/processed/`, `outputs/`) |
|---|---|---|
| S1 surface | `scripts/01_surface.py` | `surface.zarr`: elevation (3DEP), surface unit (DNR GeMS 1:100k via `configs/crosswalk_geology.json`), ice thickness |
| S3 geology | `scripts/03_geomodel.py` | `geomodel.zarr`: 3D unit and alteration on levels L1/L2/L3 (rules in `configs/units.yaml`) |
| S4 properties | `scripts/04_properties.py` | `properties_geology.zarr`: Vp, Vs, ρ, Q from `configs/petrophysics.csv` and `configs/perturbations.yaml` |
| S5 fusion | `scripts/05_fusion.py` | `model.zarr` (master product) and `fusion_report.csv` |
| S6 PNSN check | `scripts/06_validate_pnsn.py` | `pnsn_report.txt`, `pnsn_residuals.csv`, `pnsn_stations.csv` |
| S7 export/viz | `scripts/07_export_viz.py` | `vtk/*.vti`, `*.vts`, sections, `rainier3d_view.png`/`.html` |

| S8 sensor atlas | `scripts/08_atlas.py` | `web/atlas/data/`: sites, DAS fiber, PNSN events, overlay images; `data/processed/overlays/*.tif` |

S2 (literature extraction of petrophysics) is M3. For now `configs/petrophysics.csv` is filled
by hand.

```
pixi install
pixi run all      # s1, s3-s7
pixi run test
pixi run viz      # interactive PyVista window
```

## Sensor atlas and KMZ layers

`pixi run s8` then `pixi run atlas`, and open http://127.0.0.1:8765. The atlas is a MapLibre GL
terrain viewer showing every sensor in the domain, grouped into families:

- seismic, strong motion, nodes, infrasound, strain/tilt and MT/EM (all from FDSN);
- GNSS;
- the Paradise–Nisqually DAS fiber;
- meteorology and streamflow;
- the 2025 Rainier node deployment.

Sites are drawn as donut markers with one segment per sensor, and hover cards show the sensor
list, status and dates. The fiber hover shows the channel, distances, elevation and lithology.

**To add a KMZ layer:**

1. Add an entry to `configs/overlays.yaml` with `kmz: <path>`, `label` and `opacity`. Optional:
   `crop` (fractions), `jpeg`, and `white_transparent`.
2. Run `pixi run s8`.

Both single GroundOverlay files and Google Earth super-overlays (tiled quadtrees) are read by
`rainier3d.io.kmz`. Each overlay is written twice:

- as a GeoTIFF in `data/processed/overlays/`, which `scripts/07_export_viz.py --drape <name>`
  drapes on the 3D model;
- as a web image in the atlas.

To add a sensor family, add a rule to `configs/sensor_families.yaml`.

## Grid

The domain is EPSG:32610 x 553–623 km, y 5149–5224 km (70 × 75 km). Elevation is NAVD88,
positive up. Levels, from `configs/domain.yaml`, profile `m1`:

| Level | z range (m) | dx (m) | dz (m) |
|---|---|---|---|
| L1 | 4400 to 0 | 250 | 50 |
| L2 | 0 to −6000 | 500 | 250 |
| L3 | −6000 to −20000 | 1000 | 1000 |

## Method in one paragraph

Map units are crosswalked to 16 model units and extended to depth by column rules:

- ice thickness, then an unconsolidated deposit layer;
- Rainier andesite above an interpolated pre-volcanic surface;
- basement units extruded to −4 km, and plutons to −10 km;
- middle crust below;
- a placeholder magma ellipsoid and a placeholder conduit-centred alteration field.

Vp follows a crack-closure law in effective overburden pressure. Vs and density come from
unit values or from Brocher (2005). Fusion works in ln V: Vs and Vp/Vs are fused as
LP(regional) + HP(geology), with a horizontal Gaussian whose cutoff wavelength grows with depth.
Alternating projections then keep each cell between its two inputs and restore the regional
low-pass. The top 300 m is pure geology, tapering into the fused model by 1 km. The regional
model is USGS Cascadia CVM v1.7 to 9.9 km below ground, and CRESCENT Gen0 below.

## Sources

`configs/sources.yaml` is the registry; each layer's `gaia:source` attribute points into it.
`docs/data_inventory.md` lists the ~90 datasets and papers found in the 2026-09-23 survey.

## Local inputs outside this repo

- `~/GitHub/gwl-space-time-smooth/data/raw/CVM17_L01.nc`, `CVM17_L2.nc`: CVM v1.7. ScienceBase
  blocks scripted downloads with a captcha. L3 is not downloaded.
- `~/GitHub/cascadia_obs_ensemble/data/tomography/CRESCENT_Gen0.nc`
- `~/GitHub/cascadia_obs_ensemble/data/vel_pnsn_wa.csv`: PNSN 1D model; which PNSN model this
  is remains unconfirmed.

License: BSD-3-Clause.
