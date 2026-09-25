# GNSS surface strain and the edifice load (S17, S18)

**Result, as of 24 September 2026 (data frozen at `as_of` in `configs/gnss.yaml`):**
- **WRSZ.** The GNSS network resolves regional strain, and neither the 2009 nor the July 2025 summit swarm shows a strain transient above about 10 nanostrain.
- **Edifice.** The station network is too small and too snow-affected to resolve transients below a few hundred nanostrain. Its high sites also move inconsistently with PANGA's own velocities.
- **Edifice load.** Its stress is computed on the model grid, for comparison with the hydrothermal system and the magma body.

## Data (S17, `pixi run s17`)

- **Primary: PANGA.** Daily GIPSY positions (North-America-fixed) and the NA20 velocity field, from Central Washington University. There are 188 sites in the network box (124.0–119.8° W, 45.6–48.2° N); the series end on 18 July 2026.
- **Backup: UNR.** Nevada Geodetic Laboratory IGS20 North-America-fixed series for the 54 sites PANGA does not have. Another 20 sites both archives share are used to align the two frames.
- **Caching.** Every file is cached in `data/raw/gnss/`, and `manifest.csv` records its URL, retrieval time, size and SHA-256. Reruns read the cache; `--refresh` downloads again.
- **Totals.** 1,050,643 site-days in 256 series.

## Weekly refresh

The numbers on this page are from the frozen run (`as_of` 2026-09-01 in `configs/gnss.yaml`). On top of it,
`.github/workflows/gnss-weekly.yml` reruns the pipeline every Monday at 09:00 UTC:
- `gnss-fetch --refresh --as-of today`: every archive file is downloaded again.
- `gnss-strain --no-load`: velocities, QC, the strain grid and the regional series. The edifice load is skipped:
  it needs the local model and does not depend on the GNSS data.
- `gnss-publish --rolling`: the assets of the release `gnss-latest` are replaced.

The job runs in the slim pixi environment `gnss`.

The release holds three assets:

| Asset | Contents |
|---|---|
| `rainier3d_gnss.zip` | the latest outputs, plus `manifest.csv` (URL, time and SHA-256 of every downloaded file) and `fetch.json` (the `as_of` date and the last day with data) |
| `rainier3d_gnss.zip.sha256` | its checksum |
| `rainier3d_gnss_<as_of>.zip` | a dated copy of each refresh |

`rainier3d fetch gnss` downloads the latest refresh, and downloads again only when the published checksum changes. To pin a
dated copy, pass its URL: `rainier3d.api.fetch("gnss", url=".../gnss-latest/rainier3d_gnss_2026-09-28.zip")`.

On pull requests that touch the pipeline, the job runs the same steps without uploading.

Test run, 25 September 2026 (local, `gnss` environment, empty cache):
- S17 fetched 1,050,988 site-days in 256 series in 1 min 41 s; the last day with data was 2026-09-12.
- S18 took 44 s.

| Region | Dilatation, frozen run (nanostrain/yr) | Dilatation, test run (nanostrain/yr) |
|---|---|---|
| WRSZ | −16.6 ± 3.5 | −16.8 ± 3.5 |
| Edifice (QC-passed) | −27.9 ± 12.4 | −29.3 ± 12.4 |

The same 22 sites were flagged in both runs.

## Velocities and quality control (S18, `pixi run s18`)

- **Velocities.** Station velocities come from MIDAS (Blewitt et al., 2016). Steps come from the PANGA fit headers and the UNR steps database.
- **Frame alignment.** A translation + rotation fit of UNR onto PANGA over the 20 shared sites leaves a residual RMS of 0.10 mm/yr.
- **Quality control.** 22 of 203 sites are flagged: their MIDAS velocity differs by more than 1 mm/yr from PANGA's published velocity, or by more than 2.5 mm/yr from the median of neighbours within 40 km. They include the high edifice sites MUIR, CSHR, SNRS, PNHG and PNHR. PNHG moves at 44 mm/yr east, which is not tectonic. Flagged sites stay in `velocities.csv` with their flag and are left out of the strain fits.

## Secular strain rate

Uniform-strain fits to the MIDAS velocities of the sites around each region (region definitions in `configs/gnss.yaml`):

| Region | Sites | Dilatation (nanostrain/yr) | Maximum shear (nanostrain/yr) | Azimuth of e1 |
|---|---|---|---|---|
| WRSZ (polygon + 25 km) | 17 | −16.6 ± 3.5 | 11.1 | 136° |
| Edifice (within 25 km of the summit, QC-passed) | 6 | −27.9 ± 12.4 | 4.3 | 171° |
| Edifice, all sites including the flagged ones | 11 | +120.5 ± 11.8 | 61.2 | 103° |

The grid (`data/processed/gnss/strain_grid.nc`, 5 km, adaptive smoothing) gives −14.6 nanostrain/yr of dilatation at the summit cell, with a smoothing scale of 30 km because the flagged summit sites are excluded. The grid also carries the annual areal-strain amplitude and its peak day, the seasonal (hydrological loading) signal.

## Daily strain and the swarms

![Transient areal strain](gnss/strain_series.png)

- **Method.** The daily uniform strain of each region's stations is fitted to trajectory residuals (trend, annual and semiannual terms, and steps removed per site), so stations joining or leaving do not shift it. Blue lines are 30-day medians; red lines mark the swarms.

| Region | Daily scatter (MAD) | 60-day change across 13 Feb 2009 | 60-day change across 8 Jul 2025 |
|---|---|---|---|
| WRSZ | 20 nanostrain | +6 nanostrain | +7 nanostrain |
| Edifice | 106 nanostrain | no QC-passed coverage | −166 nanostrain, within the 411-nanostrain scatter of the 30-day medians |

- **The edifice scatter.** Winter excursions of up to 1,500 nanostrain since 2017 come from the close-in high sites. With stations a few kilometres apart, a few millimetres of snow-related antenna error become about 1,000 nanostrain of apparent strain. Resolving edifice or magma-body strain needs more sensitive or denser instruments: the Longmire quartz tiltmeters (UW.LON9), borehole strain, or InSAR.

## Stress from the edifice load

- **Method.** Boussinesq point loads on an elastic half-space (`rainier3d.geodesy.load`; Johnson, 1985). The load is the edifice above the pre-volcanic surface of the geology model: 1,131 cells of 500 m, a weight of 2.34 × 10¹⁵ N, equivalent to 95 km³ of rock at 2,500 kg/m³, on a reference plane at 1,789 m.
- **Checks.** The solution passes two tests: the vertical force on a buried plane balances the load within 1%, and the stress field is in equilibrium off the axis.
- **Output.** `data/processed/edifice_load.zarr` holds the six stress components, the mean stress, the maximum shear and the principal stresses on the model levels L1–L3.
- **Under the summit:**

| Elevation (m) | Vertical stress (MPa) | Mean stress (MPa) | Maximum shear (MPa) |
|---|---|---|---|
| 0 | −38.5 | −18.7 | 15.2 |
| −2,000 | −24.0 | −9.4 | 11.2 |
| −5,000 | −13.0 | −4.4 | 6.6 |
| −11,500 (placeholder magma body centre) | −4.9 | −1.5 | 2.6 |

- **Limitations.** Homogeneous half-space; flat reference plane; ν = 0.25 and ρ = 2,500 kg/m³ are placeholders; points within 250 m of the plane are left out.
- **Scale comparison.** The secular geodetic strain rates correspond to stress rates of order 1 kPa/yr (µ ≈ 30 GPa × 3 × 10⁻⁸/yr), against a static load stress of 1–40 MPa.

## Strain in the model volume (S25, `pixi run s25`)

S25 puts two strain fields on the grid of the 3D viewer volume: 500 m × 250 m, from the surface to 20 km below
sea level, rock cells only. The results go to:
- `data/processed/strain_3d.zarr` (the product `strain_3d`);
- `outputs/gnss/strain_orientation.csv`;
- `outputs/gnss/strain_3d_summary.json`;
- the paper figures 16–18.

The numbers below come from that summary.

**Tectonic strain rate.** GNSS measures the horizontal strain rate at the surface only. We carry the S18 tensor
down unchanged through the elastic upper crust and take the vertical strain from plane stress,
e_zz = −ν/(1 − ν)(e_xx + e_yy) with ν = 0.25. Both are assumptions. The field is resolved on vertical planes
parallel to the West Rainier Seismic Zone. The zone's strike, N174.4°E (elongation 3.1), is the long axis of its
1294 epicentres in the ComCat catalogue.

| WRSZ (inside its polygon, 5 km below sea level) | Value |
|---|---|
| Axis of maximum shortening | N48°E |
| Maximum shear strain rate | 10.4 nanostrain/yr |
| Right-lateral shear rate on WRSZ-parallel planes | 10.0 nanostrain/yr |
| Normal strain rate across the zone | −12.9 nanostrain/yr (contraction) |

With shortening at N48°E, the planes of maximum shear strike N3.5°E and N93.5°E. The WRSZ strike lies 9° from
the first, so the GNSS field loads the zone almost optimally for right-lateral slip: 96% of the maximum shear.

**Edifice-load strain.**
- **Method.** The Boussinesq stress of S18 is turned into strain with the local stiffness of the velocity
  model (μ = ρVs², λ = ρVp² − 2μ).
- **Cone interior.** Inside the cone, above the half-space (higher than 1539 m, the reference plane minus
  250 m), the stress is taken as the laterally confined overburden: σzz = −ρgd and σh = ν/(1 − ν) σzz. That
  gives volumetric strain but no SHmax, because horizontal stress is isotropic there.
- **Output.** SHmax is the most compressive horizontal stress; the product also stores the full strain tensor.

| Elevation beneath the summit (m) | 2500 | 1500 | 1000 | 500 | 0 | −2000 | −5000 | −11,500 |
|---|---|---|---|---|---|---|---|---|
| Volumetric strain (microstrain) | −563 | −831 | −668 | −518 | −413 | −208 | −73 | −24 |

The load compresses the whole edifice root, and the compression is strongest just below the base of the cone.
Neither field produces dilatation above sea level beneath the summit, where the shallow swarms occur:

| Field | Value there |
|---|---|
| Edifice load | −410 to −830 microstrain |
| GNSS areal strain rate | −15 nanostrain/yr |

Dilatation there would need a source these models do not contain, such as the pressurisation of the
hydrothermal system.

SHmax of the load is tangential (circumferential) around the summit at and above sea level, and radial at
5 km below sea level and deeper (Fig. 18 of the paper). The horizontal shear strain of the load is
1–30 microstrain within 20 km of the summit. That is the strain the GNSS rates would accumulate in
10³–10⁴ years.

**For shear-wave splitting.** `strain_orientation.csv` lists, at elevations 1.5, 1, 0, −2, −5, −10 and −15 km:
- the GNSS shortening axis, every 5 km;
- the SHmax of the load, every 2 km within 20 km of the summit.

Each row gives the magnitude with the azimuth (degrees east of north). Fast directions of splitting from
aligned cracks are expected parallel to the most compressive horizontal stress.

**In the 3D viewer.** The five strain fields are properties of "Below ground". With the depth slice on, the
bars of the selected field are drawn at the nearest 1 km level: GNSS shortening axes for the tectonic fields,
SHmax for the load fields.
