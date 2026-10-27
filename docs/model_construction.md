# How the rainier3d subsurface model is built

Status: 2026-10-27, branch `paper-review-fixes` (rebuild of 27 October 2026 on a Linux server). This document records, stage by stage, how the seismic and
hydraulic model of the subsurface is assembled, what each stage changes and what it leaves alone, so that the
construction can be disclosed in the paper (paragraph at the end). Numbers come from reruns of the stages named;
the stage scripts are `scripts/NN_*.py`, the parameters `configs/*.yaml`, and every value without a published
source carries the registry key `m1_placeholder` (`configs/sources.yaml`).

The model is built in four layers of evidence, from the most local to the most constrained by data:

| Stage | What it supplies | What it does not do |
|---|---|---|
| 1. Geology (S1 to S3) | Units, their geometry and alteration, from maps and stated rules | No velocities |
| 2. Rock physics (S4) | Vp, Vs, density, Q, porosity and permeability of every cell, including a critical zone built from the same laws | No fit to travel times |
| 3. Fusion with earlier models (S5, with the S13 calibration) | Long wavelengths from regional tomography; smooth contacts; global factors fitted to travel times | No lateral correction of the geology at scales below ~6 km |
| 4. Tomography (S37) | Lateral corrections of about 12 km and larger, fitted to 99,716 PNSN arrivals and tested on held-out events | Nothing in the critical zone; no structure below its resolution |

## 1 Geology (S1 to S3)

- **Surface (S1).** Mapped units of the DNR 1:100k geology crosswalked to 16 model units (`configs/units.yaml`,
  `configs/crosswalk_geology.json`), glacier ice thickness, deposit thicknesses per map symbol from the
  Description of Map Units, the 1996 helicopter EM survey for alteration (S22).
- **Surface layers (S2).** Soil thickness, texture, bulk density and hydraulics (SOLUS100, POLARIS), depth to bedrock
  (SoilGrids 2017), water table (Fan et al. 2017), canopy height.
- **Column rules (S3, `rainier3d.geomodel.rules`).** Below each surface cell, top down: ice, the deposit layer,
  Rainier volcanics above an interpolated pre-volcanic surface (the edifice base), the young-volcanic cap to 300 m
  below the bedrock top, basement units extended to −4 km and plutons to −10 km, middle crust below. A magma body is
  a sphere of radius 6.5 km centred 11.5 km below sea level, spanning the 5–18 km range of Moran et al. (1999), with
  a 2 km cosine taper of its anomaly (`magma_weight`).
- **Consequence.** Contacts are rule surfaces. Flat-lying ones (edifice base, cap base) and the vertical walls where
  map units are extended to depth are sharp by construction; stage 3 smooths them.

## 2 Rock physics, including the critical zone (S4)

- **Rock law (`rainier3d.properties.assign.rock_properties`).** Vp from a crack-closure law in effective pressure,
  Vs from the unit's Vp/Vs or Brocher (2005), density from the unit or Nafe–Drake, the alteration factors; one law
  for every cell. The magma anomaly is not applied here (stage 3).
- **Critical zone (`rainier3d.cz.medium`, `rainier3d.cz.level`, `configs/cz.yaml`, `docs/critical_zone.md`).** Fine
  columns from the ground (or the glacier bed) to 150 m: soil, Quaternary cover, weathered rock, fractured rock, fresh
  rock. One medium: a weathering index W (1 in soil, cover and weathered rock, falling to 0 across the fractured
  zone) blends a granular frame (Hertz–Mindlin with the soft-sand bound, Gassmann with a Brie fluid, suction stress
  above the water table) with the rock law at the same effective stress, by a Hill average of the moduli. Where W =
  0 the medium is the rock law, so the critical zone joins the rock below without a step: at the 150 m base, Vs is
  within a median 0.5% (90th percentile 1.5%) of the L1 cell below (`cz.base_continuity` in
  `outputs/paper/numbers.json`).
- **Coupling to the model grid.** L1 cells (50 m) that reach into the columns take their travel-time average; the
  top rock cell of each column averages from the ground (or bed) to its base. Invariant
  `test_l1_keeps_the_travel_time_of_the_critical_zone`: the vertical S time through the top two rock cells equals
  that of the columns to 10⁻³ in every ice-free column (81,388 checked).
- **Bounds.** Vp/Vs ≤ 3 in cells without critical zone, ≤ 5 in cells that contain it (saturated granular media,
  Pasquet et al. 2015); invariant `test_physical_ranges`.

## 3 Fusion with earlier models and calibration (S5, S13)

- **Regional models.** USGS Cascadia CVM v1.7 to 9.9 km below the ground (the base of its data), CRESCENT Gen0
  below (`rainier3d.fusion.regional`). The jump between them at 9.9 km (median 6% in Vs, CRESCENT faster) is
  spread with a raised cosine over 8–16 km below the ground (`fusion.regional_blend_m`, `m1_placeholder`): CVM
  plus W times the jump above 9.9 km, CRESCENT minus (1 − W) times the jump below, so each model is used only
  where it has data.
- **Fusion in ln V (`rainier3d.fusion.blend`).** Vs and Vp/Vs of the fused model are the long wavelengths of the
  regional model plus the short wavelengths of the geology model: LP(regional) + [geology − LP(geology)], with a
  horizontal Gaussian whose cutoff grows from 6 km at the surface to 20 km at depth; alternating projections keep
  every cell between its two inputs. The top 300 m is the geology model alone, tapering to the fused model by 1 km.
- **Smoothing of the rule contacts (`blend.smooth_geology`).** Below the 150 m critical-zone columns the geology is
  low-passed in the vertical (cutoff growing to 1 km) and horizontally (cutoff growing from zero at 150 m to
  750 m 150 m deeper, then with depth, to 2 km; `lambda_h_ramp`, `lambda_h_start_m`), before fusion. The critical
  zone itself is not smoothed and is not smoothed into the cells below; the horizontal cutoff starts from zero so
  that the unsmoothed critical zone does not meet smoothed rock in a step at its base.
  Effect in L1 (fused Vs with the calibration of 21 October, without and with the smoothing; measured on the run
  of 21 October 2026, with the lateral cutoff starting at 750 m, not recomputed): vertical jumps across unit
  contacts below 150 m (median |Δ ln Vs|) 0.146 → 0.031; lateral jumps across unit boundaries at 1–2 km depth
  0.019 → 0.006. Roughness of the whole model: `rainier3d.report.roughness`
  (`model.roughness` in `outputs/paper/numbers.json`).
- **Magma body.** Its anomaly (−10% Vp, −15% Vs, −3% density, `configs/perturbations.yaml`, placeholders) is applied
  to the fused model, so the fusion does not remove it.
- **Calibration (S13, `configs/velocity_calibration.yaml`).** Three global factors of the rock law and a
  depth-dependent bias of the regional model, fitted to PNSN P and S arrivals of 88 events with 3D relocation;
  held-out RMS 0.0937 s (P), 0.1877 s (S) after the fitting half, 0.0926 and 0.1880 s for the final model
  (refit of 27 October 2026 on the blended and smoothed model; V₀ ×1.45, P* ×1.36, Vs ×0.958).

## 4 Tomography (S37)

- **What it solves for (`rainier3d.validate.tomo`, `scripts/37_tomography.py`).** Smooth perturbations of ln Vp and
  ln Vs of the stage-3 model on 3 km nodes (9 depths, −3 to 25 km below sea level), V = V₃ exp(w m).
- **The critical zone is left as built.** w is 0 in the top 150 m below the ground or the glacier bed (the
  critical-zone columns) and rises linearly to 1 at 500 m (`tomography.cz_taper_m`). The forward model, the
  kernels and the written model use the same w, so the critical zone keeps its rock physics, joins the updated rock
  below continuously, and the stage-2 invariant still holds in the result.
- **Data and forward problem.** 99,716 PNSN analyst picks (57,659 P, 42,057 S) of 3,770 earthquakes, 2015 to the
  data freeze of 2026-09-23, 50 stations inside the domain; eikonal travel times on a 250 m grid with topography,
  the starting model sampled by slowness averaging so that the critical zone keeps its vertical travel time; every
  event relocated in every trial model; hypocentres separated from velocity (Pavlis & Booker 1980).
- **Validation.** Events in alternate 10 km squares (balanced by pick count) are held out. They choose the smoothing
  weight and decide when to stop: a step is kept only if it lowers their misfit after relocation by more than 0.5%.
- **What it does to discontinuities.** The tomography adjusts structure of about 12 km and larger; it does not
  sharpen or smooth contacts at the kilometre scale, which stage 3 sets.
- **Result (run of 2026-10-27 on the blended, smoothed and recalibrated model, 127.1 min on a 48-core server).**
  Three steps kept (two on 14 October), smoothing weight 0.3 chosen on the held-out events. Held-out RMS 0.0904 →
  0.0722 s (P, −20%) and 0.1802 → 0.1206 s (S, −33%); RMS of held-out station means 0.052 → 0.023 s (P) and
  0.152 → 0.066 s (S), without station terms. Checkerboard: 12 km cells recovered with correlation 0.66–0.74 and
  45–54% of the amplitude between sea level and 6 km depth, 6 km cells with 0.37–0.43 in the top 2 km; nothing
  above sea level and little below 12 km. Ray kernels checked against finite differences through the eikonal
  solver (slope 0.9995, correlation 0.9993). On the sampled nodes the update has a mean of +0.1% (Vp) and −0.5%
  (Vs) and an RMS of 4.7% and 5.7%.
- **The critical zone after the tomography.** Unchanged in the 150 m columns; at most 2.3% (Vp) and 3.0% (Vs) in the
  L1 cells that straddle the 150 m base. All 10 invariants of `tests/test_invariants.py` pass on `model_let.zarr`
  (`RAINIER3D_MODEL=data/processed/model_let.zarr pixi run pytest tests/test_invariants.py`), including the
  critical-zone travel time. Without the taper the same inversion changed Vs by more than 5% in 30% of the
  critical-zone cells and broke the travel-time agreement in 79% of the columns, for a held-out misfit of 0.258
  against 0.274: a small gain bought with an unresolved change to a layer built from rock physics.
- **Product.** `data/processed/model_let.zarr`; `model.zarr` remains the stage-3 model until the update is adopted.
  Report: `docs/tomography/index.html` (site `/tomography/`). The stages run as the `pixi` families `model`,
  `calibrate` and `tomography` (README, Pipeline).

## Disclosure paragraph for the paper

The subsurface model is built in four stages, each recorded in the repository with its parameters and sources.
First, mapped geology is extended to depth by stated column rules, which produce flat-lying contacts and vertical
unit boundaries by construction. Second, every cell receives Vp, Vs and density from one crack-closure rock law at
its effective pressure, and the top 150 m below the ground or glacier bed are built as a critical zone from the
same law blended with a granular frame at the same effective stress, so that the near surface is petrophysically
consistent with the rock beneath it. Third, the geology-based model is fused in ln V with the USGS Cascadia
community velocity model and CRESCENT Gen0, blended over 8–16 km below the ground, which supply wavelengths longer
than 6–20 km; before fusion the rule contacts below the critical zone are low-passed with cutoffs that grow with
depth (to 1 km vertically, and horizontally from zero at the base of the critical zone to 2 km), and a small number
of global factors are calibrated against PNSN travel times. Fourth, a
local-earthquake tomography of PNSN P and S arrivals, with relocation in every model and earthquakes held out by
region to choose the regularisation and the number of iterations, perturbs the fused model at wavelengths of about
12 km and larger below the critical zone, which it leaves unchanged; it reduces held-out P and S residuals by 20
and 33 per cent without station terms. Numerical values chosen by the authors rather than taken from the literature
are labelled as placeholders in the configuration files.
