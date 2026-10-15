[S-AB] TITLE / ABSTRACT / PLS
Iteration 1, full first review. Manuscript: docs/paper/rainier3d_paper.md on main @ d61305c (line numbers below refer to this file).
Target: ESSD data description paper (profile calibration row, not the GRL table).

Inventory
- Title (l.2): "rainier3d: a reproducible digital model of the subsurface and surface of Mount Rainier, Washington" (16 words).
- Abstract (YAML `abstract:`, l.24-44): 8 paragraphs plus a 4-item bullet list, about 507 words (`sed -n 24,44p | wc -w` = 508, less the YAML key).
- Plain-language field: none for ESSD. The YAML `description:` (l.5, HTML meta and site card) acts as a one-sentence summary and was read as such.
- Length: ~507 words. No hard cap checked. To my knowledge Copernicus sets no word limit for ESSD abstracts, but most ESSD abstracts run 200-400 words; this one is about twice the median. Not verified online this session.
- Abstract structure present: problem[N] approach[Y] result[Y] significance[partial]
- Quantitative result stated: Y (calibration RMS, relocation RMS, strain rate, catalogue counts)
- Data location / DOI in abstract: N

Verification legend: [OUT] = checked against a file in outputs/ or configs/ on this machine; [TXT] = checked against body text only.

Faithfulness (per result sentence)
| # | Abstract sentence (first words), line | Support | Status |
|---|---|---|---|
| F1 | "It covers a 70 × 75 km box ... 20 km below sea level" l.25 | §2 l.76, tbl:grids l.93-98 [TXT] | supported |
| F2 | "...four are read from local or delivered copies" l.25 | §3 l.152-156 [TXT] | supported, but see S-AB.12 (another set of four machine-local inputs at l.182) |
| F3 | "the whole database can be rebuilt with one environment ..." l.25 | §3.2 l.160-182 [TXT] | partial: l.162 says stages needing credentials or delivered files skip those layers; l.1225 says the 10 m lidar grids were made in QGIS |
| F4 | "three stacked grids ... from 250 m × 50 m to 1 km" l.27 | tbl:grids l.93-98 [TXT] | supported |
| F5 | "Mapped geology is extended to depth by explicit rules" l.27 | §sec:geology l.522ff [TXT] | supported |
| F6 | "Near-surface hydrothermal alteration ... helicopter electromagnetic survey" l.27 | §sec:alteration l.559-581 [TXT] | supported |
| F7 | "A pressure-dependent rock-physics law ... merged ... in the wavenumber domain" l.27 | §sec:rockphysics l.363, §sec:fusion l.583 [TXT] | supported |
| F8 | "calibrated on 1823 P and 1280 S analyst picks from 88 ..." l.29 | §sec:calibration l.618 [OUT: outputs/joint_calibration_cz/picks.csv has 88 events; history.json all-events n = 1819+4 rejected P, 1280 S] | supported |
| F9 | "Three rock-physics multipliers and a depth-dependent correction ... Gauss–Newton" l.29 | l.624-648, tbl:multipliers, tbl:bias [TXT] | supported |
| F10 | "On the 44 held-out events ... 0.092 s for P and 0.187 s for S, against 0.131 and 0.263 s ... and 0.120 and 0.316 s before calibration" l.29 | §sec:validation l.709 and tbl:iterations row 0 l.666 [OUT: outputs/relocation/heldout_published.json 0.0921/0.1866 vs 0.1307/0.2632; outputs/joint_calibration_cz/history.json iteration 0 held-out 0.1198/0.3163] | supported, but the "before calibration" pair comes from S13 (history.json), the other two from S14 (heldout_published.json); intro l.54 gives 0.186 for the same quantity (S13 iterate 4). See S-AB.9 |
| F11 | "An independent local-earthquake tomography confirms the Vs correction beneath Rainier" l.29 | §sec:validation l.727-735, tbl:imush [TXT] | overstated: see S-AB.9 |
| F12 | "the 371 PNSN earthquakes ... median RMS 0.107 against 0.119 s for the 340 well-located events ... one ... 12 m, against four pinned" l.31 | §sec:relocation l.1162-1180, tbl:relocation [OUT: outputs/catalog/summary.json n_events 371, rms_median 0.1065/0.1195, above_ground 1/4; the 340 is not in summary.json, paper text only] | supported; contradicted by Conclusions l.1235 (0.109 s; "no event lies above the ground") |
| F13 | Surface layer list l.33-37 | §sec:surface-core l.230, tbl:env l.250-260, tbl:canopy l.304-315 [TXT] | supported |
| F14 | "Both are carried into the model volume as strain on a 500 m grid" l.39 | §sec:strain3d l.832, tbl:products l.1086 [TXT] | imprecise: the grid is 500 m horizontal × 250 m vertical |
| F15 | "at 5 km below sea level the geodetic field loads the WRSZ in right-lateral shear at 10 nanostrain per year" l.39 | tbl:wrsz l.845-851 [OUT: outputs/gnss/strain_3d_summary.json right_lateral_shear_rate_median 9.97e-9 yr⁻¹] | number supported; framing overstated: see S-AB.9 |
| F16 | "1,650 landslide, avalanche and debris-flow events, 19 ... seismically, ... 463 debris flows and three lahar deposits" l.41 | §sec:mass, tbl:mass-counts l.1040-1051 [OUT: outputs/mass_movements/events.csv dated 5 Oct 2026 has 1,649 events (1,623 crowns, 323 slides), summary.csv has 316+7 slides; the paper table cites the run of 2026-09-25 with 1,650 / 1,624 / 324] | CHECK AGAINST RESULTS: count differs by one from the current local output |
| F17 | "distributed under CC-BY 4.0 with a command-line and Python client ... formats" l.43 | §sec:access l.1078-1149, tbl:products, tbl:formats [TXT] | supported for products-v1.0.0; the relocated-catalogue and storm releases have no licence yet (TODO at l.1243) |
| F18 | "A web viewer shows ... the relocated catalogue and the storm" l.43 | §viewer l.1198 [TXT] | "the storm" has no antecedent in the abstract; see S-AB.11 |

Findings

S-AB.1 PARTIAL (length, l.24-44). About 507 words, against no hard ESSD cap that I can confirm offline. For a reader deciding whether to download (P1, P6) the length is less of a problem than the layout: Copernicus abstracts are plain text in the journal metadata and Crossref deposit, so the bullet list at l.33-37 would be flattened or dropped. Suggest one sentence for the surface layers and a cut of about 150 words, mostly from l.27 (method detail) and l.31 (relocation detail).

S-AB.2 FAIL (problem and gap, l.25). The abstract opens with what rainier3d is, not why it is needed. The gap is stated well in the Introduction (l.48: monitoring relies on 1D models with station corrections; regional 3D models do not resolve the edifice, altered core, glaciers or shallow units). One sentence of that before l.25 would let a hydrologist or cryosphere reader (P4, P5) see why a seismological calibration sits at the centre of a multi-layer data set.

S-AB.3 PASS (approach, l.25-29). Scripted fetch, checksummed cache, source registry, rule-based geology, EM alteration, rock-physics law, wavenumber fusion and travel-time calibration are all named.

S-AB.4 PASS (quantitative result, l.29, l.31, l.39, l.41). Numbers are given with their comparison baselines. F10 is the strongest sentence in the abstract.

S-AB.5 PARTIAL (significance, l.43). Usefulness is implied by the export formats but never said. One clause on who can use it (earthquake location and waveform modelling, deformation models, lahar and landslide studies) would serve the ESSD usefulness criterion (C1).

S-AB.6 PARTIAL (one-sentence contribution). The profile defines the contribution as integration of subsurface, surface, geodetic and hydrologic layers on one grid. The abstract implies it ("The same grids carry ...", l.33) but never states it as the contribution. Suggested opening: "rainier3d places the subsurface, surface, geodetic and hydrologic layers of Mount Rainier and the West Rainier Seismic Zone (WRSZ) on one set of grids, built from open archives by a scripted, checksummed workflow."

S-AB.7 PARTIAL (title, l.2). Specific and accurate on scope. Two judgment calls:
- "reproducible" is a claim a P1 reviewer will test first. Four inputs are local or delivered copies (l.152-156), some layers skip without credentials (l.162), the 10 m lidar grids were made in QGIS (l.1225), and no DOI or software tag exists yet (l.1243). The claim may hold for the published products-v1.0.0, but if the title keeps it the abstract should qualify it as it already does at l.25.
- The title names Mount Rainier only, while the box is chosen to include the WRSZ and two abstract results concern it (l.31, l.39). "Mount Rainier and the West Rainier Seismic Zone" could be added if length allows. ESSD titles often name the data set type ("a gridded data set of ..."); optional.

S-AB.8 PARTIAL (traceability). 15 of 18 sentence-level claims trace to a section and table (see table). F11 and F15 trace but are overstated (S-AB.9). F16 is CHECK AGAINST RESULTS: the paper's 1,650 events matches the 2026-09-25 run quoted in the tbl:mass-counts caption (l.1051), but the S24 outputs now on disk (outputs/mass_movements/events.csv, 5 Oct 2026) hold 1,649 events, 1,623 crowns and 323 slides. Either the paper or the cache needs a rerun of S24 before submission.

S-AB.9 FAIL (claims beyond the body), three items:
- l.29 "An independent local-earthquake tomography confirms the Vs correction beneath Rainier." The body (l.727-735) says the comparison is "largely independent in the south, less so in the north", that iMUSH Vs is resolved over only 11-19% of the northern half, that the source is local earthquakes and explosions, and that at 4-8 km rainier3d Vp/Vs is about 0.05 below iMUSH. Suggest: "The Vs correction agrees with the iMUSH tomography beneath Rainier to within 2% below 2 km depth, where that model resolves Vs." (P2 would ask this first.)
- l.39 "at 5 km below sea level the geodetic field loads the WRSZ in right-lateral shear at 10 nanostrain per year." The body (l.835-838) states that the horizontal rate is carried down unchanged by assumption, "not observations", so the value is the same at every depth. Naming a depth reads as a depth-resolved result, and "loads" is interpretive. Suggest: "Assuming the surface strain rate holds through the elastic upper crust, the GNSS field is right-lateral on planes parallel to the WRSZ at 10 nanostrain per year." (P3.)
- l.29 vs l.54: the abstract gives held-out S RMS 0.187 s (S14 relocation in the published model) and the Introduction gives 0.186 s (S13 iterate 4) for what reads as the same quantity, and "0.120 and 0.316 s before calibration" in the same abstract sentence is an S13 number, not S14. Both are defensible; one sentence in the abstract mixes two scripts. Suggest using S14 for all three models if an S14 uncalibrated held-out score exists, or saying "during calibration" for the 0.120/0.316 pair, and aligning l.54 with l.29.
- Cross-feed (not in S-AB scope, for C4): Conclusions l.1235 says median RMS falls to 0.109 s and "no event lies above the ground", both contradicting abstract l.31, tbl:relocation and outputs/catalog/summary.json (0.1065 s; one event 12 m above ground). Conclusions l.1232 says V₀ is raised by 31%, which is the calibration without the critical zone (tbl:multipliers caption); the published value is ×1.47. Conclusions "5-9% too slow at 2-7 km" vs tbl:bias factors 1.045-1.081 (4.5-8.1%).

S-AB.10 PARTIAL (acronyms, readability). WRSZ, PNSN and RMS are defined. Undefined or unexplained: GNSS (acceptable for this readership), CRESCENT Gen0 (a P4/P5 reader cannot tell it is a regional velocity model; "the CRESCENT Gen0 community model" would do), NonLinLoc at l.31 (named without saying it is a location code), "S−P residuals" (fine for P2, opaque for P4-P6). The abstract starts sentences with lowercase "rainier3d" (l.25, l.31 mid-sentence is fine); Copernicus copy-editing may capitalise it, so the authors may want to decide first.

S-AB.11 FAIL (self-containment, ESSD). Three gaps:
- No data location, DOI or version in the abstract. ESSD asks that the data set be identified by its DOI in the abstract (Copernicus ESSD guidance as I recall it; not checked online this session). The Zenodo concept and version DOIs are still TODO (l.1243), and products-v1.0.0 is a GitHub release asset, which P1 will not accept as a persistent repository. Once deposited, add "The products are available at https://doi.org/10.5281/zenodo.XXXX (Denolle et al., 2026)" as the last sentence.
- "the storm" (l.43) has no antecedent: the December 2025 flood section was removed on 2026-10-05, and the only body mention is the viewer bullet at l.1198 and the S29 cache rows at l.138-139. Either say "the December 2025 atmospheric-river storm" or drop it from the abstract. Its release has no licence yet (l.1243).
- The abstract says nothing about placeholders. "Every parameter names its source in a registry" (l.25) is literally true, because `m1_placeholder` is a registry key, but reads as if every value is sourced. Limitations l.1209 lists all 16 unit rows of configs/petrophysics.csv and several configs as placeholders. P1 will check this. A clause such as "author-chosen values are flagged as placeholders" keeps the Limitations candour (never_change) visible in the abstract.

S-AB.12 PARTIAL (completeness of the data description, P1, P4). The abstract omits two products the body treats as central:
- the critical-zone model (§sec:cz, l.445-516), which is in every trial model of the published calibration and raises V₀ from ×1.31 to ×1.47 (tbl:multipliers caption);
- the soil-property, regolith and Vs30 layers (§sec:surface-soil, l.272) and the terrain-geometry layers (§sec:surface-terrain, l.323), and the geohydrology section (§sec:hydro, l.960) as such.
The edifice-load stress product (`edifice_load`, tbl:products l.1087) is mentioned only as converted strain. "Four" at l.25 is also ambiguous: §3 l.152 lists four model inputs, and l.182 lists a different four machine-local inputs of the viewer platform. Naming them ("the Cascadia and CRESCENT model files, the PNSN 1D table and the delivered canopy products") would remove the ambiguity, though it costs words.

S-AB.13 PASS (description field, l.5). Consistent with the body and free of jargon beyond "PNSN". It omits the relocated catalogue and the viewer; fine for a meta description.

Persona notes (lenses, not scores)
- P1: S-AB.11 (no DOI; placeholders invisible), S-AB.7 ("reproducible"), F16 count mismatch.
- P2: S-AB.9 first bullet; would also ask why 371 events are named when 340 are compared.
- P3: S-AB.9 second bullet; "500 m grid" (F14).
- P4/P5: S-AB.2 (no motivation for non-seismologists), S-AB.12 (critical zone and soil/Vs30 layers missing), "the storm" undefined.
- P6: S-AB.5; the abstract does name formats and client, which serves P6 well.

Tier feed
- C1 (significance; ESSD uniqueness/usefulness/completeness): S-AB.2, S-AB.5, S-AB.6, S-AB.12. The integration claim is the contribution and should be stated as such.
- C4 (evidence to conclusion): S-AB.8 (F16 CHECK AGAINST RESULTS), S-AB.9 (iMUSH "confirms"; depth-invariant strain stated at 5 km; mixed S13/S14 numbers), plus the Conclusions contradictions at l.1232 and l.1235.
- C5 (presentation): S-AB.1 (length; bullets in a plain-text abstract), S-AB.10, S-AB.11 ("the storm"), S-AB.12 ("four" ambiguity).
- C7 (data/code availability, ESSD): S-AB.11 (no DOI in abstract; DOIs TODO; GitHub release not a persistent repository; two releases unlicensed), S-AB.7 (reproducibility claim in the title vs l.152-162, l.1225).

Top fixes, ordered
1. Mint the Zenodo DOIs and put the data DOI, version and licence in the last abstract sentence (S-AB.11). Blocking for ESSD.
2. Recast "confirms" (l.29) and the 5 km strain sentence (l.39) to match what the body shows (S-AB.9), and fix Conclusions l.1232 and l.1235 so they agree with the abstract and tbl:relocation.
3. Rerun or reconcile S24 so the 1,650 / 1,624 counts in l.41 and tbl:mass-counts match outputs/mass_movements/events.csv (currently 1,649 / 1,623) (S-AB.8).
4. Add one gap sentence and one contribution sentence at the start, replace the bullet list with a sentence, define or drop "the storm", mention the critical zone and the placeholder flag, and cut about 150 words of method detail from l.27 and l.31 (S-AB.1, .2, .6, .11, .12).
