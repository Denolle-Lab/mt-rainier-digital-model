# Next rebuild: smoother model interfaces, unit rename (October 2026)

A brief for the session that runs this rebuild on the Linux server (`docs/running_remotely.md`). The branch is
`paper-review-fixes` (PR #43). Marine Denolle approved the changes on 15 October 2026. Follow `AGENTS.md`.

## Why

Figure 17 of the paper (section B–B′, `docs/paper/figures/fig5_section_BB.png`) shows steps in the model that
are not geology. The local-earthquake tomography (S37) does not remove them: its update has a wavelength of
about 12 km and is zero in the top 150 m. Baseline from `pixi run python -m rainier3d.report.roughness
data/processed/model.zarr`, model of 14 October 2026:

| \|Δ ln Vs\| between neighbouring 250 m cells | median | p95 | p99 |
|---|---|---|---|
| across the L2/L3 level boundary, −6 km | 0.0048 | 0.013 | |
| across the CVM v1.7 to CRESCENT switch, 9.9 km below the ground | 0.0083 | 0.018 | |
| ordinary vertical step, 7–9 km below the ground (reference) | 0.0005 | 0.0026 | |
| lateral, 150–1000 m below the ground | 0.0029 | 0.054 | 0.20 |
| lateral, 1000–2000 m below the ground | 0.0028 | 0.015 | 0.036 |

## Tasks

1. **CVM v1.7 to CRESCENT.**
   - **Now:** `rainier3d.fusion.regional` switches from CVM v1.7 to CRESCENT Gen0 (with Brocher Vp) at
     `CVM_MAX_DEPTH` = 9.9 km below the ground.
   - **Change:** blend the two over a depth window, for example 8–12 km below the ground, with a smooth weight.
     Put the window in `configs/domain.yaml` with a source key (`m1_placeholder` if it is a choice), not in code.
   - **Target:** `cvm_crescent_step` near the reference step.
2. **L2/L3 boundary at −6 km.**
   - **First find the cause:** each level is fused and low-passed on its own grid, with its own spacing.
     Compare L2's bottom cell and L3's top cell at the same columns, in `vs` and in `vs_regional` and
     `vs_geology`, before changing anything.
   - **Change:** make the two levels agree where they meet, for example by low-passing on a common grid or by
     blending across the boundary.
   - **Target:** `l2_l3_step` near the reference step.
3. **Walls of extruded map units below the critical zone.**
   - **Now:** `blend.smooth_geology` (`lowpass_h_growing`) starts the lateral cutoff at zero at the
     critical-zone base (`lambda_z_from_depth_m`, 150 m) and grows it to `lambda_h_m` 2 km at 2 km depth.
   - **Change:** start it at a finite cutoff below the critical zone, for example 500–1000 m, still growing with
     depth. Keep the critical zone untouched: the top 150 m stays as built.
   - **Target:** a lower p99 of `lateral_150_1000m`, with the contacts of the geology still visible in
     Figures 16 and 17.
4. **Rename unit 6.**
   - **Change:** `rainier_andesite` becomes `rainier_volcanics`, label "Rainier volcanics", because the edifice
     is not only andesite. The code stays 6 and its parameters do not change.
   - **Files:** `configs/units.yaml`, `configs/petrophysics.csv`, every reference in `src/`, `scripts/` and
     `tests/` (`git grep -n rainier_andesite`), the paper and supplement text ("Rainier andesite"),
     `docs/velocity_model.md` and the figure legends.

## Checks after each change

- **Fast loop:** `pixi run s4 && pixi run s5`, then the roughness script and `pixi run test`. The invariants in
  `tests/test_invariants.py` must pass without loosening a tolerance.
- **Arrays:** compare arrays before and after with a checksum, so that each change touches only what it should.

## Rebuild and finish

1. **Run the families:** `model`, `calibrate`, `validate`, `tomography`, `applications` and `deliver`, as in
   `docs/running_remotely.md`, with `RAINIER3D_WORKERS` set to the core count.
2. **Paper numbers:** `outputs/paper/numbers.json` (S10) holds every model-derived number of the paper. Update
   the text from it; the numbers that change are listed in the description of PR #43. Add the roughness table
   above, before and after, to the paper's fusion section.
3. **Supplement and tomography report:** update their numbers from the new S37 run (`outputs/tomography/`).
4. **Notebook:** run `examples/pykonal_tutorial.ipynb` on the new model and check that the rays no longer bend
   at about −9 km.
5. **Products release:** do not publish it. `products-v1.1.0` (S20) is a public release, and Marine decides
   when it goes out.

## Outcome (rebuild of 21 October 2026)

Run on the Linux server (48 cores, `RAINIER3D_WORKERS=48`), all eight families from the cached inputs
(`pixi run manifest -- --check`: 6213 of 6213 files identical). Log: `outputs/logs/rebuild_20261021.log`.
`pixi run test`: 153 passed, none skipped; no tolerance changed.

**Roughness.** Same metric before and after (`rainier3d.report.roughness`, uniform 250 m grid). "Before" is the
model built here from the code and calibration of 14 October (it reproduces the baseline table above exactly);
"after" is the published model, recalibrated. The CVM-to-CRESCENT measure is now the largest step per column
6–16.5 km below the ground (one step at 9.9 km would miss a blend, whose slope is zero at its ends).

| \|Δ ln Vs\| between neighbouring 250 m cells | before (median, p95, p99) | after |
|---|---|---|
| L2/L3 level boundary, −6 km | 0.0048, 0.013 | 0.0030, 0.0043 |
| CVM v1.7 to CRESCENT, largest step per column, 6–16.5 km below the ground | 0.012, 0.0185 | 0.0037, 0.0062 |
| reference: same statistic 16.5–20.5 km below the ground (CRESCENT only) | 0.0007, 0.0015 | 0.0011, 0.0020 |
| ordinary vertical step, 7–9 km below the ground | 0.0005, 0.0026 | 0.0028, 0.0038 |
| lateral, 150–1000 m below the ground | 0.0029, 0.054, 0.199 | 0.0045, 0.047, 0.109 |
| lateral, 1000–2000 m below the ground | 0.0028, 0.015, 0.036 | 0.0034, 0.014, 0.023 |

The 7–9 km band is no longer a clean reference: the recalibrated regional correction is steeper between its
4, 7 and 11 km knots, and the blend window starts at 8 km.

**Tasks.**
1. **CVM to CRESCENT: done, with a different formulation.** The jump at 9.9 km is 0.062 in ln Vs at the median
   column (p05–p95 0.017–0.085). A raised cosine of width W spreads it to about 0.024/W per 250 m, and a window
   that ends at the 9.9 km base of the CVM data cannot be wide enough. So the jump Δ of each column is spread
   instead: CVM + WΔ above 9.9 km, CRESCENT − (1 − W)Δ below, W over 8–16 km (`fusion.regional_blend_m`,
   `m1_placeholder`). Each model is used only where it has data. Target partly met: 0.012 → 0.0037, still about
   three times the deep reference. A wider window would smooth more but shifts CRESCENT further.
2. **L2/L3: done, cause found first.** The levels agree: across −6 km the median change of ln Vs is +0.0046
   against +0.0040 predicted by L2's own gradient (residual 0.0005; 0.0000 in `vs_geology`). The step came from
   `export.grids.uniform`, which clamped each level to its own centres and put the change over the 625 m between
   them into one cell; it now interpolates across the gap. The stored model is unchanged by this fix; the eikonal
   grids (nearest cell per level) were not affected.
3. **Walls below the critical zone: done.** The lateral cutoff starts at 750 m (`lambda_h_start_m`,
   `m1_placeholder`) just below the 150 m base and grows to 2 km. With the old calibration, no cell above 175
   m changed (array comparison); the recalibration then changes all rock cells. p99 of `lateral_150_1000m`
   0.199 → 0.109. Contacts remain visible in Figures 16 and 17; the −9 km band of Figure 17 is gone.
4. **Rename: done.** `rainier_volcanics`, "Rainier volcanics", code 6. The archived calibration files v1 and v2
   keep the old name.

**Calibration changed.** V₀ ×1.44 → ×1.32, P* ×1.42 → ×0.56 (ln −0.58 ± 0.12; it moved from +0.24 to −0.58
over the iterates, with the regional Vp factor at 2 km rising from 1.016 to 1.066), rock Vs ×0.951 → ×0.960.
Held-out RMS 0.093 s (P) and 0.188 s (S), as before. S37 kept three steps (two before); held-out RMS
0.0908 → 0.0722 s (P), 0.1800 → 0.1204 s (S).

**Notebook.** `examples/pykonal_tutorial.ipynb` run on the old and new `model.zarr`: in the old model the long
rays run flat along about −9.5 km; in the new one they curve smoothly. The bend near −5 km close to the source
is in both (geology).

**Clean-machine fixes found on the way** (the laptop always had the stores these stages expected):
S22 read `geomodel.zarr` while S3 reads S22's output (now reads the S1 surface); S21 needed `model_nocal.zarr`,
which no family built (new `nocal` task); the PNSN 1D and uncalibrated rows of the model table are rebuilt by
`s14-1d` and `s14-nocal`; S18 and S10 read S8's event catalogue (S8 now first in `applications`); S34 read
S29's storm before S29 ran (reordered).

**Still open.**
- Machine-local inputs not on the server: the canopy layers of S19 (`~/Downloads/MtRainier_gridded_products*`;
  S10 now keeps the committed canopy figure) and the retired calibration snapshots `model_vscal_20260924.zarr`,
  `model_joint_s13.zarr` with their S14 runs (Figure 10 (b) and `relocation_qc.csv` now leave them out).
  Copying them from the laptop restores both; staging the canopy files into `data/raw/` closes review item R4.
- `gh` is not logged in on the server (`gh auth login`), so PR #43's description was not read or updated.
- The paper environment warns that pandoc-crossref was compiled for pandoc 3.11 and runs under 3.9.
- Products release `products-v1.1.0` (S20) not built or published: Marine decides.
- Claims to look at, from the text update:
  - S13's smoothing weight λs is now 0.01, at the edge of its scan, with a negligible score difference from 0.1.
  - The critical-zone base mismatch grew to 2.3% (p90 6.0%; was 0.5%): 1.6% from the smaller P*, the rest from
    the lateral filter that now starts just below the columns.
  - One S26 event sits 7 m above the ground in rainier3d; "no event above ground" no longer holds.
  - Vp/Vs at 4–8 km is 0.07 below iMUSH (was 0.05), which sharpens review item S-DI.6.
  - The "1–30 microstrain" load shear is not reproduced by `numbers.json` (p5–p95 0.98–13.7) and was left as is.

## Follow-up rebuild (27 October 2026)

**Review of the 21 October run.** Three findings, all fixed before the rebuild:
- A step at the base of the critical zone: the lateral cutoff of 750 m started in the first cell below the
  unsmoothed columns, so they met smoothed rock next to every unit boundary (base continuity median 2.3%, p90
  6.0%). The cutoff now ramps from zero at the base to 750 m 150 m deeper (`lambda_h_ramp: 6` in
  `configs/domain.yaml`).
- The CVM-to-CRESCENT measure was biased: the largest step per column over 6–16.5 km was compared with the same
  statistic over a window half as long. It is now measured on all steps 8–16 km below the ground, without the pair
  across a level boundary, against all steps 16.5–20.5 km (percentiles); the largest step per column is kept
  without a reference.
- The air mask in the gap between levels: fixed, no effect on the numbers.

**Rebuild.** Linux server, 06:12–10:21, the six families model, calibrate, validate, tomography, applications and
deliver from the cached inputs. Log: `outputs/logs/rebuild_20261027.log`. `pixi run test`: 155 passed; no
tolerance changed.

**Calibration changed.** V₀ ×1.32 → ×1.45, P* ×0.56 → ×1.36 (ln +0.305 ± 0.146; over the iterates after the
first it ranged from −0.29 to +0.31 and was still rising, together with ln V₀), rock Vs ×0.960 → ×0.958. The
Miocene plutons are at the cap of 0.98 V∞ again. Held-out RMS 0.093 s (P) and 0.188 s (S), as before. S37 kept
three steps; held-out RMS 0.0904 → 0.0722 s (P), 0.1802 → 0.1206 s (S).

**Roughness after** (`model.roughness` in `outputs/paper/numbers.json`; median, p95, p99):

| \|Δ ln Vs\| between neighbouring 250 m cells | after |
|---|---|
| L2/L3 level boundary, −6 km | 0.0030, 0.0043 |
| CVM v1.7 to CRESCENT, all steps 8–16 km below the ground | 0.0013, 0.0034, 0.0054 |
| same, largest step per column | 0.0032, 0.0057 |
| reference: all steps 16.5–20.5 km below the ground (CRESCENT only) | 0.0007, 0.0017, 0.0021 |
| ordinary vertical step, 7–9 km below the ground | 0.0028, 0.0038 |
| lateral, 150–1000 m below the ground | 0.0032, 0.043, 0.115 |
| lateral, 1000–2000 m below the ground | 0.0032, 0.014, 0.024 |

**Still open, re-evaluated.**
- Machine-local inputs: still missing on the server. The log reports the canopy figure not remade (S19 layers
  missing) and `model_vscal_20260924.zarr` and `model_joint_s13.zarr` left out of the calibration figure.
- `gh` login: fixed (fine-grained token for Denolle-Lab with Contents and Pull requests read and write); the
  branch is pushed and the follow-up PR is #46 (#43 was merged before these commits).
- pandoc-crossref: the warning (compiled for 3.11, run under 3.9.0.2) is still printed.
- Products release `products-v1.1.0`: not built or published.
- Claims from the text update:
  - λs of S13 is still 0.01, the smallest value of the scan (score 0.713 against 0.714 at 0.1). The paper now
    says the score does not resolve the weight below 0.1. Open: widen the scan or fix the weight.
  - Critical-zone base mismatch: closed. Median 0.48%, p90 1.5% (`cz.base_continuity`); the explanation from
    the smaller P* is gone from the paper.
  - S26: two events end above the ground in rainier3d, by 7 m (uw62188477, grade B) and 27 m (uw61989406, grade
    A), on the flanks at 2.5–2.6 km elevation. NonLinLoc's mask and the measure read the same 100 m surface
    grid but interpolate it differently; the ground varies by 65 and 94 m within 100 m of the two epicentres,
    more than the excess. The paper says so.
  - Vp/Vs at 4–8 km: 1.69 against 1.76 in iMUSH, 0.06–0.07 below. Still sharpens review item S-DI.6.
  - Load shear: closed. The paper now gives 1–14 microstrain (p5–p95 0.99–13.6, median 3.7) from `numbers.json`.
