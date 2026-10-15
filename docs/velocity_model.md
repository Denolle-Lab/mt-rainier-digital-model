# The rainier3d velocity model: a user guide

This guide is for anyone who wants to use the velocity model of Mount Rainier: to locate earthquakes, compute
synthetics, build a mesh, or compare with another model. It says what the model contains, how to load it, which
version to use, and what the model can and cannot tell you. How the model is built is in
`docs/model_construction.md` and in the paper (`docs/paper/rainier3d_paper.md`, Sect. 5).

Start with `examples/velocity_model_quickstart.py`. It downloads the model and prints a summary, then samples a
point, plots a profile and a section, reads one critical-zone column, and exports a grid.

For travel times and rays, `examples/pykonal_tutorial.ipynb` runs pykonal in the model for a source and a set of
stations, and compares the times with the analyst picks of the event (`pixi run jupyter lab` in the repository).

## 1. Which model to use

| Product | What it is | Use it for |
|---|---|---|
| `model` | The fused, calibrated model: geology-based Vp, Vs and density below the critical zone, merged with the regional tomography at long wavelengths, calibrated on PNSN travel times | the default; anything that needs the documented, invariant-tested model |
| `model_let` | `model` after the local-earthquake tomography (S37): the same fields with a smooth ln V update, zero in the top 150 m | travel-time work near the network (location, ray tracing); compare against `model` before relying on it |
| `grids` | `model` resampled on one uniform 500 m grid (CF netCDF, EMC netCDF, NonLinLoc P and S grids) | codes that need a regular grid and no Python |

Fit of each to PNSN arrivals, as RMS residual on held-out events after relocation in the model
(`outputs/paper/numbers.json`, run of 14 October 2026):

| Model | P (s) | S (s) | Held-out events |
|---|---|---|---|
| PNSN one-dimensional model | 0.131 | 0.263 | 44 calibration events |
| `model` | 0.093 | 0.188 | 44 calibration events |
| `model` (start of S37) | 0.091 | 0.180 | 1849 events in 10 km squares |
| `model_let` | 0.073 | 0.121 | the same 1849 events |

The two sets of held-out events differ, so compare within a set, not across sets.

## 2. Get it

```bash
pip install "git+https://github.com/Denolle-Lab/mt-rainier-digital-model"   # the rainier3d command and rainier3d.api
rainier3d list                                                            # products, versions, sizes
rainier3d fetch model                                                     # about 200 MB, checked against its SHA-256
```

```python
import rainier3d.api as r3

tree = r3.open_model()                        # downloads once, then reads the cache
let = r3.open_model(product="model_let")      # the model after the tomography
```

- **Where it goes:** `$RAINIER3D_DATA`, by default `~/.cache/rainier3d/<product>/extracted`.
- **Updating:** a new release is listed in the package catalogue (`src/rainier3d/products.json`). After
  `pip install -U "git+https://github.com/Denolle-Lab/mt-rainier-digital-model"`, the next `fetch` replaces the
  cached copy, because its checksum no longer matches the catalogue.
- **Version:** `rainier3d list` prints the release each product comes from. Quote it when you publish results.
- **Working in the repository:** `pixi run model` and the other families rebuild everything from the cached
  inputs (README, Pipeline). The stores are then `data/processed/model.zarr` and `model_let.zarr`.

## 3. Structure

The model is an xarray DataTree stored as Zarr v3 (`consolidated=False`). Each node is a dataset:

| Node | Grid | Content |
|---|---|---|
| `/surface` | 100 m, (y, x) | ground elevation, mapped geology, ice thickness, alteration at the surface, soil and vegetation layers |
| `/cz` | 250 m, (cz_depth, y, x), 52 layers to 150 m | critical-zone columns: Vp, Vs, density, saturation, effective stress, porosity, permeability, van Genuchten parameters |
| `/L1` | 250 m × 50 m, elevation 0 to 4400 m | the subsurface above sea level |
| `/L2` | 500 m × 250 m, elevation −6 to 0 km | the upper crust |
| `/L3` | 1 km × 1 km, elevation −20 to −6 km | the middle crust |
| `/let` (`model_let` only) | 3 km nodes, 9 depths | the tomography perturbation on its own node grid, with ray coverage |

**Coordinates and conventions.**
- **Horizontal:** UTM zone 10N, metres (EPSG:32610), at cell centres. The box is 553–623 km easting and
  5149–5224 km northing (70 × 75 km), about 122.31–121.38° W and 46.48–47.17° N.
- **Vertical:** `z` is elevation in metres, NAVD88 (EPSG:5703), positive up, at cell centres. The levels L1–L3
  are stacked in elevation, not in depth.
- **Depth below the ground:** `depth` (L1–L3) is the depth of the cell centre below the ground surface, which is
  the top of the ice on glaciers; it is negative in air. `cz_depth` (`/cz`) is measured below the ground or,
  under ice, below the glacier bed.
- **Air:** above the ground, Vp, Vs, density and Q are NaN and `unit` is 0. `r3.grid` fills air cells with the
  rock below them and flags them in `air`, so meshes that follow the topography find rock everywhere.
- **Ice:** glacier ice is unit 1, with Vp 3800 m/s, Vs 1919 m/s and density 917 kg/m³.
- **Units:** SI throughout: m/s, kg/m³, Pa, m. Every variable carries `units` and `long_name`; `print(ds)`
  shows them.

## 4. Variables

Levels L1, L2 and L3 (`rainier3d.io.attrs.LEVEL`):

| Variable | Units | Meaning |
|---|---|---|
| `vp`, `vs`, `rho` | m/s, m/s, kg/m³ | the fused model: the values to use |
| `qp`, `qs` | 1 | quality factors from a rule on Vs (`q` block of `configs/perturbations.yaml`) |
| `vp_geology`, `vs_geology` | m/s | the geology model before the fusion (S4) |
| `vp_regional`, `vs_regional` | m/s | the corrected regional model (USGS Cascadia CVM v1.7 to 9.9 km below the ground, CRESCENT Gen0 below) |
| `unit` | 1 | model unit, table below; `flag_values` and `flag_meanings` in its attributes |
| `alteration` | 1 | hydrothermal alteration intensity, 0 fresh to 1 altered (helicopter EM survey, S22) |
| `magma_weight` | 1 | weight of the magma-body anomaly, 1 in its core to 0 outside |
| `porosity`, `log10_permeability`, `weathering_index` | 1, log10(m²), 1 | hydraulic properties; weathering index 1 regolith to 0 fresh rock |
| `depth`, `elevation` | m | depth below the ground of each cell; ground elevation of each column |
| `dlnvp_let`, `dlnvs_let` (`model_let` only) | 1 | the tomography update: `vp = vp_model × exp(dlnvp_let)` |

The critical-zone node `/cz` (`rainier3d.io.attrs.CZ`) holds `vp`, `vs`, `rho`, `saturation`, `sigma_eff` (Pa),
`porosity`, `log10_permeability`, `weathering_index`, `theta_r`, `theta_s`, `alpha` (1/m) and `n` (van Genuchten),
the base depths `z_soil`, `z_cover`, `z_weathered` and `z_fractured`, `ice_thickness`, `water_table` and the layer
thickness `cz_thickness`.

**Units of the model** (`configs/units.yaml`; parameters in `configs/petrophysics.csv`):

| Code | Unit | Kind |
|---|---|---|
| 0 | `air` | – |
| 1 | `ice` | ice |
| 2–5 | `water`, `glacial_drift`, `alluvium_colluvium`, `lahar_deposits` | unconsolidated deposits |
| 6 | `rainier_andesite` | edifice |
| 7 | `young_volcanics` | cap (Quaternary–Pliocene volcanics) |
| 8 | `miocene_intrusive` | plutons (Tatoosh, White River, Carbon River, Nisqually) |
| 9–14 | `miocene_volcanics`, `ohanapecosh`, `eocene_volcanics`, `eocene_sedimentary`, `miocene_sedimentary`, `pre_tertiary` | supracrustal units |
| 20 | `middle_crust` | deep |
| 21 | `magma_mush` | deep: the magma body |

## 5. Recipes

All of these run in `examples/velocity_model_quickstart.py`.

```python
import rainier3d.api as r3

tree = r3.open_model()

# a point: lon, lat and depth BELOW SEA LEVEL in metres; returns the level it used
r3.sample(tree, -121.7603, 46.8523, 5000)        # {'vp': ..., 'vs': ..., 'rho': ..., 'unit': ..., 'level': 'L2'}

# one level as a dataset; nearest cell to a UTM point
l2 = tree["L2"].to_dataset()
col = l2.sel(x=594500, y=5189500, method="nearest")            # a column under the summit
col.vs.where(col.unit > 1)                                     # rock only (no air, no ice)

# one uniform grid over all levels, for plotting or for another code
g = r3.grid(tree, dx=500, dz=250, zmin=-15000)                 # optional bbox=(w, s, e, n) in degrees
g.vs.where(g.air == 0).sel(y=5189500, method="nearest").plot(x="x", y="z")
r3.export(g, "netcdf", "out/rainier3d_500m.nc")               # also "nll", "emc", "specfem", "pylith", "csv"

# the top 150 m: read the critical-zone columns, not the 50 m cells of L1
cz = tree["cz"].to_dataset().sel(x=590662, y=5178067, method="nearest")   # Longmire
cz.vs.sel(cz_depth=slice(0, 30))
```

The command line does the same without Python:
`rainier3d sample --lon -121.76 --lat 46.85 --depth 5000` and `rainier3d export model --format nll ...`
(`docs/products.md` lists every format, with the NonLinLoc and PyLith settings).

**Common mistakes.**
- **Depth axes:** `r3.sample` takes depth below sea level; `depth` and `cz_depth` are below the ground.
- **Top cells:** the top L1 cells of a column are travel-time averages of the critical-zone column, which keeps
  the vertical travel time right at 50 m resolution. For anything that depends on the top 150 m (site
  response, surface waves above a few Hz, Vs30), read `/cz`.
- **Mixing levels:** the levels have different spacings. `r3.grid` resamples all three onto one grid; selecting
  by `z` across levels by hand needs care at their boundaries (0 and −6 km elevation).
- **Using `vp_geology` or `vp_regional`:** these are the inputs of the fusion, kept for comparison. Use `vp`.

## 6. What the model resolves, and its limits

- **Long wavelengths (more than about 6–20 km):** they come from the regional tomography, corrected by one depth
  profile fitted to PNSN travel times. The correction holds beneath Rainier, but the iMUSH tomography shows it
  makes Vs 5–6% too fast at 2–6 km in the south of the box.
- **Shorter wavelengths:** they come from the geological rules: map units extended to depth, the edifice above its
  pre-volcanic surface, and plutons to 10 km below sea level. Contacts and the walls of extruded units are smoothed
  over about 1–2 km below the critical zone, so the model has no sharp interfaces there.
- **Rock physics:** the unit parameters are author choices within published ranges (`m1_placeholder` in
  `configs/petrophysics.csv`), scaled by three global factors: zero-pressure Vp ×1.44, crack-closure pressure ×1.42
  and rock Vs ×0.951. V₀ and Vs are resolved by the travel times; the crack-closure pressure is not.
- **Top 150 m:** the critical zone is petrophysically consistent with the rock below (one water table, one pore
  pressure), but its parameters are not calibrated, because travel times barely constrain the top 50 m. Its
  depth-to-rock priors differ by a factor of 13.9 at the median.
- **Magma body:** prescribed as a sphere 6.5 km in radius centred 11.5 km below sea level under the summit, 15%
  slower in Vs in its core. Its size and anomaly are author choices; the tomography has almost no rays below 12 km.
- **Tomography (`model_let`):** checkerboard tests recover 12 km structure between sea level and 6 km depth
  (correlation 0.63–0.75, about half the amplitude), and almost nothing below 12 km or under the summit below
  5 km. Where ray coverage is low, the update is set by the smoothing. `/let` holds the ray coverage (`dws_p`,
  `dws_s`).
- **Attenuation:** Q follows a rule on Vs. In the 18,544 of 2.24 million cells with Vp/Vs below √(8/3), the rule
  implies a negative bulk quality factor.
- **No per-cell uncertainty:** the model has no uncertainty at each cell. The paper's uncertainty table
  (Sect. 9) says, product by product, what is quantified and what is not.

## 7. Cite, licence and questions

- **Cite:** Denolle, Yao, Hemmett, Köpfli, Han and Kidiwela (2026) (`CITATION.cff`). Also give the release
  (`rainier3d list`) and the sources of the layers you use (`docs/data_policy.md`).
- **Licence:** the products are CC-BY 4.0; the code is BSD-3-Clause.
- **Questions and errors:** open an issue at <https://github.com/Denolle-Lab/mt-rainier-digital-model/issues>.
  Say which product and release, and which cell or coordinates.
