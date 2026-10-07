# [S-DI] DISCUSSION, iteration 1

Manuscript: `docs/paper/rainier3d_paper.md` on `main` @ d61305c (read only; nothing rerun). Line numbers are those
of that file. Target: ESSD. The paper has no Discussion section. Judged here: Limitations (L1202–1226), Conclusions
(L1228–1237), and the interpretive passages in the critical zone (L445–516), "Why this parameterisation"
(L698–703), Validation and the iMUSH comparison (L705–744), the fused model (L748–756), strain and load
(L822–958), the depth-to-rock and water-table text (L291, L985–1014).

```
[S-DI] DISCUSSION
Moves: M1 summarize[Y] · M2 evaluate[partial] · M3 implications[partial] · M4 future[Y]
Comparison breadth: self[Y] regional[Y] global[partial, one precedent]
Alternatives evaluated: [partial] · Limitations stated: [partial]
New results smuggled in: [N; but 6 stale or conflicting numbers in Limitations/Conclusions, S-DI.1]
Overgeneralization flags: [4: L826, L855, L29/L1232 "confirms", L707 "does not overfit"]
Findings: S-DI.1 FAIL (L1212, L1219, L1232, L1235, L1009, L1014) · S-DI.2 PARTIAL · S-DI.3 PARTIAL (L699 vs L726)
          S-DI.4 PARTIAL · S-DI.5 PARTIAL · S-DI.6 PARTIAL · S-DI.7 PARTIAL · S-DI.8 PARTIAL (L826, L855)
          S-DI.9 PASS · S-DI.10 FAIL (L826) · S-DI.11 PARTIAL
Top fixes: (1) reconcile the stale numbers in Limitations and Conclusions with the tables;
           (2) add a per-product "uncertainty and fitness for use" table to Limitations;
           (3) withdraw or qualify L826 and L855 and the word "confirms" for iMUSH;
           (4) add the missing comparisons (1D with station corrections; MT; Vs30; focal mechanisms; other volcano models).
```

## Verdict

For an ESSD data paper the interpretive load is about right in size, and most of it is already hedged: the
critical-zone dv/v is labelled "not a prediction" (L515–516), the strain section lists what it leaves out
(L935–958), and the magma body is handed to "data that resolve it" (L754). The weak points are of a different
kind. Limitations and Conclusions carry numbers from earlier runs that now contradict the tables, the Limitations
list omits several limits stated elsewhere in the text, and no product carries a spatial uncertainty a data user
can read. Two strain sentences draw conclusions the method section itself says cannot be drawn.

## Comparison breadth

| Scope | Present | Missing |
|---|---|---|
| Own group | dv/v magnitude against @clements_denolle_2023, @shi_2026 (L515) | nothing missing; self-reliance is light |
| Regional, seismic | CVM v1.7, CRESCENT Gen0 (fusion); iMUSH @ulberg_2020_article (L724–740); PNSN 1D; @moran_1999 and @pang_2025 for the magma body (L754) | Rainier-specific tomography @obrebski2015, @flinders2017 are named only as future work (L1213), never compared; magnetotellurics beneath Rainier (McGary et al. 2014, Nature) for the magma body and the Southern Washington Cascades Conductor; focal mechanisms or stress inversions at the summit and WRSZ (for example Moran et al. 2000, JVGR; verify) against the load SHmax and the WRSZ shear sense |
| Regional, surface | radar ice thickness @driedger1986 (L242); wells against two water tables (L997–1006); boreholes against depth to rock (L485–487); @finn_2001, @john_2008 for alteration (L579) | model Vs30 against the USGS Vs30 map, which L299 announces as "a reference for comparison" but never compares; glacier volume against @sisson2011 is deferred (L1218) |
| Global or other volcanoes | San Francisco Bay model @aagaard2021 (L524) | SCEC community velocity and fault models (CVM-S, CVM-H, CFM, UCVM); 3D velocity models of other instrumented volcanoes (Kīlauea and Mauna Loa, Lin et al. 2014; Mount St. Helens beyond iMUSH); volcano digital-twin efforts (EU DT-GEO for Etna and Campi Flegrei); ESSD precedents for multi-layer regional compilations. All named here as candidates; verify before citing |

## Alternatives considered

| Choice | Alternatives tested in the text | Not tested |
|---|---|---|
| Calibration parameterisation | two, scored the same way (L698–703, tbl:models) | none needed |
| Depth to rock | three estimators against 23 boreholes (L485–487) | none needed |
| Water table | two products against 5,591 wells (tbl:wells) | the model uses @fan2017_wtd (L397), which ranks upland wells at Spearman −0.13 (L1002); the consequence for the critical-zone Vs is not shown |
| Eikonal solver, air handling | pykonal vs fteikpy; air vs rock fill (L621–622, L1156) | none needed |
| Held-out split | alternating events in origin-time order (L656, L707) | a spatially blocked split; summit and WRSZ clusters put fitting and held-out events on shared ray paths |
| 1D baseline | PNSN 1D without station terms (tbl:models, tbl:relocation) | PNSN 1D with its station corrections, which is how the 1D model is used operationally |
| Fusion cutoffs, strain smoothing, load density and ν | single values, all `m1_placeholder` or author choices | no sensitivity shown |

## Limitations

The Limitations section is candid about placeholders and keeps that candour (never_change). It is incomplete as a
list a data user can work from. Limits stated in the body but absent from L1202–1226:

- critical-zone parameters are not calibrated (L505–506); the `f` factors, the 15 m fractured zone and the
  porosities of `configs/cz.yaml` are `m1_placeholder` (L465, L476–483) but `configs/cz.yaml` is not in the
  unsourced-parameter list at L1205;
- the Q rule gives a negative bulk Q in 11,738 fused cells with Vp/Vs < √(8/3) (L369), and the Q rule has no
  source (TODO at L369);
- 6,403 consolidated-rock cells reach Vp/Vs up to 3.97 in the top L1 cell (L495–497, L443);
- the adopted Vp/Vs at 4–8 km (1.70–1.71) is 0.05 below iMUSH (L726);
- the water table in the model is the one that fits upland wells worse (L397–399, L1002);
- the magma-body depth reference is unverified (TODO at L557);
- the identity of the PNSN 1D model is undocumented (L1214, listed, good).

No product states a spatial uncertainty. The model has `vs_unc_regional` from CRESCENT below 9.9 km (L587) and
linearised standard deviations of 15 parameters (tbl:multipliers, tbl:bias). Nothing tells a user how uncertain Vs
is in a given L1 cell, or how far the strain rate at 10 km can be trusted (L958 says only "least certain").

## Findings

**S-DI.1 FAIL. Limitations and Conclusions contradict the tables (C4).** Each pair below was read, not rerun.

| Line | Text says | Table or body says |
|---|---|---|
| L1212 | top 300 m: 21% faster in Vp, 30% in Vs | 23% and 31% (L677, L750; calibration with the critical zone) |
| L1219 | 12 events stop at the base of the search volume | 10 (L1163, L1169) |
| L1232 | V₀ raised by 31% | ×1.47 in the published model; 1.31 is the run without the critical zone (L673, tbl:multipliers) |
| L1232 | regional Vs 5–9% too slow at 2–7 km | factors 1.045–1.081 (tbl:bias), "5–8%" at L676 |
| L1235 | "no event lies above the ground"; median RMS 0.119 to 0.109 s | one event 12 m above (tbl:relocation L1172, abstract L33); 0.107 s (L1170, L1178) |
| L1009 | crack-closure law assumes hydrostatic pore pressure everywhere | hydrostatic below the water table, none above (L367); suction stress above it (L403) |
| L1014 | "None of these couplings is applied" | fluid substitution (Gassmann, L420–423) and the water table (L397) are applied in the critical zone and in P of every cell (L407) |

Fix: regenerate these from the same outputs as the tables; L1009–1014 should say what is applied (Fan water table,
Gassmann in the columns) and what is not (valley fill, hydrothermal core, loading).

**S-DI.2 PARTIAL. Interpretation against the question.** The three properties promised at L50–52 (tied to geology,
consistent with tomography, reproduces PNSN times) are each answered in the body, but Conclusions (L1230–1237)
never says whether the three were met; it lists contents. Fix: one sentence per property with its number.

**S-DI.3 PARTIAL. Expectations confirmed or not.** L699 rejects the Vs-only calibration because Vp/Vs 1.60–1.67 is
"low for crustal rock and lower still than expected beneath a volcano with a hydrothermal system". The adopted
model sits at 1.70–1.71 at 4–8 km, also below the independent iMUSH value (1.75–1.77, L726), and still has 11,738
cells below 1.63. The argument used against the alternative applies, more weakly, to the adopted model and is not
turned on it. P2 will ask this first. Fix: state at L701 or L726 that the adopted Vp/Vs at 4–8 km is 0.05 below
iMUSH and list it in Limitations.

**S-DI.4 PARTIAL. Comparison breadth (C6).** See the table above. The highest-value additions for this paper:
(a) magnetotellurics beneath Rainier (McGary et al. 2014) next to the magma body (L754) and the conductor
(L1210); (b) focal mechanisms or stress inversions against the load SHmax (L880) and the WRSZ shear sense (L855);
(c) one paragraph placing rainier3d among community velocity models (SCEC CVM/CFM, UCVM) and other volcano
models, where ESSD reviewers (P1) will look for "uniqueness". @obrebski2015 and @flinders2017 are cited only as
future constraints; a sentence on whether they agree with the regional correction belongs in the iMUSH paragraph.

**S-DI.5 PARTIAL. Contrasting results acknowledged (C6).** Good: iMUSH south of 46.65° N contradicts the
correction and the paper says so (L727, L1211); IceBoost vs radar on Emmons and Winthrop (L242). Missing: the
Fan water table is the worse of the two at the wells (L1002) yet drives the model, and this is said only in a
parenthesis (L398).

**S-DI.6 PARTIAL. Alternative explanations (C4).**
- The 10% RMS gain of the 3D relocation (L1178) is compared with a 1D model without station terms. L742 already
  shows that the 3D model explains part of what station corrections absorb, so the gain is partly a station-term
  effect. Some of the 371 events of 2023–2025 with M ≥ 2 are also among the 88 calibration events (L618), so the
  comparison is not fully independent of the fit. P2. Fix: relocate in the 1D model with PNSN station
  corrections, and report the RMS for events not in `configs/validation_events.csv`.
- Summit events move 0.52 km deeper (L1180). The text does not say which model feature does it (the slow
  edifice, the critical zone, V₀ ×1.47), or whether other depth studies of summit seismicity agree.
- Held-out split (L707): alternating events share paths with fitting events in two tight clusters. "So the fit
  does not overfit" (L707) is stronger than an interleaved split supports. Fix: a spatially blocked split
  (summit vs WRSZ) or soften to "the held-out and fitting misfits agree".

**S-DI.7 PARTIAL. Limitations explicit (C7, usability).** See the Limitations block. The items exist but are
scattered, and none is quantified per product. P1 and P6 need one place that says, for each product, what its
uncertainty is and what it is fit for. Examples the paper can state from what it already holds: usable frequency
for waveform modelling at 250 m × 50 m and 500 m grids (P2); strain rate in the volume valid as surface value only
(P3); water table upland reliability, Spearman −0.13 above 600 m (P4); glacier outlines about 2000 against a 2025
NDSI composite and 1981 radar (P5; L268, L242); redistribution status (P6, L1226).

**S-DI.8 PARTIAL. Interpretation marked.** Most interpretation is flagged ("illustrate the coupling, not a
prediction", L516; "assumptions, not observations", L839). Two are not:
- L855 "the geodetic field loads it almost optimally for right-lateral slip" rests on a depth-invariant
  surface rate (L839, eq:tectdepth) and a strike from epicentres; no uncertainty on the 9° angle or on the
  10.0 nanostrain/yr (no error in tbl:wrsz; the abstract L36 repeats it). P3.
- L869–870 "would need a source ... such as the pressurisation of the hydrothermal system" is a hypothesis in a
  data description; acceptable if marked "one candidate is".

**S-DI.9 PASS. No new results.** Limitations and Conclusions introduce no new analysis. Their conflicting numbers
are stale values, filed under S-DI.1.

**S-DI.10 FAIL. Overgeneralization (C4).**
- L826 "The load stress therefore sets the orientation of stresses in the upper crust beneath the edifice." The
  argument compares the load stress with 10³–10⁴ years of tectonic stress accumulation. L946–947 states that the
  absolute tectonic background stress is unknown, so the two cannot be summed. The orientation claim needs that
  background. Fix: "The load stress equals 10³–10⁴ years of tectonic loading at the geodetic rate; whether it
  dominates the orientation depends on the background stress, which is unknown ([@sec:strainmethod])."
- Abstract L29 "confirms the Vs correction beneath Rainier" and Conclusions L1232 "the iMUSH tomography confirms
  locally": iMUSH Vs is resolved over only 11–19% of the northern half (L725), and the north is where the two
  studies share the most PNSN data (L728). "Agrees with, where resolved" is what the evidence supports.

**S-DI.11 PARTIAL. Implications and future work (C7).** Future work is clear (L1204, L1206, L1212–1213, L1237).
Implications for users are thin: Conclusions does not say what the model enables (hazard, ground-motion and lahar
studies; wave-propagation runs; seismic detection of mass movements, which L1018 names) or for whom. One sentence
per audience would serve ESSD's usefulness criterion and the multi-discipline readership.

## Persona notes

- P1 (ESSD reviewer): no per-product uncertainty; stale numbers in Conclusions will be caught on first read.
- P2 (volcano seismologist): wants the 1D-with-station-terms baseline, a spatially blocked held-out test, the
  Vp/Vs shortfall against iMUSH, and the frequency limit of the grids.
- P3 (geodesist): wants uncertainty on the WRSZ shear rate and angle; L826 will draw an objection.
- P4 (hydrologist): the water table in the model is the worse one at the wells; L1009/L1014 contradict the
  critical-zone text.
- P5 (cryosphere): vintage mismatch of outlines, thickness, DEM and NDSI is not in Limitations.
- P6 (hazard and data engineer): needs one fitness-for-use table; licence gaps (L1226) are already explicit.

## Tier feed

| Criterion | Input from S-DI |
|---|---|
| C4 Evidence–conclusion | S-DI.1 (7 conflicting statements), S-DI.10 (L826; "confirms" at L29, L1232), S-DI.6 (1D baseline, L707). Lowers C4 until fixed. |
| C6 Literature | S-DI.4, S-DI.5: regional comparison good; MT, focal mechanisms, Vs30, other community and volcano models missing. |
| C7 Impact | S-DI.7, S-DI.11: limitations candid but scattered and unquantified per product; user-facing implications thin. |

## Fixes, ordered

1. Reconcile L1212, L1219, L1232 (×2), L1235 (×2), L1009 and L1014 with the tables (S-DI.1).
2. Add to Limitations a table, one row per product: uncertainty available, what it is valid for, known biases,
   pointer to the section. Fold in the missing items listed above (S-DI.7).
3. Rewrite L826 and qualify L855; replace "confirms" with "agrees where resolved" at L29 and L1232 (S-DI.8,
   S-DI.10).
4. Add the 1D-with-station-corrections relocation and a non-calibration-event subset to the catalogue comparison;
   soften or test L707 (S-DI.6).
5. Add a short positioning paragraph (community velocity models, other volcano models, MT at Rainier) and the
   Vs30 comparison announced at L299 (S-DI.4).
6. Turn Conclusions into a check against the three properties of L50–52 and add one sentence on uses by audience
   (S-DI.2, S-DI.11).
