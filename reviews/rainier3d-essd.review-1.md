```
DENOLLE GROUP PRE-SUBMISSION REVIEW
=====================================
Manuscript: rainier3d: a reproducible digital model of the subsurface and surface of Mount Rainier, Washington
Target: Earth System Science Data (ESSD), data description paper     Date: 2026-10-07
Reviewer: Pre-Submission Orchestrator (10 subagents -> 8-criterion synthesis)
Note: Advisory. All findings require human judgment before submission.
Profile: denolle-rainier3d (ESSD calibration row and readership personas P1-P6 from the profile)
Provenance: Skill v2.5 (commit 211bcc1 + LOCAL_PATCHES.md) | Model claude-opus-5-5 | Iteration 1 |
            Manuscript sha256 f57858892585 (docs/paper/rainier3d_paper.md, main @ d61305c, 1313 lines)
Mode: Full first review
```

Subagent blocks (full findings with line numbers): `reviews/rainier3d-essd-iter1/S-*.md`.
Line numbers refer to `docs/paper/rainier3d_paper.md` at d61305c.

## Summary

rainier3d puts subsurface velocity, density and attenuation, a critical-zone model, surface layers, geodetic strain,
edifice-load stress, geohydrology and a mass-movement catalogue for Mount Rainier on one grid. It is built by a
scripted, checksummed pipeline from public archives, with every parameter traced to a source registry. The data set
is unique for a Cascade volcano and the rebuild route is unusually well documented: the reproducibility culture of
the repository is the paper's main strength. The paper is not ready for ESSD. The blocking issue is the data
deposit: there is no DOI, and the only published product release (`products-v1.0.0`) predates the model the paper
describes by 121 commits. After that, the paper needs one pass to bring numbers into agreement (Conclusions and
Limitations still quote the calibration without the critical zone), per-product uncertainty statements, a
positioning paragraph against comparable models, and a smaller main-text figure set.

## Submission readiness

```
  [ ] Ready — minor issues only
  [ ] Revise before submission
  [ ] Major revision required
  [x] Not ready — fatal issue(s) first

  FATAL:
   1. S-RP.R1/R2, C3 | No persistent identifier for data or code; products-v1.0.0 predates the described model
      (no critical zone, no REBUILD.md/inputs.csv); tbl:products describes a products-v1.1.0 that does not exist;
      no v1.0.0 software tag. ESSD checks data availability before review. | l.1092, l.1241
  MAJOR:
   1. S-CO.6, S-DI.1, S-RE.6 (C4) | Conclusions and Limitations contradict the body: V0 "+31%" (adopted x1.47),
      RMS 0.109 s (0.107), "no event above ground" (1, 12 m), 21/30% (23/31%), 12 rejected events (10). | l.1212,
      l.1219, l.1232, l.1235
   2. S-ME.10, S-RE.1 (C2/C4) | The "44 held-out events" score of the published model is not fully independent:
      S13's last two iterations use all 88 events and lambda_s is chosen on the held-out half. The independent
      number is the fitting-half iteration 4: 0.092 s (P), 0.186 s (S). The abstract (0.187) and introduction
      (0.186) disagree. Verified in outputs/joint_calibration_cz/history.json and scripts/13 l.249-254. | l.29,
      l.53, l.707
   3. S-ME.14, S-RE.7, S-DI.11 (C2, ESSD) | Most gridded products carry no uncertainty (Vp, Vs, rho; alteration;
      critical-zone columns; strain at depth; load stress); dilatation_sigma exists in the strain grid but is not
      described. ESSD asks for it per product.
   4. S-ME.15, S-ME.17 (C2) | "One effective stress for the whole model" overstates the code: pore pressure is
      shared, but L1-L3 use a constant rho_b = 2500 kg/m3 from the ground or ice surface (ice loaded at 2500, not
      917), while the columns integrate actual densities. Geohydrology still describes the old hydrostatic rule
      and "no coupling". Verified in src/rainier3d/properties/assign.py l.56-64. | l.440ff, l.1008-1014
   5. S-RP.R4 (C3) | "Four inputs from local copies" understates: configs read at least ten from ~/Downloads or
      ~/GitHub, including the unidentified PNSN 1D table (the validation baseline) and canopy files whose upstream
      repository is private. | l.25, l.152, l.182, l.1237
   6. S-RP.R3, S-RP.R5 (C3/C4) | Headline numbers differ between paper, docs/joint_calibration.md and the
      relocated-catalogue release (0.188 vs 0.187 s; 353 vs 354 located; 0 vs 1 above ground); three strain values
      carry "no script computes it" TODOs. | l.801-806
   7. S-IN.2, S-CD.10, S-DI.4 (C1/C6) | No positioning against comparable integrated models (SCEC CVM/CFM, other
      instrumented volcanoes, digital-twin or ESSD precedents); the gap is argued only against coarse regional
      models; Rainier imaging papers already in the bib (McGary 2014, Bedrosian 2018, Delph 2018, Moran 1999)
      are not cited. | l.48-55
   8. S-AB.9, S-DI.10, S-RE.4 (C4) | Overreach: "tomography confirms the Vs correction" (iMUSH resolves Vs over
      11-19% of the north); WRSZ shear "at 5 km" is a surface value extended by assumption; "load stress sets the
      orientation" contradicts l.946 (tectonic background unknown); "does not overfit" on an interleaved split.
      | l.29, l.39, l.707, l.826, l.855
   9. S-FD.12 (C8/C3) | Figures show the CC-BY-NC-ND Ma et al. water table (fig:surface b, fig:depthrock c) and
      DNR lidar layers with unconfirmed terms (fig:canopy a/b) inside a CC-BY Copernicus article.
  10. S-FD.1, S-FD.3, S-RE.8 (C5) | 26 figures and 32 tables, about twice an ESSD data description; four figures
      and four tables never cited (fig:residuals, fig:imush, fig:relocated, fig:relshift; tbl:outline, tbl:ai,
      tbl:czlayers, tbl:datasets); fig:mass, fig:strain, tbl:mass cited out of order.
  11. S-FD.11 (C2/C4) | Figure content disagrees with text: fig:pnsn 1828 vs 1823 picks; fig:map 240 nodes / 42
      seismometers vs 191 / 46; fig:mass 323 slides vs 324; fig:relocated 1D "1 above ground" vs 4.
  12. S-AB.11, S-CO.12-14 (C3/C5) | Abstract is not self-contained for ESSD (no DOI/version, "the storm" now has no
      antecedent, about 507 words with a bullet list); availability says products-v1.0.0 while tbl:products says
      v1.1.0; event-release licence TODO though the release notes already state CC BY 4.0.
  MINOR: see Detailed findings (S-ME.11-13, 16, 18, 20-30; S-FD.4-9; S-IN.6, 8, 11; S-CO.1, 3, 7, 9, 15-17;
         S-PR.1-6; S-CD.2-5; 22 [TODO] markers).
```

## Strengths

1. Deterministic, checksummed compilation: every cached input listed with its SHA-256 (`docs/data_manifest.csv`),
   a source registry behind every parameter, `m1_placeholder` as an explicit marker of author choices, and a
   platform rebuild that two runs reproduce byte for byte (S-RP.1, S-RP.10; S-ME.7-8).
2. The calibration relocates every event in every trial model, separates hypocentres from velocity by projection,
   and scores alternatives (Vs-only, regional depth factors) on the same data; the strain section states its
   assumptions as a model for the rest (S-ME.4, S-ME.6, S-DI.2).
3. High reference-combination novelty: community velocity models, granular contact mechanics, critical-zone
   refraction studies, water-table models, canopy, landslide inventories and GNSS strain on one grid; low
   self-citation (3.4%) (S-CD.1, S-CD.8).
4. Candid limitations and honest labelling of synthetic outputs as simulations (S-DI.7, S-DI.8).
5. Clean register: no em-dashes, no LLM-tell vocabulary, 12 word-level slips in 1313 lines (S-PR).

## Section by section

```
[S-AB] ~507 words (no hard cap confirmed); 13 findings: 3 PASS, 7 PARTIAL, 3 FAIL. Gap sentence missing (AB.2);
       overreach at l.29, l.39 (AB.9); no DOI/version, "the storm" orphaned (AB.11); critical zone and soil/Vs30
       omitted (AB.12). Numbers checked against outputs/ hold except mass movements (1,649 on disk vs 1,650).
[S-IN] Move 1 PARTIAL, Move 2 PARTIAL, Move 3 PASS with mismatch. Uniqueness argued only vs regional models;
       bullets L51-53 carry methods detail; S-labels, L1 and "invariant test" used before definition; 1D
       monitoring claim uncited.
[S-ME] Design, provenance, chain PASS; equations PARTIAL (4 defects: half-amplitude filter, Vs "floor" is a cap,
       Brie notation, residual phase index); uncertainty FAIL; held-out (ME.10), effective stress (ME.15),
       stale Geohydrology (ME.17) MAJOR; Q rule citable (Olsen et al. 2003, to verify); 12 TODOs in methods.
[S-RE] Order PARTIAL (relocation under "Accessing the model"; calibrated values used before calibration);
       17 interpretation sentences in results, 5 overreaching; l.496 "4.70 within 4 to 4.5" is false; numbers
       FAIL on several (see MAJOR 1, 6, 11).
[S-DI] Comparison breadth good regionally (CVM 1.7, CRESCENT, iMUSH, PNSN 1D, wells); missing magnetotellurics
       (McGary 2014), focal mechanisms, the Vs30 comparison announced at l.299, other volcano models.
       Alternatives missing: spatially blocked validation, 1D with station corrections, catalogue events reused
       from calibration, Vp/Vs at 4-8 km 0.05 below iMUSH (the same objection used against the Vs-only fit).
[S-CO] Pols 4/7; element 3 (problem) missing; 4 of 5 numbers disagree with the body; new/unsupported scope claims
       (all but four inputs scripted; every parameter sourced; one layer carries time); critical zone absent.
[S-FD] 26 figures (fig21_flood_event.png orphaned), 32 tables, 17 numbered equations (6 referenced); citation
       order FAIL; 2 analytical captions (fig:fusion, fig:depthrock); colour CONCERN (fig:alteration rainbow,
       no units or panel letters; red units in sections); fig:workflow caption describes the wrong layout;
       fig:strainseries has no generating script.
[S-RP] Checklist: PASS 2 (RP.1, RP.10), FAIL 4 (RP.2, 4, 7, 8), PARTIAL 5. VERDICT: NOT RECONSTRUCTABLE.
       Blocking stops: R1 no DOI; R2 deposit is not the described product; R3 numbers disagree across artefacts;
       R4 >= 10 machine-local inputs; R5 three strain values without a script; R7 incomplete rebuild sequence
       (no pixi tasks for S19-S21, S26; NonLinLoc unpinned). Non-blocking: R6, R8-R10.
[S-CD] Self-citation 3.4% (4 of 118 keys); 47 venues; 1949-2026, median 2014; ~86% US-led (inferred, verify);
       novelty high; 60 bib entries uncited; 9 citation/licence/DOI TODOs.
[S-PR] 12 candidates (colloquial 4, metaphor 6, emotional 1, intensifier 1); highest-confidence swaps:
       "breaks" -> "violates" (l.700), "sees only" -> "is sensitive only to" (l.579), "fair measure" ->
       "unbiased measure" (l.720), "know neither" -> "include neither" (l.1153).
```

## Readership (personas from the profile)

| Persona | Served? | Single change that helps most |
|---|---|---|
| P1 ESSD data reviewer | No: stops at the availability section | Mint the Zenodo DOIs for a products release built from the described model |
| P2 Volcano seismologist | Mostly | Report the independent held-out score and a spatially blocked check |
| P3 Geodesist | Partly | Describe `dilatation_sigma` and state that strain at depth is the surface field by assumption |
| P4 Hydrologist | Partly | Fix the Geohydrology text to the shared water table; say which water table each product uses and its licence |
| P5 Cryosphere / atmosphere | Partly | Ice-thickness uncertainty and the removed storm layer's status in the viewer |
| P6 Hazard practitioner / data engineer | Mostly | One product table: format, CRS, licence, version, DOI, size, uncertainty |

## Diversity signals (surfaced, not scored)

Self-citation is low (3.4% of cited keys). Venues are broad (47; largest share JGR Solid Earth, 11%). The
reference years run from 1949 to 2026. Author geography is about 86% US-led, inferred by hand and explained by
the domain; verify before use. The gap is not diversity but positioning: no comparable integrated model or ESSD
precedent is cited. A draft Citation Diversity Statement is in `S-CD.md`; the profile marks it optional.

## Detailed findings by criterion

**C1 Scientific question and novelty: Good.** The data set is unique and the integration is the contribution
(S-CD.8, S-AB.3). C1.1 PARTIAL: the abstract and introduction never state the gap or name integration on one grid
as the contribution (S-AB.2, S-AB.6, S-IN.4). C1.2 PARTIAL: uses by reader community are implied, not named (S-IN.5,
S-AB.5).

**C2 Methods and soundness: Fair.**
- C2.1 FAIL: the held-out score of the published model (S-ME.10).
- C2.2 FAIL: no per-product uncertainty (S-ME.14, S-RE.7).
- C2.3 FAIL: "one effective stress" overstated; stale Geohydrology (S-ME.15, S-ME.17).
- C2.4 PARTIAL: four equation defects (S-ME.11-13, S-ME.30).
- C2.5 PARTIAL: under-ice rule differs from tbl:czlayers (S-ME.18); soft-sand above phi_c unstated (S-ME.16).
- C2.6 FAIL: fusion invariant table and top-300 m numbers stale against outputs (S-ME.21, S-ME.23).
- C2.7 PARTIAL: Electron Mudflow minimum read as a maximum (S-ME.26).
- C2.8 PARTIAL: tectonic strain at depth uses the 30-60 km smoothed grid (S-ME.28).
- C2.9 FAIL: figure numbers disagree with text (S-FD.11).

**C3 Reproducibility and open science: Fatal** (owned by S-RP).
- C3.1 PASS: data availability section present (RP.1).
- C3.2 FAIL: no DOI for data (RP.2, R1).
- C3.3 PARTIAL: three DOIs recorded "from memory" (RP.3).
- C3.4 FAIL: no code DOI, no software tag; `CITATION.cff` claims 1.0.0 with no tag (RP.4).
- C3.5 PARTIAL: pixi.lock pins the environment; NonLinLoc unpinned (RP.5, R6).
- C3.6 PARTIAL: rebuild block incomplete (RP.6, R7).
- C3.7 FAIL: products not in a data repository; release predates the model (RP.7, R2).
- C3.8 FAIL: FAIR "F" fails without a DOI (RP.8).
- C3.9 PARTIAL: restrictions stated; SoilGrids is a fourth non-redistributable source, the paper says three (RP.9, R10).
- Reproduction verdict: NOT RECONSTRUCTABLE (R1-R5, R7 blocking).

**C4 Evidence-conclusion alignment: Fair.**
- C4.1 FAIL: Conclusions/Limitations numbers (S-CO.6, S-DI.1).
- C4.2 FAIL: overreach at l.29, 39, 707, 826, 855 (S-AB.9, S-DI.10, S-RE.4).
- C4.3 FAIL: l.496 "4.70 within 4 to 4.5" is arithmetically false (S-RE).
- C4.4 PARTIAL: scope claims in the Conclusions (S-CO.9).
- C4.5 PARTIAL: alternatives not tested: blocked validation, 1D with station terms, iMUSH Vp/Vs objection applied to the adopted model (S-DI.6).
- Abstract trace: 15 of 18 claims trace to a section and table; 2 overstated; 1 to verify (mass-movement count) (S-AB.8).

**C5 Presentation: Fair.**
- C5.1 FAIL: figure and table load and citation order (S-FD.1, S-FD.3).
- C5.2 FAIL: abstract length and structure for Copernicus (S-AB.1, S-AB.11).
- C5.3 PARTIAL: two analytical captions; workflow caption wrong (S-FD.4).
- C5.4 CONCERN: colour and legends (S-FD.5, S-FD.7).
- C5.5 PARTIAL: terms before definition (S-IN.8).
- C5.6 PARTIAL: section order, with relocation under Access and calibrated values used early (S-RE.2).
- C5.7 Minor: 12 register slips (S-PR).

**C6 Literature integration: Fair.**
- C6.1 FAIL: no positioning against comparable models (S-CD.10, S-IN.9).
- C6.2 PARTIAL: Rainier imaging papers in the bib but uncited; Obrebski, Flinders, Ulberg only in Limitations and Validation (S-IN.9, S-DI.4).
- C6.3 PARTIAL: 9 citation/DOI/licence TODOs (Podvin and Lecomte 1991; Q rule; unit ranges; PNSN 1D identity) (S-CD).
- C6.4 PASS: every cited key resolves in the bib (S-CD); `docs/citations.csv` over-reports 4 keys as cited.

**C7 Impact: Good.** Significance is implicit in the export formats (S-AB.5). Future work is clear (S-DI.11), but
the Conclusions phrase the water budget as if no coupling exists (S-CO.7).

**C8 Ethics and compliance: Fair** (orchestrator).
- C8.1 PASS: AI use is disclosed in a dedicated section and in the availability statement.
- C8.2 FAIL: the Author contributions TODO "confirm all authors reviewed and edited" is open; the statement names
  "scripts S0-S29" (now S0-S36); SH's code contributions (the S36 magnetics stage, the sensor inventory and
  viewer fixes, PRs #32-#39) are not credited, only design and terrain specification.
- C8.3 CHECK: funding names only the Paros Geohazard Center; confirm whether any grant also supported the work.
- C8.4 FAIL: third-party licences of figure content (S-FD.12); event-release licence TODO (S-CO.14).
- C8.5 PASS: attribution notices present, but the text says "two" and lists three (S-CO.16).

## Journal-specific notes (ESSD)

- ESSD requires the data to be accessible through a persistent identifier before review. Run `scripts/27_zenodo_deposit.py` on a products release built from the described commit and cite the version DOI in the abstract and the availability section.
- Data sets in the appendix without a persistent identifier: 18 of 37 rows (S-RP inventory). Data services without a DOI are acceptable when the access route is stated; list them as such.
- Copernicus abstracts are plain text: remove the bullet list. No citations in the abstract.
- The figure count is not capped, but 26 figures and 32 tables exceed typical ESSD data descriptions; a supplement split is proposed in `S-FD.md`, with about 13 main-text figures.

## Items requiring human verification

- DOIs taken from memory: `brocher_2005`, `glathida`, `rgi60` (l.1250). Every candidate reference in S-CD.10, S-DI.4 and S-ME.27 (Olsen et al. 2003) is from model memory.
- Mass-movement count: 1,649 events in `outputs/mass_movements/events.csv` (run of 5 Oct) against 1,650 in the paper. S24 reads cached inventories, but a failed 1 m 3DEP window is skipped (`fetch_crown_dems`); check whether this dropped an event. If so, S24 is not deterministic.
- Identity of the PNSN 1D model table (l.155, l.1214, l.1266).
- Whether the private `koepflma/canopy-storage_seismic` upstream will be made public.
- Licence terms of the WA DNR lidar products and of SoilGrids 2017.
- Geographic and field labels in S-CD.4 and S-CD.5 were assigned by hand.

## AI-review disclosure stamp

> This manuscript was checked with the Denolle Group Pre-Submission Reviewer (v2.5, model claude-opus-5-5), an
> advisory AI tool, through 1 review iteration(s) prior to submission. All findings were reviewed and adjudicated
> by the authors. The tool does not run code, resolve links, or confirm results, and it does not endorse the
> manuscript's validity.

## Ledger for next iteration

```
LEDGER  (manuscript_id=rainier3d-essd  iteration=1  skill=v2.5 (211bcc1+local)  model=claude-opus-5-5)
S-RP.R1 | C3 | Fatal | OPEN | l.1241            | no DOI for data or code; no software tag
S-RP.R2 | C3 | Fatal | OPEN | l.1092, 1241      | products-v1.0.0 predates described model; v1.1.0 does not exist
S-RP.R3 | C3 | Poor  | OPEN | several           | headline numbers differ across paper, docs, release
S-RP.R4 | C3 | Poor  | OPEN | l.25, 152, 182    | >=10 machine-local inputs, not four; PNSN 1D unidentified
S-RP.R5 | C3 | Fair  | OPEN | l.801-806         | three strain values without a generating script
S-RP.R6 | C3 | Fair  | OPEN | l.1155-1159       | NonLinLoc version unpinned; S26 has no pixi task
S-RP.R7 | C3 | Fair  | OPEN | l.164-178         | rebuild block incomplete (S13/14, S20, S21, S25, S26, S29, S30, S33-36)
S-RP.R8 | C3 | Fair  | OPEN | l.369, 370, 557   | placeholder parameters without source ranges
S-RP.R10| C3 | Good  | OPEN | l.188             | four non-redistributable sources, paper says three
S-CO.6  | C4 | Fair  | OPEN | l.1232, 1235      | Conclusions numbers contradict body (V0, RMS, above ground)
S-DI.1  | C4 | Fair  | OPEN | l.1212, 1219      | Limitations numbers contradict body (21/30%, 12 events)
S-ME.10 | C2 | Fair  | OPEN | l.29, 53, 707     | published model's held-out score not independent
S-ME.14 | C2 | Fair  | OPEN | products          | no per-product uncertainty
S-ME.15 | C2 | Fair  | OPEN | l.440ff           | "one effective stress" overstated (constant rho_b, ice at 2500)
S-ME.17 | C2 | Fair  | OPEN | l.1008-1014       | Geohydrology describes the old pore-pressure rule
S-AB.9  | C4 | Fair  | OPEN | l.29, 39          | "confirms"; WRSZ shear at 5 km by assumption
S-DI.10 | C4 | Fair  | OPEN | l.707, 826, 855   | "does not overfit"; "sets the orientation"; "optimally"
S-RE.4  | C4 | Fair  | OPEN | l.496             | "4.70 within 4 to 4.5" false; 17 interpretation sentences
S-FD.11 | C2 | Fair  | OPEN | figures           | figure content vs text (picks, nodes, slides, above ground)
S-FD.12 | C8 | Fair  | OPEN | fig:surface b ... | NC-ND and unconfirmed-licence content in CC-BY figures
S-FD.1  | C5 | Fair  | OPEN | all               | 26 figures, 32 tables; supplement split
S-FD.3  | C5 | Fair  | OPEN | several           | uncited figures/tables; citation order
S-FD.4  | C5 | Good  | OPEN | captions          | analytical captions; workflow caption layout
S-FD.7  | C5 | Good  | OPEN | fig:alteration    | rainbow colour map, no units, no panel letters
S-AB.11 | C3 | Fair  | OPEN | l.24-44           | abstract lacks DOI/version; orphan "the storm"; bullets
S-AB.2  | C1 | Good  | OPEN | l.25              | no gap sentence in the abstract
S-AB.12 | C1 | Good  | OPEN | l.24-44           | critical zone, soil/Vs30 omitted from abstract
S-IN.2  | C1 | Fair  | OPEN | l.48              | uniqueness argued only vs regional models
S-IN.6  | C5 | Good  | OPEN | l.51-53           | contribution bullets carry methods detail
S-IN.8  | C5 | Good  | OPEN | l.48-55           | S-labels, L1, invariant used before definition
S-IN.11 | C4 | Good  | OPEN | l.29, 53          | 0.186 vs 0.187 s
S-CD.10 | C6 | Fair  | OPEN | l.48-55           | no positioning against comparable models
S-CD.TODO|C6 | Fair  | OPEN | l.155, 369, 370, 1158, 1250 | citation/DOI TODOs
S-DI.4  | C6 | Good  | OPEN | l.299, Limitations| missing MT, focal mechanisms, Vs30 comparison
S-DI.6  | C4 | Fair  | OPEN | Validation        | alternatives: blocked split, 1D+station terms, iMUSH Vp/Vs
S-CO.3  | C1 | Good  | OPEN | l.1230            | Conclusions omit the problem statement
S-CO.9  | C4 | Fair  | OPEN | l.1237            | scope claims (inputs, parameters, "one layer carries time")
S-CO.13 | C3 | Fair  | OPEN | l.1241 vs 1092    | v1.0.0 vs v1.1.0
S-CO.14 | C8 | Good  | OPEN | l.1241            | event-release licence TODO (already CC BY 4.0)
S-CO.16 | C5 | Good  | OPEN | l.1245            | "two" attribution notices, three listed
S-ME.11 | C2 | Good  | OPEN | l.593             | half-amplitude, not half-power filter
S-ME.12 | C2 | Good  | OPEN | l.589             | Vs "floor" is a cap
S-ME.13 | C2 | Good  | OPEN | l.420             | Brie notation clash
S-ME.18 | C2 | Good  | OPEN | l.464, 478        | under-ice rule vs tbl:czlayers
S-ME.21 | C2 | Good  | OPEN | tbl:invariant     | stale against fusion_report.csv
S-ME.26 | C2 | Good  | OPEN | tbl:dmuthick      | Electron Mudflow minimum read as maximum
S-ME.28 | C2 | Good  | OPEN | l.836-837         | depth strain uses smoothed grid
S-ME.32 | C3 | Good  | OPEN | pixi.toml         | s13 default iterations 3, published run used 4
C8.2    | C8 | Fair  | OPEN | Author contrib.   | TODO open; S0-S29 stale; SH code contributions uncredited
C8.3    | C8 | Good  | OPEN | Acknowledgements  | confirm funding sources
S-PR.1-6| C5 | Good  | OPEN | 12 lines          | register slips (l.505, 506, 579, 591, 699, 700, 709, 720, 1153, 1180, 1212, 1219)
VERIFY  | C4 | Good  | OPEN | l.41, 338, 343    | mass-movement count 1,649 on disk vs 1,650
```
