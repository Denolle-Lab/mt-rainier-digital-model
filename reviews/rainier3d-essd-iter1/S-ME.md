# [S-ME] METHODS — iteration 1 (full first review)

Manuscript: `docs/paper/rainier3d_paper.md` on `main` @ d61305c (1313 lines). Calibration: ESSD row of
`profiles/denolle-rainier3d.md`. Sections reviewed: lines 73–1200 (Domain through Accessing the model).
Verification key: **[code]** checked against the source file named; **[output]** checked against a committed or
built output file on disk (not rerun); **[arith]** recomputed by hand from numbers in the paper; **[paper]** read
from the manuscript only. Nothing was rerun.

Six-question coverage: who[Y] what[Y] when[Y] where[Y] how[Y] why[partial]
- why is partial: the choice of method is argued well for the fusion and calibration (lines 591, 698–701), but
  many rock-physics and critical-zone choices are stated with no reason or alternative (fixed ρ_b = 2500 kg m⁻³,
  Hill blending, travel-time upscaling, soft-sand above φ_c, the f factors).

Software/version inventory: **partial**
| Tool | Where named | Version given |
|---|---|---|
| pixi lock (all Python deps) | l.111 | lock file only, no versions in text |
| pykonal | l.620–621 | 0.4.1 |
| fteikpy | l.621 | no |
| NonLinLoc (Grid2Time, NLLoc) | l.1153–1158 | no |
| py3dep | l.122, 234 | no |
| xarray / zarr (v3) | l.89, 1107 | zarr format v3 only |
| scipy (gaussian_filter, used by the fusion) | not named | no |
| SNAP biophysical processor (Sentinel-2 LAI) | l.310 | no |
| MIDAS (re-implemented in `rainier3d.geodesy.velocity`) | l.772 | n/a; re-implementation not validated against UNR MIDAS in text |
| QGIS (lidar 10 m grids) | l.321 | no |
| Claude Code / Claude Opus 5.5 | l.198 | model named |

Uncertainty treatment for key quantities: **partial** (see S-ME.5).

---

## Checklist

- **S-ME.1 Study design up front: PASS** (l.73–94, [@fig:workflow]). The S1–S5 chain, calibration loop and
  products are laid out before the methods. P6 can follow it.
- **S-ME.2 Equations and units: PARTIAL.** Most equations verified correct [code]; four defects below
  (S-ME.11, S-ME.12, S-ME.13, S-ME.17).
- **S-ME.3 Choices justified: PARTIAL.** Fusion, calibration parameterisation and the Fan versus Ma water table are
  argued; rock-physics and CZ choices mostly are not (S-ME.16, S-ME.18).
- **S-ME.4 Method appropriate: PASS** for a data description, with the held-out caveat of S-ME.10.
- **S-ME.5 Uncertainty: FAIL for the gridded products.** See S-ME.14.
- **S-ME.6 Assumptions explicit: PARTIAL.** The strain section (l.893–958) is a model of how to do this. The
  effective-stress and CZ assumptions are not (S-ME.15, S-ME.16).
- **S-ME.7 Data provenance: PASS** ([@tbl:raw], registry). Minor gaps: S-ME.22.
- **S-ME.8 Processing chain: PASS** with hand-offs to S-RP below.
- **S-ME.9 Software versions: PARTIAL** (table above).
- **S-ME.10 Plain and concise: PASS** overall; [@sec:calibration] is dense but complete.

---

## Numbered findings

Severity: **M** major (affects correctness or ESSD acceptance), **m** minor, **t** trivial/clarity.

### Correctness of equations and their implementation (C3)

**S-ME.11 (m) Gaussian filter is half amplitude, not half power. l.593; [code] `src/rainier3d/fusion/blend.py`
l.5, l.22.** σ = √(2 ln 2) λ_c / 2π gives a transfer exp(−σ²k²/2) = 0.5 at k = 2π/λ_c, i.e. half amplitude
(quarter power). Half power would need σ = √(ln 2) λ_c / 2π. The code and the paper agree with each other; only
the description is wrong. Fix the words ("half amplitude"), not the code, since the invariant and calibration were
run with this σ. The same wording is in the module docstring.

**S-ME.12 (m) "Floored at Vp/1.6" is a ceiling on Vs. l.589; [code] `src/rainier3d/fusion/build.py` l.42–44:
`vs = np.minimum(vs, vp / 1.6)`.** The operation caps Vs so that Vp/Vs ≥ 1.6. Write "Vs is capped at Vp/1.6 (Vp/Vs
at least 1.6)". Also say it applies to the corrected regional model only; the fused cells can still go below 1.633
(the 11,738 cells of l.369) because the geology side is not bounded.

**S-ME.13 (m) Notation clash in the Brie fluid modulus. l.420.** $K_f = (K_w - K_a)S^{e} + K_a$ uses S (undefined)
with an exponent e, next to $S_e$ (effective saturation) of [@eq:vg]. In the code [code: `cz/medium.py`,
`S = (θ_r + (θ_s − θ_r) S_e)/θ_s`] S is water saturation, not S_e. Define S, and rename the Brie exponent (e.g.
$e_B$) so a reader does not read $S^e$ as $S_e$.

**S-ME.15 (M) "One effective stress" is only partly true in the code. l.357, 361, 407, 440; [code]
`properties/assign.py` `effective_pressure_mpa`, `cz/medium.py` `profile`, `cz/level.py` l.76, l.84;
`configs/perturbations.yaml` `pressure`.** The pore pressure is shared: both laws use hydrostatic pressure below
the same Fan et al. (2017) water table, placed at the bed under ice. The total stress is not:
- L1–L3 cells use [@eq:crack] with a constant ρ_b = 2500 kg m⁻³ from the ice surface down, so glacier ice is
  loaded at 2500, not 917 kg m⁻³ (about 1.55 MPa too much under 100 m of ice), and no unit density enters.
- The CZ columns integrate the actual column density (ice at 917 kg m⁻³ via `overburden_pa`, then granular and
  rock-law densities) and add suction stress weighted by W.
So l.440 ("from the same overburden (glacier ice included)") is not what the L1–L3 cells do. The 0.3% median Vs
continuity at 150 m (l.442) shows the mismatch is small at the column base. It is larger in L1 cells under thick
ice. Either evaluate [@eq:crack] with the column overburden, or state the two total-stress rules and bound the
difference. P2 and P3 will both look for this, since the paper sells "one effective stress" as a design feature.
Also state the implicit Biot coefficient of 1 and that ρ_b is an `m1_placeholder` (it is unsourced in
`configs/perturbations.yaml`, which has no `source_key` in the `pressure` block).

**S-ME.17 (M) Stale text in Geohydrology contradicts the model. l.991, l.1008–1014 vs l.393–443.** Line 1009 says
"at present the crack-closure law assumes hydrostatic pore pressure everywhere (water density 1000 kg m⁻³)" and
line 1014 says "None of these couplings is applied in the model". Both describe the old M1 rule (the
`water_table is None` branch of `effective_pressure_mpa` [code]). The published model applies a water table to the
crack-closure pressure and Gassmann fluid substitution in the CZ columns ([@sec:granular], [@sec:cz]). Rewrite the
"How the layers can enter the seismic model" list as what is applied (water table, Gassmann–Brie in the columns)
and what is not (valley fill, hydrothermal core, loading). P4 reads this section first and will get the wrong
answer.

**S-ME.16 (m) Soft-sand model above the critical porosity is unstated. l.409–417; [code] `cz/rockphysics.py`
`soft_sand`.** For φ ≥ φ_c = 0.40 the code returns Hertz–Mindlin evaluated at φ_c, while Gassmann then uses the real
φ_g. Soil porosity in the box has a median of 0.63–0.65 ([@tbl:soil], l.285, 298), so most soil cells sit in the
branch the paper does not describe. State the rule and its consequence (the dry frame does not soften above 0.40).
Related assumptions to state: suction stress is weighted by W, so rock (W = 0) gets none (l.403, correct in code);
the subglacial water table at the bed (zero pore pressure at the bed) ignores subglacial water pressure near
flotation.

**S-ME.18 (m) Under-ice column rule differs from [@tbl:czlayers]. l.464, 478; [code] `cz/medium.py`
`boundaries`, `profile`.** With f = 0 the table formula gives $z_3 = z_2 + 2$ m, i.e. 2 m of weathered rock under
ice. The code sets z1 = z2 = z3 = 0 and forces W = 0 throughout the column, so under ice the column is the fresh rock
law, not a fractured zone grading to it. Line 478 and the [@fig:czsection] caption say "fractured rock"; with W = 0
it is unweathered rock law at that effective stress. Add the under-ice rule to the table.

**S-ME.19 (t) Equations verified correct [code + arith].** No action; recorded so the next iteration does not
redo them.
| Equation | Check |
|---|---|
| Brocher Vs(Vp), Nafe–Drake ρ(Vp), Brocher Vp(Vs) (l.368, 587) | coefficients match `petro/relations.py` and Brocher (2005) |
| [@eq:crack] | matches `crack_closure` and `effective_pressure_mpa` (except S-ME.15) |
| Q_P = 2Q_S gives negative bulk Q below Vp/Vs = √(8/3) (l.369) | [arith] correct |
| [@eq:hm] | matches `hertz_mindlin` |
| [@eq:gassmann], Brie, Hill | match `cz/rockphysics.py` |
| [@eq:alteration] | half and tenth of fresh resistivity [arith] correct; 0.3 matches `units.yaml` `start_decades` |
| [@eq:gn] | correct normal-equation step for r(θ+δ) ≈ r − Gδ with prior/regularisation L [arith] |
| Prior factors e^0.3, e^0.7, e^0.1 = 1.35, 2.0, 1.1 (l.642) | [arith] |
| Multipliers e^0.385, e^0.583, e^−0.039 (tbl:multipliers) | match `configs/velocity_calibration.yaml` |
| Magma Vp/Vs +6%, alteration Vp/Vs +8% (l.371–372) | [arith] |
| Plane-stress ε_zz, uniaxial cone stress, compliance, Boussinesq (l.902, 919–926) | standard forms, signs tension-positive consistent |
| Load 2.34 × 10¹⁵ N ↔ 95 km³ at 2500 kg m⁻³ (l.813) | [arith] |
| Grid sizes in [@tbl:grids] | [arith] consistent with spacings and bounds |

### Calibration and validation (C3; P2 lens)

**S-ME.10 (M) The published model's "held-out" score is not held out. l.29 (abstract), l.53, l.658, l.667, l.707;
[code] `scripts/13_joint_calibration.py` l.261–262; [output] `outputs/joint_calibration_cz/history.json`.** After
four iterations on the fitting half, two more run on all 88 events (`run(th_fit, set(order), ...)`). The published
multipliers and regional correction (θ = 0.385, 0.583, −0.039) come from that all-events run, so the 44 "held-out"
events of l.707 and of the abstract (0.092 / 0.187 s) were in the fit of the published model. In addition, λ_s
was chosen on the held-out half (l.656), which makes it a validation set, not a test set. The honest independent
score is iteration 4 of the fitting half (0.092 P, 0.186 S held out; history.json), and the paper does report it.
The effect is small (held-out S 0.1862 at iteration 4 against 0.1866 after the all-events run), which is good news,
but the text must say it. Options: (a) publish the fitting-half model and its held-out score; (b) keep the
all-events model and report the iteration-4 held-out score as the out-of-sample number, stating that the final two
iterations include those events and changed the held-out RMS by < 1 ms; (c) add a k-fold or a second random split.
P2 will ask exactly this, plus whether the gain survives a different split (events alternate in time; a split by
region or by depth would test the regional correction harder).

**S-ME.20 (m) Posterior scaling uses an uncorrected reduced χ². l.658; [code] `scripts/13_joint_calibration.py`
l.265.** χ² is computed as RMS²/σ² over all picks, with no degrees-of-freedom correction for the 4 × 88 = 352
hypocentre parameters and 15 velocity parameters out of 3103 picks (about 12% fewer degrees of freedom), and with
the unweighted RMS although the fit is Huber-weighted. Since χ² = 0.568 < 1, the scaling shrinks the posterior
s.d. (σ_P and σ_S are PNSN location residuals, l.618, which already include model error). State this, or report
unscaled s.d. alongside. The ±0.03 on V₀ (l.673) is consistent with ln s.d. 0.020 × 1.47 [arith].

**S-ME.21 (m) Fusion invariant table is stale. l.52, 115, 610, 701; [output] `outputs/fusion_report.csv`
(written 3 October 2026 11:00, same time as `data/processed/model.zarr`).**
| Quantity | [@tbl:invariant] | fusion_report.csv |
|---|---|---|
| L1 Vs low-pass RMS | 0.012 | 0.0132 |
| L1 mean ln(V/V_reg), Vp / Vs | +0.046 / +0.077 | +0.068 / +0.095 |
| L2 mean, Vp / Vs | +0.000 / +0.001 | +0.0012 / +0.0020 |
| L3 mean, Vp / Vs | 0.0002 / 0.0001 | 0.0002 / 0.00001 |
Lines 52, 115 and 701 already say 0.013, and l.750 quotes +0.068 / +0.095 from the same file, so only the table is
behind. Regenerate it from the CSV; if the "below 1 km" mean is meant, add that column to `fusion_report.csv` so
the number has a file.

**S-ME.23 (m) Top-300 m numbers disagree. l.677 and l.750 ("23% faster in Vp and 31% in Vs", mean ln 0.21 and
0.27) against l.1212 ("21% faster in Vp and 30% faster in Vs").** exp(0.21) = 1.23, exp(0.27) = 1.31 [arith], so
Limitations quotes ln values as percentages (and 0.27 as 30%). Use one convention.

**S-ME.24 (m) Calibration ray kernel. l.654.** The 20% underestimate of the ray derivative is honestly described.
One clarification: residuals use the full forward problem, so the fit is not biased, but the regional posterior
s.d. of [@tbl:bias] (0.003–0.016) are computed with the too-small kernel and are therefore too small by a similar
factor. Say so in the [@tbl:bias] caption.

**S-ME.22 (t) Event count. l.132 ("91 calibration events") vs l.618 (88).** `configs/validation_events.csv` lists 91
events [output]. State that 3 fail the six-pick / four-P rule, or which they are.

### Uncertainty of the derived layers (C2; P1 lens)

**S-ME.14 (M) Most gridded products carry no uncertainty. ESSD requirement.** P1 checks that each derived layer
states its uncertainty. Status:
| Product | Uncertainty in paper | Note |
|---|---|---|
| Vp, Vs, ρ, Q (`model.zarr`) | none per cell; only `vs_unc_regional` from CRESCENT below 9.9 km (l.587) | calibration posteriors exist (tbl:multipliers, tbl:bias) but are not propagated to cells |
| Alteration intensity | none | thresholds are placeholders; at least give a sensitivity to the 0.3 / 0.7 decades |
| CZ columns (Vs, saturation, σ′) | none | all parameters `m1_placeholder` (l.425, 474–477) |
| GNSS strain-rate grid | dilatation ± only for the regional fits (tbl:strain) | `strain_grid.nc` has `dilatation_sigma` [code: `geodesy/strain.py` l.84–102] but the paper does not mention it; no shear or azimuth uncertainty |
| Strain at depth | "least certain part" (l.958), no number | P3 asks how uncertainty grows with depth |
| Edifice-load stress | none | sensitivity to ν and ρ is linear/simple, could be stated in one sentence |
| Glacier thickness | IceBoost error grids are cached (l.124) but not carried | |
| Water table | well comparison (tbl:wells) | good |
| Relocated catalogue | per-event NLL uncertainty (tbl:relocation) | good |
Minimum fix for ESSD: a table "uncertainty by product" with either a carried field, a stated sensitivity, or
"not quantified" plus the reason. One cheap, defensible addition for Vp/Vs: a per-cell envelope from the posterior
s.d. of the three multipliers and the regional knots, run through the forward problem at ±1 s.d.

### Sourcing and placeholders (C2)

**S-ME.25 (m) Placeholders: sourced keys exist, a few values are missing from the Limitations list.** l.1205
lists the placeholders in petrophysics, perturbations, units and gnss. Not listed: `configs/cz.yaml` (every value is
an author choice per its header; l.425 and l.476 say so in the text), `configs/terrain.yaml` radii (l.334), ρ_b and
ρ_w of `perturbations.yaml` `pressure` (no `source_key` at all [code]), the 10 m default water table where the Fan
grid is NaN (`cz/level.py` l.78, `nan=10.0`, unstated in the paper), and the Huber threshold, damping and knot
positions of the calibration. Add them to l.1205 or to one placeholder table.

**S-ME.26 (m) Deposit thickness rule misread for a stated minimum. l.543, [@tbl:dmuthick] row Qvl(e); [code]
`configs/units.yaml` `symbol_thickness_m`.** The rule takes "the midpoint of the stated range, from zero when only a
maximum is given". For the Electron Mudflow the description gives a minimum ("at least 26 ft"), and the config
treats it as a maximum ([0, 7.9] m, midpoint 4.0 m). A lower bound of 7.9 m means 4.0 m understates the deposit. Fix
the rule (e.g. use the stated minimum) or flag it as an exception.

**S-ME.27 (m) The Q rule has a citable source.** l.369 TODO: `configs/perturbations.yaml` already calls it an
"Olsen-style rule": Q_S = 50 V_S (km s⁻¹) and Q_P = 2 Q_S is the rule of Olsen, Day and Bradley (2003, BSSA). Cite
it and keep `m1_placeholder` for its use at Rainier. [code comment; reference not checked in the registry]

### [TODO] markers in the methods sections

Twelve between l.73 and l.1200; one more in Limitations (l.1214). None may survive submission.
| Line | Content | Suggested owner |
|---|---|---|
| 155 | PNSN 1D model identity (P3 or C3) | ask PNSN; the S6 check and both relocation comparisons depend on it |
| 221 | Deposit of the AI session transcripts | author decision |
| 267 | Command that gives NDVI 0.46 without offset correction | rerun S2 with the correction off and log it |
| 369 | Source for the Q rule | see S-ME.27 |
| 370 | Published range per unit of [@tbl:units] | one column in `petrophysics.csv` |
| 557 | Moran (1999) depth reference (bsl or below summit) | check the paper; shifts the body by ~4.4 km if wrong |
| 801, 802 | Daily-strain MAD 20 / 106 not reproduced; files give 23 / 133 | replace with file values and add the statistic to S18 |
| 806 | "up to 1500 nanostrain" vs 2335 in the 30-day median | state period and statistic |
| 1030 | No trigger field in `events.csv` | drop the item or add the field (date-based storm flag is easy) |
| 1092 | products-v1.1.0 sizes | after release |
| 1158 | Podvin and Lecomte (1991) citation | add to registry |

### Other methods points

**S-ME.28 (m) Tectonic strain at depth cites the wrong field. l.836–837; [code] `scripts/25_strain_volume.py`
l.6, l.64; `geodesy/volume.py` `horizontal_rate_at`.** The text says "the horizontal tensor of [@tbl:strain] is
carried down". S25 carries the 5 km strain grid (`strain_grid.nc`), whose smoothing scale is 30–60 km inside the box
(l.780), not the regional uniform fits of [@tbl:strain]. That is why the WRSZ maximum shear is 10.4 nanostrain yr⁻¹
in [@tbl:wrsz] and 11.1 in [@tbl:strain]. Refer to the grid, and state that a 30 km smoothing scale is wider than
the WRSZ polygon (about 17 × 44 km), so the "almost optimal loading" of l.854 is a regional statement, not a
fault-scale one. P3 lens.

**S-ME.29 (m) Upscaling by travel-time average. l.489–497.** The slowness average is right for vertical travel
time but not for Vs of a horizontally layered cell seen by surface waves or for the effective moduli (Backus). It is
the documented cause of Vp/Vs > 3 in 8,947 top-cells. Say why it was chosen (the calibration uses travel times) and
that waveform users at > 1 Hz should use the `/cz` node, not the L1 cell. P2 asks about waveform fitness at the
stated grid spacing.

**S-ME.30 (t) Residual notation. l.638–639.** $t_{ij}$ and $T_j$ need a phase index (T depends on P or S); the
sentence "the pick of phase at station j" is missing a word.

**S-ME.31 (t) Intro versus abstract held-out S RMS. l.29 (0.187, S14 in published model) vs l.53 (0.186, S13
iteration 4).** Both are right for different runs; pick one for the abstract and introduction and name it. Relates
to S-ME.10.

**S-ME.32 (t) Reproduction default. [code] `pixi.toml` l.71 `s13` runs the script with the default
`--iterations 3`; the paper (l.658) and `docs/joint_calibration.md` l.302 use 4.** `pixi run s13` therefore does not
reproduce the published calibration. Hand-off to S-RP.

---

## Domain flags

- Inversion: regularisation stated and λ_s chosen by held-out score (good); no resolution or checkerboard test for
  the 12 regional knots; trade-off of P* with the 2 km knot is stated (l.674) but no correlation matrix is given.
- Held-out set reused for model selection and for the final fit (S-ME.10).
- Pick uncertainties are location-residual RMS, not pick errors; they mix model and pick error (l.618).
- Velocity model named and justified (CVM 1.7, CRESCENT Gen0); the reference 1D model is not identified (l.155).
- Location: NLL settings given in full (l.1155–1159); NLL version missing.
- Catalog completeness: calibration selection M ≥ 2 with pick thresholds stated; relocated catalogue M ≥ 1 stated.
- Fusion filter wording (S-ME.11).

## Tier feed

- **C2 (data quality, primary):** S-ME.14 (M, uncertainty by product), S-ME.17 (M, stale hydrology text), S-ME.21,
  S-ME.23, S-ME.25, S-ME.26, twelve TODOs.
- **C3 (method correctness):** S-ME.10 (M, held-out not independent), S-ME.15 (M, one effective stress only
  partly), S-ME.11, S-ME.12, S-ME.16, S-ME.18, S-ME.20, S-ME.24, S-ME.28, S-ME.29.

## Top fixes (ordered)

1. **S-ME.10:** state that the published model is fitted on all 88 events, report the iteration-4 held-out score
   as the out-of-sample number in abstract, introduction and validation, and add one alternative split.
2. **S-ME.14:** add an uncertainty-by-product table; propagate the calibration posteriors to a Vp/Vs envelope;
   mention `dilatation_sigma` of the strain grid.
3. **S-ME.15 + S-ME.17:** make the effective-stress claim match the code (ice density and unit density in
   [@eq:crack], or state the difference), and rewrite l.1008–1014 to say what the model now applies.
4. **TODOs and stale numbers:** S-ME.21 table, S-ME.23 percentages, l.801–806 strain statistics, l.557 Moran depth
   reference, l.155 PNSN 1D identity.

## Hand-off to S-RP

- `pixi run s13` default `--iterations 3` against the 4 used for the published calibration (S-ME.32).
- Daily strain MAD and edifice excursion numbers (l.801–806): "no script computes it".
- NonLinLoc cross-check at OBSR (l.623) "has not been rerun".
- NDVI 0.46 (l.267) has no command.
- `configs/validation_events.csv` has 91 rows, 88 used: the selection filter should be reproducible from code.
- Software versions beyond pykonal: NonLinLoc, fteikpy, SNAP, QGIS.
- Four inputs read from local or delivered copies (l.152–156): CVM 1.7 captcha, CRESCENT, PNSN 1D, canopy products.
