# rainier3d derived products, products-v1.1.0 (draft release notes)

Draft for the release made by S20. Marine Denolle decides when it goes out. After the upload:

```bash
pixi run s20 --tag products-v1.1.0 --upload
gh release edit products-v1.1.0 --prerelease --notes-file reviews/products-v1.1.0-release-notes.md
```

Then commit the updated `src/rainier3d/products.json`, rerun `examples/pykonal_tutorial.ipynb` (it downloads the
`model` product) and commit its outputs. Delete this header (down to the line) from the release text.

---

**For testing.** The velocity model of Mount Rainier rebuilt on 27 October 2026 (PR #46), released for
seismologists to try in location, travel-time and waveform work before a v2 release. Please report what you find in
an issue.

Download with `rainier3d fetch <product>` or `rainier3d.api.fetch`. Checksums: `SHA256SUMS` and
`src/rainier3d/products.json`. How to use each product: `docs/products.md`, `docs/velocity_model.md` and the tutorial
notebook `examples/pykonal_tutorial.ipynb`. Licence and attribution: `docs/data_policy.md` (CC-BY 4.0 for the derived
products).

## Products

| Product | What changed since v1.0.0 |
|---|---|
| `model` (zarr) | Rebuilt: see below. |
| `model_let` (zarr) | New: `model` after the local-earthquake tomography (S37), with its ln V update and node grid. |
| `grids` | Rebuilt from `model`: uniform 500 m netCDF, EMC-style netCDF, NonLinLoc P and S grids. |
| `strain_3d`, `edifice_load` | Rebuilt with the new model. |
| `alteration`, `mass_movements` | Repackaged; this rebuild did not change their method. |

## What changed in the model

- **No artificial interfaces.**
  - The jump from the Cascadia model (CVM v1.7) to CRESCENT at 9.9 km below the ground (median 6% in Vs) is
    spread over 8–16 km. Before, it was a switch, along which long rays ran flat at about −9.5 km.
  - The uniform grids interpolate across the gap between levels, so the step at −6 km is gone.
  - Map units extended to depth are smoothed laterally below the critical zone. The cutoff grows from zero at the
    150 m base of the critical zone to 2 km.
  - Steps of ln Vs between neighbouring 250 m cells (99th percentile): CVM to CRESCENT 0.017 → 0.0054 (deep
    reference 0.0021); lateral, 150–1000 m below the ground, 0.199 → 0.115.
- **Recalibrated.** Rock-law multipliers V₀ ×1.45, P* ×1.36 and Vs ×0.958, with a static correction of the
  regional model, fitted to PNSN P and S arrivals with 3D relocation (S13).
- **Critical zone.** It joins the rock below within a median 0.5% in Vs.
- **Unit 6** is now `rainier_volcanics` ("Rainier volcanics"), with the same code and parameters.

## How well it fits

- **88 PNSN events relocated in each model (S14):**

  | Model | P RMS (s) | S RMS (s) |
  |---|---|---|
  | PNSN 1D | 0.132 | 0.268 |
  | `model` | 0.093 | 0.191 |

  On the held-out half of the calibration, the RMS is 0.093 s (P) and 0.188 s (S).
- **2023–2025 PNSN catalogue (S26), 1D against 3D:** median RMS 0.119 → 0.106 s with the same picks and locator.
- **`model_let`:** held-out RMS 0.090 → 0.072 s (P) and 0.180 → 0.121 s (S), on events held out by 10 km blocks.

## Known limits

- **Resolution:** this is the coarse `m1` profile. L1 cells are 250 m × 50 m (surface to sea level), L2 500 m × 250 m
  (to −6 km) and L3 1 km (to −20 km).
- **Placeholder parameters:** many are still `m1_placeholder` in `configs/` (for example the smoothing cutoffs and
  the blend window), and their replacement is tracked work.
- **Vp/Vs:** at 4–8 km below the ground beneath Rainier (north of 46.75° N), it is 0.06–0.07 below the iMUSH
  tomography (Ulberg et al. 2020).
- **Calibration:** the smoothing weight of S13 sits at the edge of its scan (0.01), and P* is not resolved by the
  arrivals.
- **Quality factors** follow a rule from Vs, not attenuation data.
- **Locations:** two relocated events (S26) end 7 m and 27 m above the ground on steep flanks, within the relief of
  the 100 m surface grid.
- **Near-surface use:** the top 300 m are the geology model alone. The regional models do not resolve them, and the
  arrivals barely constrain them.

## Reproduce

Commit: the merge of PR #46. Run the families `model` to `deliver` (`docs/running_remotely.md`) from the cached
inputs, then `pixi run s20 --tag products-v1.1.0` and compare the archives with `SHA256SUMS`.
