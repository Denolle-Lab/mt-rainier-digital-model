# [S-RE] RESULTS: rainier3d (ESSD), iteration 1

Manuscript: `docs/paper/rainier3d_paper.md` at main @ d61305c (line numbers below refer to this file).
Results scope for this data paper: sections 4 to 9 (surface layers through mass movements), plus the relocated catalogue (section 10.2, `sec:relocation`), which is a result even though it sits under "Accessing the model".

**How numbers were checked.** "File" means I compared the number with a run record in `outputs/` or `configs/` on disk (read only, nothing rerun). "Text" means I compared it only with other places in the manuscript. Files on disk carry their own dates (for example `outputs/mass_movements/` is from 5 October 2026, `outputs/terrain/` from 26 September 2026), so a mismatch can also mean that the record on disk is newer than the text.

```
[S-RE] RESULTS
Figure/table citation order: FAIL. fig:mass is cited at l.239 but placed as figure 24 (l.1053); fig:strain is cited (l.793) before fig:strainseries (l.797) but placed after it; tbl:mass is cited (l.1018) before tbl:mass-counts (l.1033) but placed after it. Never cited in the text: fig:residuals, fig:imush, fig:relocated, fig:relshift, tbl:czlayers (also tbl:outline, tbl:ai, tbl:datasets, which is acceptable for front and back matter).
Interpretation-in-results count: 17 (list in S-RE.4)
External-comparison-in-results count: 5 (list in S-RE.5)
Quantitative reporting (n, stats, uncertainty): PARTIAL. Counts and sources are good. The validation's held-out claim is compromised, and uncertainty is missing for most derived products other than the calibration multipliers.
```

## Findings

### S-RE.1 Opening outline: PASS (l.57–71, l.357)
`tbl:outline` and the opening paragraph of the subsurface section (l.357) tell the reader what each part delivers. The one gap: the outline does not list the relocated catalogue as a product, because it is hidden inside `sec:access` (see S-RE.2).

### S-RE.2 Order of presentation: PARTIAL
1. **The relocated catalogue sits in the wrong section (l.1151–1188).** It has its own abstract paragraph (l.31) and a conclusions bullet (l.1235), and it is a validation result for the 3D model. It is filed under "Accessing the model", between the export formats and the viewer. Move it to a subsection after `sec:validation` (or to its own section after `sec:fused`). **P2** reads Calibration, Validation and then expects the catalogue; **P6** reads Access and meets 40 lines of NonLinLoc settings.
2. **The terrain–catalogue comparison comes before the catalogue it uses (l.338–353).** `tbl:terrain-mass` samples "the 1,650 event points of the mass-movement catalogue (sec:mass)", which is defined 700 lines later. Move the paragraph and the table to the end of `sec:mass`. **P4** cannot judge class-by-class slope statistics before learning what "complex or unknown type" means (l.1021).
3. **Calibration results come before the calibration (l.370, l.391, l.501–506).** The ×1.47 multiplier, the held-out RMS with and without the critical zone (0.0921/0.1866 against 0.0924/0.1877 s) and the remark that "V₀ rises from 1.31 to 1.47" all appear in `sec:petro` and `sec:cz`, before `sec:calibration` defines the split, the objective and the multipliers. Keep the parameter table (`tbl:units`) with the table values. Move the calibrated numbers and the paragraph "Calibration with the critical zone" into `sec:calibration`.
4. **Validation runs from specific to general in the wrong direction (l.705–744).** The weakest test (ComCat hypocentres fixed in a 1D model, S6, l.742) comes last, after the held-out and iMUSH tests. That order is defensible, but the paragraph's last sentence draws a conclusion (S-RE.4, I14). Either place S6 first as the baseline check or move it to an appendix (S-RE.9).
5. **Methods follow the strain results (l.893–958).** `sec:strainmethod` comes after the strain-in-volume results it qualifies, and `tbl:wrsz` and the "almost optimally" sentence (l.854) are read before the reader learns that the depth extension is assigned rather than computed. Put the two-paragraph caveat (l.836–841 already starts it) next to the table.

### S-RE.3 One format per result; no duplication: PARTIAL
- **`tbl:hydro` (l.970–983) repeats numbers from `tbl:env`, `tbl:soil`, `tbl:canopy`, `sec:surface-core`, `sec:alteration` and `sec:strain`** (5.50 km³, 97.3 km², NDSI −0.48, 60,174 flowlines, 1.41 m, 19.6 m, 10.1/23 m, 10.6 of 126 km², 15 nanostrain). As a cross-walk for **P4** it is useful. Keep it, but drop the numbers and keep layer, source and section.
- **Depth to rock and water table, stated three times:** l.291, l.989 and l.1216, with the same 13.9×, 92.8%, 1.41 m and 19.6 m.
- **Annual strain amplitude, stated three times:** l.793, l.965 and l.981.
- **Column-base continuity, stated twice:** l.442 and l.493 ("median 0.3%, 90th percentile 0.8%").
- **Held-out RMS, stated four times with two values:** l.29, l.53, l.503 and l.707 (see S-RE.6, N1).
- **Top-300 m offset, stated three times with two values:** l.677, l.750 and l.1212 (see N4).

### S-RE.4 Interpretation in results: FAIL, 17 sentences
For ESSD some explanation is welcome where it tells a user how to read a layer. The ones marked **(overrun)** claim more than the data description supports, and two contradict the paper's own caveats. These are the ones to fix.

| # | Line | Sentence (abridged) | Note |
|---|---|---|---|
| I1 | 29 (abstract) | "An independent local-earthquake tomography confirms the Vs correction beneath Rainier." | **(overrun)** Independence is "less so in the north" (l.728), Vs still differs by +0.063 at 1–2 km, and Vp/Vs is 0.05 below iMUSH at 4–8 km (l.726). Suggest "agrees with". |
| I2 | 268 | NDSI deficit "consistent with debris-covered glacier tongues ... and with glacier retreat" | Untested attribution; acceptable if hedged. |
| I3 | 291 | "The two products measure different things ... trained mainly on well logs, which are sparse on volcanic edifices" | Explanation; fine for ESSD, but the claim about the training data needs a citation. |
| I4 | 319 | "That is why the lidar median (14.6 m) is lower than the GEDI median" | Fine as a reading guide. |
| I5 | 338 | "crowns lie on ridges and valley walls as often as in incised channels" | Inference from a valley-depth median; no test. |
| I6 | 673 | "The table rock is too slow near the surface, and the slower critical zone above it raises the multiplier further." | Reasonable, but it is the interpretation of a fit. |
| I7 | 699 | "That is low for crustal rock and lower still than expected beneath a volcano ...: the S−P misfit of fixed hypocentres is partly a location error." | Interpretation; no citation for "expected". |
| I8 | 707 | "so the fit does not overfit" | **(overrun)** The published model's last two iterations use all 88 events (l.658). See N1. |
| I9 | 709 | "The S−P misfit therefore lies in the velocity model, not in the catalogue hypocentres." | Inference; "therefore" is too strong. "Mostly" would be defensible. |
| I10 | 727 | "The correction is therefore local to Rainier." | **(overrun)** It rests on one southern comparison inside the iMUSH array. Better: "is not supported south of 46.65° N". |
| I11 | 742 | "The 3D structure therefore explains part of what station corrections absorb." | Inference from r = 0.70/0.67; acceptable if hedged. |
| I12 | 806 | "a few millimetres of snow-related antenna error become about 1000 nanostrain" | Attribution to snow is asserted, not shown. No seasonal test against snow depth. |
| I13 | 826 | "The load stress therefore sets the orientation of stresses in the upper crust beneath the edifice." | **(overrun, self-contradiction)** l.946–947: "Without the magnitude of the tectonic background stress the two cannot be summed." The ratio at l.826 compares a stress with a strain-rate times an assumed modulus. It also mixes vertical stress at 0 m (38.5 MPa) with mean stress at −11.5 km (1.5 MPa) to make the 1.5–38.5 MPa range. |
| I14 | 854–855 | "the geodetic field loads it almost optimally for right-lateral slip"; repeated in the abstract (l.39) as "loads the WRSZ in right-lateral shear at 10 nanostrain per year" | **(overrun)** The 5 km value is the surface tensor copied down (l.836–841, "assumptions, not observations"). The abstract states it as a measurement at depth. **P3**'s first question. |
| I15 | 869–870 | "Dilatation in that volume would need a source these models do not contain, such as the pressurisation of the hydrothermal system." | Speculation; move to Limitations or a discussion paragraph. |
| I16 | 1006 | "they test the grids where people drill, not on the volcano" | Fine as a reading guide. |
| I17 | 1184 | "The problem of the 500 above-ground events therefore lies in the older part of the catalogue" | Inference from zero above-ground events in 2023–2025; plausible, but not shown. |

Also outside the table: l.1018, "Mass movements are Rainier's most frequent hazard", is an unsourced framing claim at the head of a results section.

### S-RE.5 Comparison to other studies in results: 5
| # | Line | Comparison |
|---|---|---|
| E1 | 242 | "Part of any difference reflects thinning since 1981 [@sisson2011]" |
| E2 | 496 | Vp/Vs 4.70 "within the 4 to 4.5 of saturated sediment, @pasquet_2015". Also, 4.70 is not within 4 to 4.5. |
| E3 | 513–515 | Simulated dv/v of about 2% is "the order of" the changes measured by @clements_denolle_2023, @shen_2024 and @shi_2026 |
| E4 | 579 | Alteration "agrees with" @finn_2001 and @john_2008 |
| E5 | 754 | Magma body "of the size imaged by @moran_1999 and @pang_2025" |

E4 and the GlaThiDa check (l.242) are validation and belong in a data paper; label them as such. E2 is a factual error (4.70 > 4.5). E3 compares a simulation with observations and should move to a short discussion or be cut.

### S-RE.6 Quantitative reporting and cross-section consistency: FAIL on several numbers
Each item is marked as checked against a **File** or only against the **Text**.

| # | Lines | Issue | Checked against |
|---|---|---|---|
| **N1** | 29, 53, 503, 707, 669 | **The "held-out" score of the published model is not held out.** `tbl:iterations` and l.658 state that the last two iterations run on all 88 events. `outputs/joint_calibration_cz/history.json` confirms it: run `all-events`, iterations 0–2, with the held-out S RMS moving from 0.1862 to 0.1866 s. `heldout_published.json` (0.0921/0.1866 s, rounded 0.092/0.187 in the abstract) therefore scores the 44 events with a model fitted on them. The honest held-out score is fitting-half iteration 4 (0.0920/0.1862 s), which is the "0.186" of l.53 and l.707. The practical difference is under 1 ms, but the abstract (0.187), the introduction (0.186) and the validation (both) disagree, and l.707 calls them "the 44 events not used in the fit". Fix: quote iteration 4 as the held-out score, and the published-model numbers as "after refitting on all events". | File |
| N2 | 1232 | Conclusions: "V₀ is raised by 31%". The published multiplier is ×1.4689 (`configs/velocity_calibration.yaml`); 31% is the superseded run without the critical zone. | File |
| N3 | 1235 | Conclusions: "no event lies above the ground, and the median RMS falls from 0.119 to 0.109 s". `outputs/catalog/summary.json`: `above_ground_rainier3d` = 1, RMS 0.1065 s; `tbl:relocation` and the abstract say 1 event and 0.107 s. | File |
| N4 | 1212 vs 677, 750 | Top 300 m: "21% faster in Vp and 30% faster in Vs" (Limitations) against "23% ... 31%" (body, mean ln 0.21 and 0.27). The Limitations text has put the ln values in place of the percentages. | Text |
| N5 | 1219 vs 1163, 1169 | "12 events stop at the base of the search volume" against 10 in the text and in `tbl:relocation`. | Text |
| N6 | 608–614 | **`tbl:invariant` is stale.** `outputs/fusion_report.csv`: L1 Vs RMS 0.0132 (table 0.012); L1 mean offsets +0.068/+0.095 (table +0.046/+0.077); L2 +0.001/+0.002 (table +0.000/+0.001). l.115, l.701 and l.750 quote the file correctly, so the table contradicts the text two pages later. | File |
| N7 | 1027–1029, 41, 338, 1051, 1197 | **The mass-movement catalogue on disk has 1,649 events, not 1,650.** `outputs/mass_movements/events.csv` and `summary.csv` (5 October 2026) have 323 slides (316 crowns + 7 points), 1,623 crowns, 259 volumes and 246 failure depths. The paper says 324, 1,624, 260 and 247, and cites "run of 2026-09-25". `outputs/terrain/mass_movement_terrain.csv` (26 September) still has 1,650. Either rerun S30 on the current catalogue and update every count, or pin the paper to the 25 September run and say so. | File |
| N8 | 1029 vs 1037 | Failure depth: "247 events" have `depth_m`, but "the inventory records a failure depth for every lidar-protocol deposit (453 deposits in the box)". The two statements cannot both hold, unless 206 deposits fall outside the event points (debris-flow polygons?). State which. | Text (plus File for 246) |
| N9 | 711–720, 709 | `tbl:models` caption sources each row from `outputs/relocation/<model>/stats.json`. The conduit-centred-alteration row (0.095/0.190/856/+852) has no such directory on disk. `fused_alteration` (EM-based field, without the critical zone) gives 0.093/0.190/850/+855, which matches l.703. "three in the conduit-alteration run" (l.709) cannot be traced: `fused_alteration` has 1, `fused_vscal` has 3. Other rows match the files, except the Vs-only S RMS (file 0.1895, table 0.190). Also worth reporting: the PNSN 1D relocation places 9 of 88 events more than 50 m above the ground (`pnsn1d/stats.json`), against 2 for the published model. That is the comparison **P2** wants. | File |
| N10 | 1178 | "0.38 km deeper than in the 1D model (10th–90th percentile −0.49 to +1.59 km)" and "0.6 km horizontally". `summary.json` `shift_pnsn1d_to_rainier3d`: 0.401 km deeper, p10–p90 −0.487 to +1.747 km, 0.57 km horizontal. If the text uses the 340 grade A/B subset, say so. The 1D median RMS in the same file is 0.1195 s, which rounds to 0.120, not 0.119. Again, say which subset. | File |
| N11 | 872–876 | `tbl:edificestrain` does not match `outputs/gnss/strain_3d_summary.json` (5 October 2026), in microstrain: 1500 m −829 (table −831), 500 m −521 (−518), 0 m −418 (−413), −2000 m −209 (−208), −5000 m −71 (−73). Small, but the table predates the run on disk. | File |
| N12 | 840 | "1294 epicentres", against `events` = 1292 in `strain_3d_summary.json`. | File |
| N13 | 618, 132 | "88 PNSN earthquakes ... The event list is committed (`configs/validation_events.csv`)". That file holds 91 events (92 lines), and `tbl:raw` says "the 91 calibration events". The 88 in `outputs/joint_calibration_cz/catalog.csv` are presumably those that pass the six-pick rule. State the filter. | File |
| N14 | 1088 vs 567 | Product `alteration`: "3D intensity in the top 200 m", against a depth of investigation "capped at 150 m". | Text |
| N15 | 787 vs 848 | WRSZ maximum shear 11.1 (`tbl:strain`, uniform fit) against 10.4 (`tbl:wrsz`, grid median at 5 km). The values are not wrong (`summary.json` and `strain_3d_summary.json` both match), but they are two estimators of one quantity. Label them so. | File |
| N16 | 1232 | "regional Vs beneath Rainier is 5–9% too slow at 2–7 km", against `tbl:bias` 1.045–1.081 (4.5–8.1%) and l.676 "5–8%". | File |
| N17 | 513–514 | Storm dv/v "a median of about 2%" at 40 Hz at the permanent stations. `outputs/cz/storm_summary.json`: −2.50% (p50 over 40 sites). It also records 7 solver failures and 40 of the 46 permanent stations; neither is stated. | File |
| N18 | 291 (and 1216) | "13.9 times" and "92.8%" match `soil_layers_summary.json`. `glacier_cells_pct` = 2.6% (l.300) implies about 137 km² of the 5250 km² box, against 97.3 km² of glacier (l.240). Explain the definition (any ice > 0 in a 100 m cell?). | File |
| N19 | 371, 754 | Magma body "16% slower" from mean ln −0.16 (that is 14.9%); elsewhere the paper converts ln to % correctly (l.677). | Text |
| N20 | 676 vs 736 | "lowers Vp/Vs at 2–4 km depth from 1.83 to 1.74" has no stated source; `tbl:imush` (north, published model) gives 1.769 and 1.738. Name the statistic and region. | File (`ulberg2020_by_depth.csv`) |
| N21 | 801–806 | Three open TODOs in `tbl:swarms` and l.806 (MAD 20 vs 23, 106 vs 133, "1500" vs 2335 nanostrain). Unreproduced numbers in a results table are a blocker for **P3** and **P1**. | Text (TODO markers) |
| N22 | 1153 vs 1196 | 15,660 events and 500 above ground (box, since 1980) against 15,631 and 435 (viewer overview box, viewer terrain). One sentence on why they differ. | Text |

Checked and consistent (File): held-out PNSN 1D 0.131/0.263 s (`heldout_published.json`); `tbl:iterations`, all rows (`history.json`); multipliers and posterior s.d. (`velocity_calibration.yaml`); `tbl:models`, PNSN 1D, uncalibrated, v1 and published rows; `tbl:wells`, every cell (`outputs/wells/summary.json`); `tbl:strain` and the QC split 11/9/2 (`outputs/gnss/summary.json`); `tbl:wrsz` (`strain_3d_summary.json`); `tbl:soil` and `tbl:env` medians (`soil_layers_summary.json`); `tbl:relocation` located and rejected counts and grade A+B = 344; `tbl:imush` north rows (`ulberg2020_by_depth.csv`, rebuilt after the critical-zone model on 3 October). The `fused_v2` column in that file is the published model, as `scripts/21_*.py` documents, but "v2" collides with `velocity_calibration_v2.yaml` (the run without the critical zone). Consider renaming it.

### S-RE.7 Uncertainty with each product: PARTIAL
Uncertainty is reported for the calibration (posterior s.d., linearised and χ²-scaled), the GNSS dilatation (±), the GEDI biomass (SE) and the relocated depths (median depth s.d.). It is missing or only implicit for:
- **Ice volume, 5.50 km³ (l.240):** IceBoost error grids are cached (`tbl:raw`) but no volume uncertainty is quoted. **P5**.
- **Alteration, 10.6 km² and 1.9 km³ (l.569):** no sensitivity to the 0.3 and 0.7 thresholds of `eq:alteration` or to the fresh level L_f. **P1**.
- **Fused Vp, Vs and density in L1–L2:** no per-cell uncertainty is distributed. Only `vs_unc_regional` below 9.9 km (from CRESCENT) exists. The product table (l.1084) should say what is and is not there. This is the first thing **P1** and **P6** look for.
- **Held-out and relocation RMS gains:** a single odd/even split, with no bootstrap or paired test on per-event RMS. **P2** will ask whether 0.092 against 0.131 s survives another split. A bootstrap over events from the existing per-event residuals would answer it.
- **`tbl:bias`:** "0.003–0.016" for all knots. Give the s.d. per knot in the table (the figure has it).
- **Strain:** no uncertainty on maximum shear, azimuth (`tbl:strain`) or `tbl:wrsz`. No statement of how uncertainty grows with depth for an assigned field (**P3**). The abstract's "10 nanostrain per year" has no error.
- **Edifice-load stress and strain:** ρ and ν are placeholders, with no sensitivity range (for example ν 0.2–0.3).
- **Mass-movement catalogue:** no completeness by class or date (377 of 1,650 dated, 351 of them from one storm). **P4** needs this to use the catalogue as a time-dependent layer.
- **Water tables:** the Ma et al. ensemble uncertainty is not carried (l.991). Say this in `tbl:env`.

### S-RE.8 Figures and tables referenced and in order: FAIL
- Never cited in the text: `fig:residuals` (l.722), `fig:imush` (l.740), `fig:relocated` (l.1186), `fig:relshift` (l.1188), `tbl:czlayers` (l.467).
- Out of numerical order: `fig:mass` (cited l.239 for the fault traces, numbered 24), `fig:strain` and `fig:strainseries` (cited 20 then 19), `tbl:mass` and `tbl:mass-counts` (cited 28 then 27).
- `fig:relocated` caption (344 events, grade A/B in rainier3d) and `tbl:relocation` (340 events, A/B in both models) use different subsets. State both in the text.

### S-RE.9 Secondary material to a supplement: PARTIAL
Candidates for an appendix, which would shorten the Results for **P1**:
- the eikonal solver benchmark (l.621);
- the NonLinLoc cross-check (l.623, "not rerun");
- the S6 check at ComCat hypocentres (l.742–744, `fig:pnsn`);
- the deposit-thickness table (`tbl:dmuthick`);
- `tbl:ai`;
- the literature-source list of mass movements (`tbl:mass`, l.1055–1072).

## Tier feed
- **C2 (soundness and data quality):** N1 (held-out leakage into the published-model score); N7 (catalogue on disk differs from the paper); N9 (one `tbl:models` row has no run record); N6 and N11 (stale tables against the run records); missing per-product uncertainties (S-RE.7).
- **C4 (evidence to conclusion):** I1, I8, I10, I13 and I14 are claims that outrun the data. I13 contradicts l.946–947, and I14 states an assumed field as a measurement in the abstract. N2, N3 and N16 are conclusions that quote superseded or wrong numbers.
- **C5 (presentation):** catalogue placement and the terrain–catalogue order (S-RE.2); duplication (S-RE.3); uncited and out-of-order figures and tables (S-RE.8); the open TODOs in `tbl:swarms`.

## Persona notes
- **P1 (ESSD data reviewer):** stops at N7 (1,650 against 1,649 in the deposited catalogue) and at the missing per-cell uncertainty of the fused model.
- **P2 (volcano seismologist):** stops at N1 and at the single split. Wants the 9 against 2 above-ground events from S14 in `tbl:models`.
- **P3 (geodesist):** stops at I14 in the abstract and at the TODOs of `tbl:swarms`.
- **P4 (hydrologist and geomorphologist):** needs catalogue completeness by class and date, and the terrain comparison placed after the catalogue.
- **P5 (cryosphere):** needs the ice-volume uncertainty and an explanation of the 2.6% glacier cells against 97.3 km².
- **P6 (hazard practitioner and data engineer):** finds the relocated catalogue in the Access section; it should move.

## Ordered fixes
1. **Held-out score (N1).** Quote fitting-half iteration 4 (0.092/0.186 s, `history.json`) as the held-out result everywhere, abstract included. Report the published-model score on those 44 events as "after the final all-event iterations". Reword l.707.
2. **Regenerate every number from the current run records and align abstract, body, Limitations and Conclusions.** Covers N2–N7, N10–N13, N16 and N17: `tbl:invariant` from `fusion_report.csv`; `tbl:edificestrain`; catalogue counts after rerunning S30 on the 5 October S24 output; Conclusions V₀ ×1.47, one event above the ground, 0.107 s; Limitations 23%/31% and 10 events. Restore or delete the conduit row of `tbl:models` (N9).
3. **Cut or hedge the five overruns.** I13 (delete; it contradicts l.946); I14 (abstract: "the GNSS surface strain rate, carried to depth under a plane-stress assumption, gives ..."); I1 ("agrees with"); I10; I8. Move I15 and E3 to a discussion paragraph or Limitations. Fix E2 (4.70 lies outside 4–4.5).
4. **Reorder and cite.** Move `sec:relocation` after `sec:validation`; move the terrain–catalogue comparison into `sec:mass`; move calibrated values out of `sec:petro` and `sec:cz`; cite `fig:residuals`, `fig:imush`, `fig:relocated`, `fig:relshift` and `tbl:czlayers`; fix the numbering order of `fig:mass`, `fig:strain` and `tbl:mass`. Then add one uncertainty statement per product (S-RE.7), starting with the ice volume, the alteration area and a bootstrap on the held-out RMS.
