---
title: "Apparent magnetisation of the 1996 and 2022 aeromagnetic surveys"
date: 2026-10-01
bibliography: references.bib
---

<!-- Pandoc Markdown. Citations [@key] resolve through docs/references.bib (pixi run bib). -->

# Apparent magnetisation of the 1996 and 2022 aeromagnetic surveys

**Script:** S31 (`scripts/31_packwood_magnetics.py`, `pixi run s31`). The code is in `src/rainier3d/alteration/packwood.py`, and the parameters are in `configs/magnetics.yaml`.
**Products:** `data/processed/packwood_magnetics.zarr` (fields on the model surface grid) and two layers of the 3D viewer.
**Status of the numbers:** they come from `outputs/magnetics/summary.json`, run on 1 October 2026 on the published model (products-v1.0.0), and from the one-off checks on that run described here (the 500 m and 2 km windows, the 15 km reach, the gap fill and the amplitude ratio in the overlap).

## Summary

The 1996 helicopter survey of the edifice [@rystrom_2000] gives the terrain-correlated apparent magnetisation of S22 (`docs/alteration.md`). The 2022 Packwood fixed-wing survey [@blakely_2024] covers 69% of the model domain around the edifice but not the edifice itself. S31 computes the same quantity for the 2022 survey and merges the two fields into one map. The two surveys overlap in a ring up to 3 km wide around the edifice, where they correlate at 0.645.

Two maps are produced: one with glacier ice counted as rock, as in S22, and one with the ice left out of the magnetised terrain.

## 1. Data

| | 1996 helicopter survey | 2022 Packwood survey |
|---|---|---|
| Reference | @rystrom_2000; @finn_2001 | @blakely_2024 |
| Area | the edifice, 22 × 13 km | around the edifice, 4335 km²; 69% of the domain |
| Lines | ~250 m apart | 400 m east–west, tie lines 4 km north–south |
| Sensor above the ground (median, model grid) | 82 m | 699 m (10th–90th percentile 408–1117 m) |
| Grid used | `rp.gxf`, reduced to the pole by the authors (62 m) | `Packwood_grid_MAIN.gxf`, total-field anomaly (MAGRES, 100 m) |
| Sensor height used | flight elevation of the flight lines | channel DRAPE of `Packwood_data_MAIN.csv` |

The 2022 drape was planned 200 m above the terrain, but climb and descent limits kept the aircraft much higher over the valleys. At ~700 m above the ground the 2022 anomalies are broader and about half as large as the 1996 ones over the same rock (standard deviation ratio of the reduced-to-pole anomalies 0.46 in the overlap). Only the regression below accounts for this height, through the sensor height in the forward model; the reduction to the pole does not.

The 2022 grid is in WGS84 / UTM 10N, as the model. Its orientation is checked against the data: the high-passed reduced-to-pole anomaly correlates with the high-passed topography at 0.30 as read and at 0.03 if flipped north–south.

## 2. Method

1. **Reduction to the pole (2022).** The published anomaly removes IGRF-12 extrapolated to the survey date. That field is about 25 nT below IGRF-13 there, so the anomaly is about 25 nT higher than with IGRF-13, a nearly constant offset that the regression does not see. The field direction is that of IGRF-13 [@igrf13] at the centre of the grid, at the height and date of the survey's IGRF channel: inclination 68.37°, declination 15.05°, computed from the IAGA IGRF-13 coefficients at 46.722° N, 121.833° W; they can be checked with any IGRF-13 calculator. Induced magnetisation along the field is assumed. Gaps, including the edifice, are filled with the harmonic interpolant, and the grid is reflect-padded by a third on each side before harmonica's transform. The fill matters next to the gap: filling with the mean instead changes the 2022 field in the overlap ring by 0.11 A/m (median; 99th percentile 1.1 A/m) and lowers its correlation with 1996 from 0.645 to 0.565, against 0.003 A/m elsewhere. The merge gives the 1996 field most of the weight there.
2. **Terrain effect.** G is the anomaly at the sensor of the terrain from 0 m to the surface magnetised 1 A/m vertically (harmonica prisms on the 100 m model grid). For 2022 the sensor is the drape surface, kept at least 20 m above the ground. Prisms more than 5 km beyond each 5 km tile of sensors are left out. On a 20 × 20 km block, a 15 km reach changes the apparent magnetisation by 0.014 A/m (median; 99th percentile 0.08 A/m).
3. **Apparent magnetisation.** M is the slope of the reduced-to-pole anomaly on G in a Gaussian window. A constant in each window absorbs sources broader than the window. The window is σ = 500 m for 1996 (S22) and σ = 1 km for 2022 (`window_sigma_m` in `configs/magnetics.yaml`). At ~700 m above the ground the 2022 survey does not resolve features smaller than ~1–2 km, and a 500 m window makes its slope noisy where the terrain signal is weak. The 1st and 99th percentiles of the 2022 field are −4.3 and 5.4 A/m with σ = 500 m, −3.4 and 4.1 A/m with 1 km and −3.1 and 2.6 A/m with 2 km: 1 km was chosen by looking at the maps, between the noisy 500 m and the smooth 2 km; it is a placeholder, not a derived value.
4. **Merge.** Where both fields exist, the 1996 weight falls linearly with distance from 1 at the edge of the 2022 gap to 0 at the edge of the 1996 survey. Elsewhere the survey with data is used as it is.
5. **Glacier ice.** The first map counts glacier ice as magnetised rock, as S22 does. The second tops the prisms at the bedrock surface, the elevation minus the IceBoost v2 thickness [@iceboost_v2], for both surveys. The sensor height is unchanged.

The 1996 field is recomputed with the S22 code (`finn2001.apparent_magnetization`) and the same inputs (the checksums of `docs/data_manifest.csv`). It agrees with the published S22 field to within 0.05 A/m.

## 3. Results

| | Ice as rock | Ice excluded |
|---|---|---|
| Overlap: correlation of 2022 and 1996 | 0.645 | 0.645 |
| Overlap: median 2022 minus 1996 (A/m) | 0.10 | 0.10 |
| Merged map, 10th / 50th / 90th percentile (A/m) | −0.28 / 0.49 / 1.87 | −0.27 / 0.49 / 1.88 |

Leaving out the ice changes the map only on the glaciated upper cone. Where the ice is thicker than 10 m, the change is +0.11 A/m (median), from −0.47 to +0.83 A/m (1st and 99th percentiles). It is positive near the summit, where the ice had been counted as magnetised rock. It is negative in places on the north and northeast flanks, where removing the ice deepens the valleys of the terrain model. These are also the glaciers (Emmons, Winthrop) where IceBoost exceeds the 1981 radar thicknesses (paper, section on elevation, geology and glaciers), so the change there is the least certain.

## 4. What the maps do and do not show

- **The apparent magnetisation is a model parameter, not a measurement.** It is the magnetisation of uniformly magnetised terrain that best explains the local covariance of the anomaly with the terrain effect.
- **Low values have several causes.** Demagnetised (altered) rock lowers it, but so does a weak terrain signal in the window, a source not tied to the terrain (a buried intrusion) or remanence in another direction. Negative values occur mostly where the terrain signal is weak.
- **The two surveys do not resolve the same scales.** The 2022 survey resolves only features broader than ~1–2 km, so its finer detail in these maps is partly noise. The merge removes the seam but not this difference.
- **The ice thickness is a model.** The ice-excluded map inherits the uncertainty of IceBoost v2, largest on Emmons and Winthrop glaciers.

## 5. Products and access

In the 3D viewer, the surface layers "Apparent magnetisation (merged)" and "Apparent magnetisation (ice excluded)" (group "Geology") show the two maps, next to the S22 layer "Apparent magnetisation (terrain-correlated)". S31 adds them to an existing viewer bundle, and S11 adds them again when it rebuilds the bundle. The store `packwood_magnetics.zarr` also holds the 2022 anomaly, its reduction to the pole, the drape surface, each survey's field and the 1996 weight.

Reproduce with:

```bash
pixi run s31            # or: pixi run s31 -- --model <published model.zarr>
```

## References
