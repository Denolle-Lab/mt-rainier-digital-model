# Derived products: download and use

The products of rainier3d are published under CC-BY 4.0 as assets of the GitHub release
[`products-v1.0.0`](https://github.com/Denolle-Lab/mt-rainier-digital-model/releases/tag/products-v1.0.0).
- **Checksums:** `SHA256SUMS` lists the SHA-256 of every asset, and the package catalogue
  `src/rainier3d/products.json` records them too.
- **GNSS:** the GNSS product is refreshed every week in the release
  [`gnss-latest`](https://github.com/Denolle-Lab/mt-rainier-digital-model/releases/tag/gnss-latest).
  `products-v1.0.0` holds a fixed snapshot of it, cut on 2026-09-01.
- **Licences and attribution:** `docs/data_policy.md`. Inputs whose licence forbids redistributing derivatives
  are left out, so the model has no `water_table_depth`.

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
| `model` | 110 MB | Fused Vp, Vs, density, Qp, Qs, units and alteration on levels L1–L3, plus the surface layers (xarray DataTree, Zarr v3) | S1–S5, S13, S22 |
| `grids` | 55 MB | The model on one uniform grid: CF netCDF (500 m), EMC-style netCDF, NonLinLoc P and S grids | S9 |
| `strain_3d` | 72 MB | GNSS strain rate carried down and edifice-load strain in the volume, with orientations | S25 |
| `edifice_load` | 115 MB | Stress from the weight of the edifice on levels L1–L3 | S18 |
| `alteration` | 1 MB | Hydrothermal alteration from the 1996 helicopter EM survey (3D, top 200 m) | S22 |
| `mass_movements` | 2 MB | Landslides, lahars, debris flows, seismic mass movements, faults, lahar zones (GeoPackage, CSV) | S24 |
| `gnss` | 4 MB | GNSS velocities with QC flags, strain-rate grid, daily regional strain, download manifest | S17, S18 |

### `model`: the fused velocity model

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
