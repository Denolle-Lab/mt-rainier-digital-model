---
title: "Supplement to: rainier3d, a reproducible digital model of the subsurface and surface of Mount Rainier, Washington. S1: local-earthquake tomography of the crustal model"
pagetitle: "rainier3d supplement: local-earthquake tomography"
kicker: "Gaia Hazlab · Supplement"
description: "Local-earthquake tomography (stage S37) of the rainier3d crustal model: data, method, ray coverage, resolution tests, velocity perturbations, residuals and the comparison of runs."
runningtitle: "rainier3d supplement: local-earthquake tomography"
runningauthor: "Denolle et al."
correspondence: "Marine Denolle (mdenolle@uw.edu)"
essd-authors:
  - {given: "Marine", family: "Denolle", orcid: "0000-0002-1610-2250", affil: "1", email: "mdenolle@uw.edu"}
  - {given: "Derek", family: "Yao", orcid: "0009-0003-2417-7062", affil: "2"}
  - {given: "Michael", family: "Hemmett", orcid: "0009-0007-9810-8800", affil: "1"}
  - {given: "Manuela", family: "Köpfli", orcid: "0000-0002-4678-730X", affil: "1"}
  - {given: "Sangwoo", family: "Han", orcid: "0000-0001-5832-7127", affil: "1"}
  - {given: "Maleen", family: "Kidiwela", orcid: "0000-0002-3040-5469", affil: "1"}
essd-affiliations:
  - {id: "1", name: "Department of Earth and Space Sciences, University of Washington, Seattle, WA, USA"}
  - {id: "2", name: "Computer Science and Art, University of Washington, Seattle, WA, USA"}
repository: "https://github.com/Denolle-Lab/mt-rainier-digital-model"
viewer: "https://denolle-lab.github.io/mt-rainier-digital-model/"
footer: "rainier3d supplement · Built from docs/paper/rainier3d_supplement.md by scripts/23_paper.py."
link-citations: true
numberSections: true
header-includes: |
  \renewcommand{\thesection}{S\arabic{section}}
  \renewcommand{\thefigure}{S\arabic{figure}}
  \renewcommand{\thetable}{S\arabic{table}}
  \renewcommand{\theequation}{S\arabic{equation}}
abstract: |
  This supplement describes the fourth stage of the rainier3d crustal model: a local-earthquake tomography (stage S37) that perturbs ln Vp and ln Vs of the fused and calibrated model of Sect. 4.3 of the main text. It uses 99,716 analyst P and S picks of 3770 PNSN earthquakes from 2015 to the data freeze of 23 September 2026, recorded by 50 stations inside the model box. Travel times are computed on a 250 m eikonal grid with topography, every earthquake is relocated in every trial model, and earthquakes in 10 km squares excluded from the fit choose the smoothing and the number of iterations. The perturbation is zero in the top 150 m below the ground or glacier bed, so the petrophysical critical-zone model is left as built. Two steps reduce the RMS residual of the held-out earthquakes from 0.0909 to 0.0725 s for P and from 0.1796 to 0.1209 s for S. Checkerboard tests recover 12 km structure between sea level and 6 km depth with correlations of 0.63–0.75; ray coverage is nearly absent below 15 km and beneath the summit below 5 km. The update is written to a separate store (`model_let.zarr`); the model product described in the main text is unchanged.
---

# Purpose {#sec:s-purpose}

The crustal model of the main text (Sect. 4.3) takes its short wavelengths from mapped geology extended to depth by rules, its long wavelengths from regional tomography, and three global rock-physics factors and a depth-dependent regional correction from PNSN travel times. None of these steps corrects lateral errors of the geological rules at wavelengths of 6–20 km, between what the geology encodes and what the regional models resolve. The tomography of this supplement asks how much lateral structure the PNSN arrival times add in that band, and with what resolution. It treats the calibrated model as the reference and inverts only for smooth perturbations of it, below the critical zone.

# Data {#sec:s-data}

The picks are PNSN analyst P and S arrival times from the ComCat phase-data products [@comcat_uw] of all events of magnitude 0.5 or larger located in the 70 × 75 km model box between 1 January 2015 and the data freeze of 23 September 2026 (3867 events, 117,609 picks; `data/raw/pnsn/catalog_2015-01-01_2026-09-23_m0.5`), merged with the 88 calibration events of the main text. Only the 50 stations inside the box are used, because the travel-time grid covers the box only. Events need at least six picks, four of them P. The data set has 3770 events, 57,659 P and 42,057 S picks, and a median of 25 picks per event ([@tbl:sdata], [@fig:sdata]).

Events are assigned to a fitting and a held-out set by 10 km squares of their catalogue epicentres. Squares are allocated in decreasing order of pick count to whichever set has fewer picks, which gives 1921 fitting and 1849 held-out events with 49,859 and 49,857 picks. About 1720 events lie less than 1 km below sea level beneath the summit, spread over the whole period with 620 of them in 2025. The summit square falls in the fitting set, so 81% of these events are fitted, and most held-out events belong to the West Rainier Seismic Zone (WRSZ) and the outer box. The held-out score therefore measures how well the update transfers to regions away from the summit cluster.

| Quantity | Fitting | Held out | Total |
|---|---|---|---|
| Events | 1921 | 1849 | 3770 |
| Picks | 49,859 | 49,857 | 99,716 |
| P picks (weight > 0, starting model) | 29,345 | 28,225 | 57,570 |
| S picks (weight > 0, starting model) | 20,455 | 21,539 | 41,994 |

: Data of the tomography. {#tbl:sdata}

![Data. (a) Epicentres after relocation in the final model, coloured by set (fitting, blue; held out, orange), with the 10 km squares that define the sets (grey lines), stations (▽) and the summit (△). (b) Stations sized by the number of picks. (c) Hypocentre depth below sea level for each set; the peak above 1 km is the summit cluster.](tomography/fig01_data.png){#fig:sdata width=100%}

# Method {#sec:s-method}

**Model.** The perturbation acts on the calibrated model of the main text, $V_0$, as
$$V(\mathbf x) = V_0(\mathbf x)\,\exp\!\left[w(d)\,m(\mathbf x)\right],$$ {#eq:slet}
where $m$ is interpolated trilinearly between nodes spaced 3 km horizontally (24 × 26) at nine depths, −3, 0, 2, 4, 6, 9, 13, 18 and 25 km below sea level, separately for P and S (5616 nodes per phase), and $d$ is the depth below the ground or the glacier bed. The weight $w$ is 0 in the top 150 m, the critical-zone columns of Sect. 4.2 of the main text, and rises linearly to 1 at 500 m (`tomography.cz_taper_m` in `configs/domain.yaml`). The forward model, the kernels and the written model use the same $w$, so the critical zone keeps its rock physics and joins the updated rock below without a step. The perturbation applies to rock only (`rainier3d.validate.tomo`, `scripts/37_tomography.py`).

**Forward problem.** The calibrated model is resampled on a 250 m travel-time grid (281 × 301 × 139 nodes, from 4.5 km above to 30 km below sea level). Within the top model level, whose cells are 50 m thick, each grid node takes the average slowness of the cells within half a grid spacing, so that thin slow layers keep their vertical travel time; at the first rock node below the ground this lowers the median Vs from 2804 m s⁻¹ (nearest-node sampling) to 2302 m s⁻¹. Cells more than one cell above the ground carry 343 m s⁻¹, so rays cannot cross valleys through air. Travel-time fields are computed for every station and phase with the fast-marching solver of @white_2020, by reciprocity.

**Location.** Every event is relocated in every trial model by a grid search below the ground on every second node (500 m), followed by a Huber-weighted [@huber_1964] Gauss–Newton refinement on the full grid, as in the calibration of the main text and in the grid-search-then-refine design of NonLinLoc [@lomax_2000]. Pick uncertainties are 0.14 s for P and 0.23 s for S, and picks beyond five standard deviations receive zero weight.

**Kernels and separation.** The derivative of a travel time with respect to node $k$ is $-\int s\,w\,w_k\,\mathrm d\ell$ along the ray, with $s$ the slowness and $w_k$ the trilinear weight; rays are traced down the gradient of the station's travel-time field in steps of a quarter grid spacing [@thurber_1983]. For the best-sampled S node, the ray derivatives of 17,831 picks agree with finite differences through the eikonal solver with a slope of 0.997 and a correlation of 0.9993 ([@fig:schecks]a). Each event's rows are projected onto the orthogonal complement of its hypocentre and origin-time partials [@pavlis_booker_1980].

**Regularisation.** Each step minimises the projected misfit of the fitting events plus $\lambda_s\lVert\mathbf D m\rVert^2 + \lambda_d\lVert m\rVert^2$, where $\mathbf D$ stacks second differences along the three axes (with the coefficients of uneven spacing in depth) and both weights are relative to the mean squared column norm of the projected matrix; $\lambda_d$ = 0.03. The system is solved with LSQR [@paige_saunders_1982]. At the first iteration the linearised held-out misfit is computed for $\lambda_s$ from 0.1 to 100; it decreases towards small weights and flattens below 0.3 (0.4872 at 0.3, 0.4862 at 0.1), and the largest weight within 1% of the best, $\lambda_s$ = 0.3, is used ([@fig:schecks]b).

**Stopping rule.** After each step all events are relocated and the held-out misfit, the mean of $(r/\sigma)^2$ over P and S picks, is recomputed. A step is kept if it lowers this misfit by more than 0.5%; otherwise half the step is tried, and if that also fails the last kept model is final. The first two steps lowered the misfit from 0.503 to 0.282 and 0.272; the third step and its half raised it to 0.2732 and 0.2724, and the inversion stopped ([@fig:schecks]c). Every trial model is saved before its travel times are computed, checked for non-finite or non-positive velocities, and its travel times must be computed within three times the time taken for the starting model; otherwise the trial counts as rejected.

![Checks of the inversion. (a) Ray-integral against finite-difference derivatives of S travel times with respect to the best-sampled S node (dashed: 1:1). (b) Linearised held-out misfit against the relative smoothing weight; the dashed line is the misfit without a model change. (c) Held-out misfit after relocation for each trial model; blue, kept; orange, rejected.](tomography/fig02_checks.png){#fig:schecks width=100%}

# Ray coverage {#sec:s-rays}

The ray of every pick is traced in the final model, and the ray length and the number of distinct rays are recorded in each 250 m cell. P rays pass through 1.05 million of the 11.8 million cells and S rays through 0.88 million; 118,587 cells are crossed by ten or more P rays, the densest (12 km south of the summit at 0.75 km elevation) by 3579. Aggregated in 1 km cubes ([@fig:sdensity; @fig:sdensitysec]), coverage is densest beneath the summit in the top 2 km and along the WRSZ between 2 and 12 km depth. It thins below 12 km and is nearly absent below 15 km. Directly beneath the summit few rays pass below about 5 km, because the summit earthquakes are shallow and the deeper earthquakes lie to the west. The sampled rays ([@fig:srays]) show two families: short, steep paths from the summit cluster to the stations on the edifice, and longer paths from the WRSZ across the volume between 2 and 12 km depth. An interactive view of 2000 rays with the terrain is on the project site (<https://denolle-lab.github.io/mt-rainier-digital-model/tomography/>).

![Ray length density in 1 km cubes (km of ray per km³, logarithmic) for P (top) and S (bottom) at depths from 0 to 13 km below sea level, with stations (▽) and the summit (△).](tomography/fig10_ray_density_slices.png){#fig:sdensity width=100%}

![P + S ray length density in 1 km cubes on west–east (top) and south–north (bottom) sections through the summit.](tomography/fig10b_ray_density_sections.png){#fig:sdensitysec width=80%}

![Ray paths in the final model for 400 P (blue) and 400 S (orange) picks drawn at random from the picks with non-zero weight, with sources (dots) and stations (▽).](tomography/fig11_rays_3d.png){#fig:srays width=80%}

# Resolution {#sec:s-resolution}

Checkerboards of ±5% with cells of 12 and 6 km in all three directions, P and S of opposite sign, are inverted with the projected kernels of the final model, Gaussian noise at the pick uncertainty and the same weights as the data ([@tbl:scheck], [@fig:scb12; @fig:scb6; @fig:srecovery]). This linear test does not include changes of ray paths or hypocentres, and a checkerboard can overstate the resolution of other structures [@leveque_1993], so we read it as an upper bound.

The 12 km pattern is recovered with correlations of 0.63–0.75 between sea level and 6 km depth and with 41–59% of its amplitude; recovery falls to 0.51–0.55 at 9 km and 0.28–0.31 at 13 km. The node layer 3 km above sea level recovers nothing, and the layer at 25 km recovers the pattern with the wrong sign: both are set by the smoothing operator. The 6 km pattern is recovered with correlations of 0.37–0.45 and about 20% of its amplitude in the top 2 km, where the summit earthquakes and the stations on the edifice provide crossing rays, and with 0.17–0.27 between 4 and 9 km.

| Node depth (km below sea level) | P, 12 km | S, 12 km | P, 6 km | S, 6 km |
|---|---|---|---|---|
| −3 | −0.05 (−0.02) | −0.15 (−0.07) | 0.04 (0.01) | 0.06 (0.03) |
| 0 | 0.63 (0.41) | 0.75 (0.47) | 0.45 (0.21) | 0.41 (0.19) |
| 2 | 0.69 (0.49) | 0.73 (0.53) | 0.39 (0.20) | 0.37 (0.17) |
| 4 | 0.67 (0.50) | 0.73 (0.59) | 0.25 (0.12) | 0.22 (0.09) |
| 6 | 0.66 (0.49) | 0.74 (0.57) | 0.17 (0.08) | 0.24 (0.09) |
| 9 | 0.51 (0.32) | 0.55 (0.31) | 0.22 (0.11) | 0.27 (0.11) |
| 13 | 0.28 (0.15) | 0.31 (0.17) | 0.04 (0.01) | 0.03 (0.01) |
| 18 | 0.56 (0.32) | 0.51 (0.36) | −0.02 (−0.01) | 0.01 (0.00) |
| 25 | −0.37 (−0.16) | −0.31 (−0.13) | −0.10 (−0.06) | −0.19 (−0.08) |

: Checkerboard recovery: correlation of input and recovered patterns, and amplitude ratio in parentheses, at nodes whose derivative weight sum exceeds 5 km. {#tbl:scheck}

![Checkerboard test with 12 km cells. Rows: input P, recovered P, input S, recovered S; columns: node depth below sea level. Inputs on a ±0.05 scale, recoveries on ±0.02; nodes whose derivative weight sum is below 5 km are whitened. Blue, fast; red, slow.](tomography/fig03_checkerboard_12km.png){#fig:scb12 width=100%}

![As [@fig:scb12] for 6 km cells.](tomography/fig03_checkerboard_6km.png){#fig:scb6 width=100%}

![Checkerboard recovery against node depth: (a) correlation and (b) amplitude ratio, for 12 km (solid) and 6 km (dotted) cells, P (blue) and S (orange).](tomography/fig04_recovery_by_depth.png){#fig:srecovery width=75%}

# Results {#sec:s-results}

**Misfit.** The two kept steps reduce the RMS residual of the held-out events by 20% for P and 33% for S, and their median absolute residual by 34 and 42% ([@tbl:sresid], [@fig:sresid]). The fitting events gain more, 40 and 47%; the difference is the part of the update that does not transfer across regions. The RMS of held-out residuals averaged per station (at least 20 picks) falls from 0.051 to 0.023 s for P and from 0.152 to 0.067 s for S ([@fig:sstations]). Since the critical zone is not changed, these station delays are explained by the rock between 150 m and a few kilometres, without station terms.

| Set and phase | RMS, start (s) | RMS, final (s) | Change | Median \|r\|, start (s) | Median \|r\|, final (s) |
|---|---|---|---|---|---|
| Held out, P | 0.0909 | 0.0725 | −20% | 0.0482 | 0.0318 |
| Held out, S | 0.1796 | 0.1209 | −33% | 0.1079 | 0.0628 |
| Fitting, P | 0.0913 | 0.0546 | −40% | – | – |
| Fitting, S | 0.1794 | 0.0959 | −47% | – | – |

: Residuals after relocation in the starting and final models (picks with non-zero weight); the held-out misfit, mean $(r/\sigma)^2$, falls from 0.503 to 0.272. {#tbl:sresid}

![Residuals after relocation, starting model (blue) and final model (orange), for P (top) and S (bottom), fitting (left) and held-out (right) events.](tomography/fig07_residuals.png){#fig:sresid width=100%}

![Mean held-out residual at each station with at least 20 picks, starting (left) and final (right) model, for P (top, ±0.15 s) and S (bottom, ±0.3 s). Red, late arrivals; blue, early.](tomography/fig08_station_means.png){#fig:sstations width=100%}

**Velocity perturbations.** Nodes with a derivative weight sum above 5 km make up 52% of the P nodes and 46% of the S nodes ([@fig:sslices], bottom row). Within them the perturbation has a mean of +0.006 and an RMS of 0.045 for ln Vp and a mean of −0.0004 and an RMS of 0.053 for ln Vs (5th to 95th percentiles −0.067 to +0.074 and −0.082 to +0.066). Between sea level and 6 km depth, velocities increase by 5–8% in an arc north-east, east and south of the summit and decrease by similar amounts west and south-west of it, around and above the WRSZ; the vertical sections show a fast upper crust immediately east of the WRSZ ([@fig:ssections]). The node layer 3 km above sea level within 4.5 km of the summit, inside the edifice, is slower by 3.2% in Vp and 7.6% in Vs on average, but the checkerboard is not recovered at that layer, so the edifice anomaly cannot be interpreted with this parameterisation. A slow column beneath the summit from about 5 to 20 km depth lies where ray coverage is nearly absent; it is the downward continuation of the edifice anomaly by the smoothing operator and carries no information from the data. Outside the sampled nodes the perturbation reaches 0.19 for P and 0.34 for S, mostly in the corners of the box, because the second-difference regulariser does not penalise linear gradients.

![Velocity perturbation relative to the calibrated model, ln Vp (top) and ln Vs (middle), on node depth slices from 0 to 13 km below sea level; nodes whose derivative weight sum is below 5 km are whitened, and dots are hypocentres within 1.5 km of each slice. Bottom: log₁₀ of the S derivative weight sum, with stations (▽).](tomography/fig05_model_slices.png){#fig:sslices width=100%}

![Vertical sections through the summit, west–east (left) and south–north (right): S velocity in the calibrated model and after the update, ln Vs perturbation (not masked; below about 5 km beneath the summit and below 15 km elsewhere it lies outside the sampled volume) and Vp/Vs after the update, with hypocentres within 3 km of each section.](tomography/fig06_sections.png){#fig:ssections width=100%}

**The critical zone.** The perturbation is zero in the L1 cells that average the critical-zone columns, except in the cells that straddle the 150 m base, where the taper begins and the change is at most 2.0% in Vp and 2.8% in Vs. All ten invariant tests of the model (`tests/test_invariants.py`) pass on `model_let.zarr`: among them, the vertical S travel time of the top two rock cells equals that of the critical-zone columns to 10⁻³ in all 81,388 ice-free columns, Vp/Vs stays at most 4.70 in cells that contain critical zone and between 1.61 and 2.11 in the rock below, and the fused Vp/Vs beneath the tomography factor lies between its geology and regional inputs.

**Hypocentres.** Relocation in the final model moves epicentres by a median of 483 m and hypocentres shallower by a median of 734 m ([@fig:sreloc]): by 944 m for the 1666 events within 5 km of the summit and by 480 m elsewhere; 122 events move by more than 3 km in depth. The median formal depth uncertainty falls from 422 to 266 m. The mean velocity change is close to zero, so the upward shift beneath the summit is unlikely to be a uniform trade-off between velocity and depth; it may be related to the slower edifice above sea level, which lies at a node layer that the checkerboard does not resolve.

![Change of hypocentres between relocation in the calibrated and in the final model: (a) epicentre shift, (b) depth change (positive deeper) and (c) depth change against starting depth.](tomography/fig09_relocation.png){#fig:sreloc width=80%}

# Comparison of runs {#sec:s-runs}

Two earlier runs used the same data and splits ([@tbl:sruns]). The first used the 500 m grid of the calibration, nearest-node sampling and its own smoothing weight, $\lambda_s$ = 10, and no taper: it kept one step, resolved only 12 km structure, and gave a positive mean perturbation (+2.2% in Vp, +1.6% in Vs) coupled to a larger upward shift of hypocentres. The second used the 250 m grid with slowness averaging but no taper. Between these two the grid, the sampling and the smoothing weight change at once, so the table does not attribute the differences to any one of them; the stronger resolution on the finer grid follows in large part from the weaker smoothing that the held-out events chose. The second run and the run of this supplement differ in the taper and in the starting model, which was recalibrated after the geology of the fusion was smoothed (held-out RMS of the starting model 0.0908 and 0.1794 s against 0.0909 and 0.1796 s). The taper alone was tested on the earlier starting model (run of 13 October 2026, `outputs/tomography_250m_cztaper_cal44/`): it raised the held-out misfit from 0.258 to 0.274. Without it, the inversion changed Vs by more than 5% in 30% of the critical-zone cells and broke the travel-time agreement with the critical-zone columns in 79% of the columns: a small gain obtained by changing a layer that the travel times do not resolve. The final run reaches 0.272.

| Quantity | 500 m, no taper | 250 m, no taper | 250 m, critical zone as built, recalibrated starting model |
|---|---|---|---|
| Smoothing weight $\lambda_s$ | 10 | 0.3 | 0.3 |
| Steps kept | 1 | 2 | 2 |
| Kernel check, slope and correlation | 1.02, 0.998 | 0.998, 0.9993 | 0.997, 0.9993 |
| Held-out RMS final, P / S (s) | 0.0788 / 0.1437 | 0.0712 / 0.1167 | 0.0725 / 0.1209 |
| Held-out misfit final | 0.349 | 0.258 | 0.272 |
| 12 km checkerboard correlation, P, 0–6 km | 0.43–0.45 | 0.65–0.70 | 0.63–0.69 |
| 6 km checkerboard correlation, P, 0–2 km | 0.05–0.09 | 0.40–0.41 | 0.39–0.45 |
| Mean ln Vp / ln Vs, sampled nodes | +0.022 / +0.016 | +0.004 / −0.001 | +0.006 / −0.0004 |
| RMS of held-out station means, P / S (s) | 0.036 / 0.116 | 0.022 / 0.062 | 0.023 / 0.067 |
| Critical-zone cells changed by more than 5% in Vs | – | 30% | 0% |
| Invariant tests on the result | – | critical-zone travel time fails | all pass |

: Runs of the tomography with the same data and splits. {#tbl:sruns}

# Limitations and next steps {#sec:s-limits}

- **Resolution.** Structure smaller than about 12 km is resolved only in the top 2 km near the summit. Below 12 km, and beneath the summit below 5 km, the perturbations are set by the regularisation; this includes the depth range of the low-velocity body of the main text.
- **Station geometry.** Only the 50 stations inside the box are used. Of the 6876 picks of the 91 validation events of the main text, 3108 remain after restriction to stations and events inside the box; extending the travel-time grid beyond the box would add the rest.
- **Unsampled volume.** Damping should increase where the derivative weight sum is small, so that unsampled nodes return to the calibrated model.
- **Tests.** A test with structures of realistic shape, and a nonlinear version of the resolution test that includes relocation, should complement the checkerboards; the grids should be compared at the same smoothing weight.
- **S arrivals.** More S picks, for example from automatic picking of the 2025 nodal deployment, would reduce the larger S uncertainties.
- **Parameters.** The node spacing, depths, damping, block size, stopping tolerance, grid spacing and taper are author choices (`m1_placeholder`), in the `tomography` block of `configs/domain.yaml`.

# Code and data availability {.unnumbered}

The tomography is `scripts/37_tomography.py` with `rainier3d.validate.tomo`; its figures are drawn by `scripts/37_tomography_figures.py` from `outputs/tomography/`, which also holds the ray density, the sampled ray paths and every trial model. The result is `data/processed/model_let.zarr`, beside the model product `model.zarr`. The figures of this supplement and an interactive view of the rays are published at <https://denolle-lab.github.io/mt-rainier-digital-model/tomography/>.

# References {.unnumbered}
