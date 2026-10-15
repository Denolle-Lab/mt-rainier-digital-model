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
