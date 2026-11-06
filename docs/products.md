# Derived products: download and use

The products of rainier3d are published under CC-BY 4.0 as assets of the GitHub release
[`products-v1.1.0`](https://github.com/Denolle-Lab/mt-rainier-digital-model/releases/tag/products-v1.1.0), a test release.
- **Checksums:** `SHA256SUMS` lists the SHA-256 of every asset, and the package catalogue
  `src/rainier3d/products.json` records them too.
- **GNSS:** the GNSS product is refreshed every week in the release
  [`gnss-latest`](https://github.com/Denolle-Lab/mt-rainier-digital-model/releases/tag/gnss-latest).
  `products-v1.1.0` holds a fixed snapshot of it, cut on 2026-09-01.
- **Licences and attribution:** `docs/data_policy.md`. Inputs whose licence forbids redistributing derivatives
  are left out, so the model has no `water_table_depth`.
- **Only what rainier3d computes** (from `products-v1.1.0`): third-party fields that are only
  resampled onto the grid are left out (`configs/products.yaml`) and rebuilt by `pixi run s2`.
- **Remaking a product:** each release carries `REBUILD.md` (the commit, the data freeze, the stages to run and
  the inputs to obtain by hand) and `inputs.csv` (every cached input file of each product, with its SHA-256).

## Install the client

```bash
pip install "git+https://github.com/Denolle-Lab/mt-rainier-digital-model"   # the rainier3d command and rainier3d.api
rainier3d list                                                            # products, versions, sizes, licences
```

`rainier3d fetch <product>` downloads a product once. It checks the SHA-256, unpacks it into `$RAINIER3D_DATA`
(default `~/.cache/rainier3d/<product>/extracted`) and prints that folder. In Python, `rainier3d.api.fetch`
returns the same folder.

## The products

| Product | Size | Content | Made by |
|---|---|---|---|
| `model` | 193 MB | Fused Vp, Vs, density, Qp, Qs, units and alteration on levels L1–L3, the critical-zone columns and the surface layers (xarray DataTree, Zarr v3) | S1–S5, S13, S22 |
| `model_let` | 209 MB | `model` after the S37 local-earthquake tomography, with the update and its node grid `/let` | S37 |
| `grids` | 55 MB | The model on one uniform grid: CF netCDF (500 m), EMC-style netCDF, NonLinLoc P and S grids | S9 |
| `strain_3d` | 72 MB | GNSS strain rate carried down and edifice-load strain in the volume, with orientations | S25 |
| `edifice_load` | 115 MB | Stress from the weight of the edifice on levels L1–L3 | S18 |
| `alteration` | 1 MB | Hydrothermal alteration from the 1996 helicopter EM survey (3D, top 200 m) | S22 |
| `mass_movements` | 2 MB | Landslides, lahars, debris flows, seismic mass movements, faults, lahar zones (GeoPackage, CSV) | S24 |
| `gnss` | 4 MB | GNSS velocities with QC flags, strain-rate grid, daily regional strain, download manifest | S17, S18 |

## Provenance and uncertainty

For each product: what it is built from (keys of `configs/sources.yaml`, which give the reference, version and
licence of each input), how, what uncertainty the files carry and what is not quantified. The paper's uncertainty
table (Sect. 9) gives the sizes; `REBUILD.md` and `inputs.csv` in each release give the commit, the stages and the
checksum of every input file. Most gridded fields have **no per-cell uncertainty**: their parameters are author
choices within published ranges (`m1_placeholder`) or come from rule-based geometry.

**`model`** (S1–S5, S13, S22; paper Sects. 4–5, `docs/model_construction.md`, `docs/joint_calibration.md`)
- **Built from:**
  - surface and geometry: `usgs_3dep`, `dnr_gems_100k` (through `configs/units.yaml`), `iceboost_v2`, `rgi60`,
    `glathida`, `solus100`, `polaris`, `sentinel2_l2a`;
  - rock physics: the parameters of `configs/petrophysics.csv`, most of them `m1_placeholder`;
  - alteration: `rystrom_2000`, `finn_2001`;
  - long wavelengths: `cvm17` and `crescent_gen0` (Vp from `brocher_2005`), fused in the wavenumber domain;
  - calibration: PNSN picks of `comcat_uw`, relocated in 3D in every trial model.
- **Uncertainty carried:**
  - the travel-time fit of the 44 held-out events, RMS 0.093 s (P) and 0.188 s (S);
  - the posterior s.d. of the three calibration multipliers (`configs/velocity_calibration.yaml`);
  - the CRESCENT Vs uncertainty `vs_unc_regional`: not in the release, and S5 rebuilds it.
- **Not quantified:**
  - the uncertainty of each cell;
  - the unit parameters, geometry rules and alteration factors;
  - the size and anomaly of the magma body;
  - the critical-zone parameters, which are not calibrated;
  - the uncertainty of the soil and vegetation source products, which is not propagated.
- `docs/velocity_model.md` §6 describes what the model resolves.

**`model_let`** (S37; paper Supplement S1)
- **Built from:**
  - `model`;
  - 99,716 PNSN analyst picks (`comcat_uw`) of 3770 earthquakes;
  - travel times on a 250 m eikonal grid (`white_2020`), inverted with LSQR (`paige_saunders_1982`).
- **Uncertainty carried:**
  - the ray coverage of each node, `dws_p` and `dws_s` in `/let`. Treat nodes below 5 km of derivative weight sum
    as unresolved;
  - held-out RMS 0.072 s (P) and 0.121 s (S), on events withheld by 10 km squares.
- **Not quantified:**
  - no posterior uncertainty at each node;
  - checkerboards recover 12 km structure at 0–6 km depth with correlations of 0.66–0.74 and about half the
    amplitude. They are linear tests, so read them as an upper bound;
  - below 12 km, and beneath the summit below 5 km, the update is set by the smoothing.

**`grids`** (S9)
- **Built from:** `model`, resampled linearly onto 500 m cells; air cells take the rock value below them.
- **Uncertainty:** that of `model`.
- **Not quantified:** the 500 m cells average the 250 m × 50 m structure of L1, near the surface and in the edifice.

**`strain_3d`** (S17, S18; paper Sect. 6)
- **Built from:**
  - the horizontal `gnss` strain-rate tensor, carried down unchanged with depth, with the vertical component
    from plane stress;
  - the edifice-load strain of `edifice_load`, with the stiffness of `model`.
- **Uncertainty carried:** none.
- **Not quantified:**
  - how strain rate varies with depth (an assumption);
  - the heterogeneity of the elastic structure (no Green's functions of the model);
  - any rheology beyond linear elasticity.

**`edifice_load`** (S18; `johnson_1985`)
- **Built from:** Boussinesq point loads of the edifice above the pre-volcanic surface of `model`, on a homogeneous
  elastic half-space.
- **Uncertainty carried:** none.
- **Not quantified:** the density (2500 kg m⁻³) and Poisson's ratio (0.25), both `m1_placeholder`; the flat
  reference plane at 1789 m.

**`alteration`** (S22; `rystrom_2000`, `finn_2001`; `docs/alteration.md`)
- **Built from:** the resistivity of the 1996 helicopter EM survey, with thresholds stored in the file's
  `thresholds` attribute.
- **Uncertainty carried:** none. The `depth_of_investigation_*` fields show how deep each frequency sees.
- **Not quantified:** the intensity thresholds (`m1_placeholder`); depth beyond about 150 m.

**`mass_movements`** (S24; `docs/mass_movements.md`)
- **Built from:** `wgs_landslide_inventory`, `usgs_landslide_inventory_v3`, `allstadt_2017_esec`, `esec_v3`, the
  lahar and debris-flow literature (each event names its `source`), and `usgs_3dep` to place the crowns.
  Volumes are the published ones.
- **Uncertainty carried:** `confidence` on every event: the class of the source inventory, or the location
  uncertainty of a seismically located event.
- **Not quantified:** completeness by class and date; volume uncertainties, which the sources do not give.

**`gnss`** (S17, S18; `panga_gnss`, `unr_ngl_gnss`, `blewitt_2016_midas`, `shen_2015_strain`;
`docs/gnss_strain.md`)
- **Built from:** PANGA and UNR daily positions, frozen at the data cut (`fetch.json`, `manifest.csv`).
- **Uncertainty carried:**
  - the MIDAS velocity uncertainties `se`, `sn` and `su` (m/yr, floored at 0.2 mm/yr), with a QC `flag` on each
    site;
  - `dilatation_sigma` in `strain_grid.nc` and `strain_wrsz.csv`.
- **Not quantified:** the uncertainty of the shear rate and its azimuth; strain on the edifice, which the network
  does not resolve.

### `model`: the fused velocity model

What the model contains, which version to use and what it resolves: `docs/velocity_model.md`. The tomography
model `model_let` has the same layout (`r3.open_model(product="model_let")`).

```bash
rainier3d sample --lon -121.76 --lat 46.85 --depth 5000                     # values at one point
rainier3d export model --format netcdf --dx 250 --dz 250 --zmin -10000 --out out/rainier3d_250m.nc
rainier3d export model --format specfem --bbox -122.0 46.7 -121.6 47.0 --out out/tomography_model.xyz
rainier3d export model --format nll --dx 500 --dz 500 --out out/nll/rainier3d   # NonLinLoc P and S grids
rainier3d export model --format emc --out out/rainier3d_emc.nc
rainier3d export surface --layers elevation soil_thickness ice_thickness --out out/surface/   # GeoTIFFs
rainier3d export model --format pylith --dx 1000 --dz 500 --out out/pylith/rainier3d_elastic.spatialdb
```

**For PyLith.** `--format pylith` writes two files:
- a spatialdata `SimpleGridDB` of the elastic properties PyLith's isotropic linear-elastic material reads:
  `density` (kg/m³), `vs` and `vp` (m/s), in UTM 10N metres with z the elevation (`crs-string = EPSG:32610`);
- a `.cfg` snippet that points a material's `db_auxiliary_field` at the database.

At 1 km × 500 m the database has 257,250 nodes (13 MB). Air cells carry the rock values below them, so a mesh
that follows the topography finds rock everywhere. Two limits:
- **Model box only.** The database covers the model box. A PyLith domain larger than the box needs a regional
  database outside it, for example CVM v1.7 or CRESCENT combined in a `CompositeDB`.
- **Header format.** Check the header against the spatialdata version in use; the format follows the spatialdata
  `SimpleGridDB` documentation.

```python
import rainier3d.api as r3

tree = r3.open_model()                                   # downloads once; xarray DataTree (surface, L1, L2, L3)
vs = tree["L2"].to_dataset().vs.interp(x=594500, y=5189500, z=-2000)   # m/s at 2 km below sea level (UTM 10N)
g = r3.grid(tree, bbox=(-122.0, 46.7, -121.6, 47.0), dx=250, dz=250, zmin=-10000)
r3.export(g, "netcdf", "out/rainier3d_250m.nc")         # also "nll", "emc", "specfem", "csv"
print(r3.sample(tree, -121.76, 46.85, 5000))            # {'vp': ..., 'vs': ..., 'rho': ..., 'level': 'L2'}
```

### `grids`: ready-made uniform grids

```bash
rainier3d fetch grids     # grids/rainier3d_fused_500m.nc, grids/rainier3d_emc.nc, grids/nll/rainier3d.{P,S}.mod.{hdr,buf}
```

```python
import xarray as xr
import rainier3d.api as r3

d = r3.fetch("grids")
g = xr.open_dataset(d / "grids" / "rainier3d_fused_500m.nc")   # vp, vs, rho, qp, qs, alteration, air, surface_elevation
vp = g.vp.where(g.air == 0)                                    # rock only; air cells carry the rock value below
```

In NonLinLoc, point `GTFILES` at `grids/nll/rainier3d`, and give stations and search grids in the same UTM 10N
kilometre frame (`TRANS NONE`), with depth positive down. Paper Sect. 9 gives the full recipe.

### `strain_3d`: strain in the volume

```bash
rainier3d fetch strain_3d
```

```python
import xarray as xr
import rainier3d.api as r3

s = xr.open_zarr(r3.fetch("strain_3d") / "strain_3d.zarr", consolidated=False)
print(s.attrs["wrsz_strike_deg"])                          # WRSZ strike fitted to its epicentres
lev = s.sel(z=-5000, method="nearest")                     # 5 km below sea level
shear = lev.wrsz_shear_rate * 1e9                          # right-lateral shear rate on WRSZ-parallel planes, nanostrain/yr
shmax = lev.load_shmax_az                                  # SHmax of the edifice load, degrees east of north
vol = s.load_volumetric.sel(x=594500, y=5189500, method="nearest") * 1e6   # load volumetric strain under the summit, microstrain
```

The tables for comparison with shear-wave splitting are in the GNSS archive:
- `strain_orientation.csv`: shortening azimuths and magnitudes at seven elevations;
- `strain_3d_summary.json`.

### `edifice_load`: stress from the weight of the edifice

```python
import xarray as xr
import rainier3d.api as r3

t = xr.open_datatree(r3.fetch("edifice_load") / "edifice_load.zarr", engine="zarr", consolidated=False)
sz = t["L2"].to_dataset().szz.sel(x=594500, y=5189500, z=-5000, method="nearest") / 1e6   # MPa, tension positive
```

### `alteration`: hydrothermal alteration from the EM survey

```python
import xarray as xr
import rainier3d.api as r3

a = xr.open_dataset(r3.fetch("alteration") / "alteration_finn2001" / "rainier3d_alteration_finn2001.nc")
print(a)   # 3D intensity (0-1) in the top 200 m below the bedrock surface, resistivity per frequency, magnetisation
```

### `mass_movements`: the mass-movement catalogue

```python
import geopandas as gpd
import rainier3d.api as r3

d = r3.fetch("mass_movements") / "mass_movements"
events = gpd.read_file(d / "events.gpkg")      # one row per event: cls, name, date or age, type, volume, source
flows = gpd.read_file(d / "flows.gpkg")        # mapped lahar and debris-flow deposits
print(events.groupby("cls").size())
```

### `gnss`: velocities and strain (refreshed weekly)

```bash
rainier3d fetch gnss      # the latest weekly refresh; re-downloads only when the published checksum changes
```

```python
import pandas as pd
import rainier3d.api as r3

d = r3.fetch("gnss") / "gnss"
vel = pd.read_csv(d / "velocities.csv")                 # MIDAS velocities (m/yr) with QC flags
wrsz = pd.read_csv(d / "strain_wrsz.csv")               # daily areal strain of the WRSZ stations
# the frozen snapshot used in the paper:
r3.fetch("gnss", url=r3.products()["gnss"]["snapshot_url"], sha256=r3.products()["gnss"]["snapshot_sha256"])
```

## Cite

Cite the products as Denolle, Yao, Hemmett, Köpfli, Han and Kidiwela (2026) (`CITATION.cff`), together with
the sources of the layers you use (`docs/data_policy.md`, Appendix A of the paper). The planned Zenodo DOIs are
described in `docs/doi.md`.
