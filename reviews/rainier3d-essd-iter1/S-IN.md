[S-IN] INTRODUCTION — iteration 1
Source: docs/paper/rainier3d_paper.md, main @ d61305c, lines 46–71 (read, nothing rerun).
Calibration: ESSD row of profiles/denolle-rainier3d.md (uniqueness, usefulness, completeness; reader can use the data without contacting the authors).

Swales moves: M1 [PARTIAL ¶1, L48] · M2 [PARTIAL ¶1, L48] · M3 [PASS ¶2–3, L50–55, but narrower than the abstract]
Five questions answered: problem[Y] prior[PARTIAL] limitation[Y] aim[PARTIAL] setup[Y]
Length: 3 paragraphs + 3 bullets + outline table (L59–71), ~505 words incl. table · Reads as review not motivation: N (reads as a results summary, not as motivation)

## Inventory

| Item | Location | Content |
|---|---|---|
| ¶1 territory + gap | L48 | Rainier hazard (Hoblitt 1998; Scott 1995); 1D monitoring models (uncited); regional 3D models (CVM v1.7, CRESCENT Gen0) do not resolve edifice, altered core, glaciers, shallow units |
| ¶2 contribution | L50–53 | three properties as bullets: tied to mapped geology (149 symbols → 14 units, 95 % invariant), consistent with regional tomography (cutoffs 6/10/20 km, RMS ln V 0.013 vs 0.03), reproduces PNSN travel times (0.120→0.092 s P, 0.316→0.186 s S) |
| ¶3 scope | L55 | surface layers, geodetic strain, edifice-load stress on same grids; "digital model, not digital twin" |
| Outline | L57–71 | table of 9 sections |
| Citations | L48–53 | 6 keys: hoblitt_1998, scott_1995, cvm17_article, crescent_gen0, dnr_gems_100k, comcat_uw (of 123 unique keys cited in the paper); all six present in docs/references.bib |

## Findings

S-IN.1 Move 1 — PARTIAL (L48). Territory is one sentence of hazard plus one of seismic practice. The claim "Seismic monitoring at Rainier relies on one-dimensional velocity models, with station corrections…" carries no citation; the PNSN 1D model is itself an open TODO (L1214, L1266). "Most hazardous volcano in the Cascade Range" is cited to Hoblitt 1998 and Scott 1995; the USGS national volcanic threat assessment (Ewert et al., 2005; update 2018, to verify and add to configs/sources.yaml) is the usual source for a ranking statement.

S-IN.2 Move 2 — PARTIAL (L48). The gap is stated only as a seismological scale gap (regional models too coarse). Two problems:
- (a) It overstates the gap by omitting Rainier-specific imaging. Moran, Lees and Malone (1999) local-earthquake tomography is in configs/sources.yaml (key moran_1999, L122) and docs/references.bib (L391) and is listed in the profile's research_lineage, yet it is cited nowhere in the paper. Obrebski et al. (2015), Flinders et al. (2017) and Ulberg et al. (2020) appear only in Limitations/Validation (L1213, L1264). P2 will read L48 and ask why existing local tomography does not already "resolve the volcanic edifice". The niche has to be restated as: prior Rainier models are single-property, single-method and not distributed on a common grid with geology, surface and hydrologic layers, and none is reproducible from archives.
- (b) It gives no gap for the non-seismic layers, which are most of the data set. There is no sentence on why soil, water table, vegetation, ice, strain and mass movements need to sit on one grid with Vs. P4, P5 and P6 find no reason in the introduction to read on. The argument exists in the Conclusions (L1237: a water budget on critical-zone columns coupling precipitation, hydrology and seismic properties); it belongs here as motivation.

S-IN.3 Move 3 — PASS with mismatch (L50–55 vs abstract L25–43). The introduction's contribution is the velocity model (three bullets) plus one sentence on everything else. Absent from the introduction but headline items of the abstract: the relocated 2023–2025 catalogue (371 events, median RMS 0.107 vs 0.119 s), the mass-movement catalogue (1,650 events, 463 debris-flow outlines, 3 lahar deposits), the export formats (NonLinLoc, SPECFEM3D, PyLith, EarthScope EMC), the viewer, the CC-BY 4.0 release, and the WRSZ, which the abstract makes part of the model's identity (L25) but the introduction never names or motivates (first body use L76). For ESSD, the intro must say what the reader can do with the data (ESSD calibration row; P6 lens); it does not.

S-IN.4 Objective sentence — PARTIAL (L50). "rainier3d connects these scales in one model with three properties" is the nearest thing to an objective, and it frames the paper as a seismic-velocity paper. There is no single sentence of the form "This paper describes a data set that … so that users can …". Supply one, and make it match abstract L25.

S-IN.5 Why it matters — PARTIAL (L48). "Why" is given only through hazard (two citations) and by implication for monitoring. Concrete uses are not named: earthquake location and monitoring at Rainier (P2), ground-motion and wavefield simulation in the edifice (P2, P6), deformation boundary conditions (P3), lahar and debris-flow initiation on altered, saturated flanks (P4), glacier and snow conditioning of runoff (P5). One sentence listing these, each tied to a layer, answers ESSD's usefulness question.

S-IN.6 Length/load — PASS on length (~1 page), FAIL on content density. The three bullets (L51–53) carry methods and validation detail: 149 symbols, 14 units, 95 % invariant threshold, three cutoff wavelengths with depths, 300/1000 m taper, RMS 0.013 vs tolerance 0.03, pick counts, magnitude range, date range, residuals. These are repeated in sec:domain, sec:fusion, sec:calibration and sec:validation. Keep the claim and one number per bullet; move the rest. Citation load (6 of 123) is light rather than excessive; the deficit is in Move 1–2, not too many references.

S-IN.7 General → specific — PASS overall; minor. No subsections. Order is hazard → method gap → contribution → scope → outline. The "digital model, not digital twin" sentence (L55) is placed among the scope statements; fine, but it would read as positioning if paired with one citation on digital-twin efforts (see S-IN.9). Outline as a table (L59–71) is unusual for Copernicus; a two-sentence roadmap does the job and frees the table count. Outline omits sec:relocation and the viewer, which are reader-facing products (L1151, L1190). Author's choice; low priority.

S-IN.8 Terms at first use — FAIL (minor, clarity only).
- S1, S3, S5, S13 (stage labels) and L1 (level label) are used at L51–53 before they are introduced (L80–91). Terms of art per the profile, so keep them, but add one clause on first use ("numbered scripts S0–S30, [@sec:domain]" and "the finest grid level, L1").
- "invariant test" (L51) undefined at first use; define once or cite tests/test_invariants.py.
- WRSZ never appears in the introduction (see S-IN.3); in Copernicus the abstract does not count as first use.
- CRESCENT and "ln V" are fine for this audience; USGS, PNSN, RMS are expanded.

S-IN.9 Fair and global representation — FAIL (feeds C6; profile stretch).
- No positioning against comparable community or volcano models. Candidates the profile asks to surface (all to verify before citing; none is in configs/sources.yaml as far as grep shows: zero hits for "scec", "etna", "kilauea", "twin"):
  - SCEC Community Velocity Models (CVM-S, CVM-H; Shaw et al., 2015) and the Unified CVM framework (Small et al., 2017), plus the SCEC Community Fault Model (Plesch et al., 2007): the closest analogue for a registry-driven community model with a query client.
  - 3D multi-property models at other instrumented volcanoes, e.g. Mount St. Helens (iMUSH; Kiser et al., 2016), Etna, Kīlauea, Campi Flegrei, and the EU DT-GEO digital-twin component for volcanoes. One sentence plus two or three citations is enough to place rainier3d, and it is the natural home for the "not a digital twin" statement.
  - ESSD precedents for multi-layer regional compilations, and FAIR/data-reuse literature (Wilkinson et al., 2016) to back the reproducibility claim the abstract makes.
- All cited prior work is US federal or state; no non-US model is mentioned. Self-citation: zero group papers in the introduction, so no over-self-citation.

S-IN.10 Citations in reference list — PASS. All six keys resolve in docs/references.bib (L767, 1684, 1695, 1717, 2061, 2092). Side note for S-CI: cvm17_article and hoblitt_1998 are typed @book; check the entry types.

S-IN.11 Number consistency with abstract — FAIL (minor; feeds C7). Intro L53 gives the held-out S residual as 0.186 s; abstract L29 gives 0.187 s. Both exist in the paper: 0.186 is the final S13 iteration (L666, L707), 0.187 is the published model relocated with S14 (L707, outputs/relocation/heldout_published.json). The intro also omits the PNSN 1D baseline (0.131 / 0.263 s), which is the comparison the intro's own gap statement (1D monitoring models) calls for. Use the S14 published-model numbers and the 1D baseline, as in the abstract.

## Tier feed

- C1 (significance / ESSD uniqueness and usefulness): introduction argues uniqueness only for the velocity model and only against regional models; does not argue why the integrated multi-layer grid is needed, does not name uses or users. S-IN.2, S-IN.3, S-IN.4, S-IN.5. Major.
- C6 (citations and idea diversity): Rainier-specific tomography omitted from the gap statement (moran_1999 registered but never cited); no community-model or other-volcano positioning; no FAIR/ESSD precedent; US-only. S-IN.1, S-IN.2a, S-IN.9. Major for P2 and P1.
- C7 (clarity / consistency): method-level numbers in the contribution bullets, stage and level labels before definition, 0.186 vs 0.187 s mismatch, WRSZ absent. S-IN.6, S-IN.8, S-IN.11. Minor.

## Top fixes (ordered)

1. Rewrite the niche (L48) to cite the Rainier-specific imaging (Moran et al., 1999; Obrebski et al., 2015; Flinders et al., 2017; Ulberg et al., 2020) and the comparable community/volcano models (SCEC CVM/CFM; one or two instrumented volcanoes), then state the gap as the absence of a reproducible, multi-property model on one grid that joins subsurface, surface, geodetic and hydrologic layers. (S-IN.2, S-IN.9; P1, P2)
2. Add one objective sentence that matches the abstract and one sentence of uses tied to layers and readers: location and monitoring, wavefield simulation, deformation modelling, lahar and debris-flow initiation, glacier and runoff; name the WRSZ and the relocated and mass-movement catalogues, the formats and the licence. (S-IN.3–S-IN.5; P2–P6)
3. Cut each contribution bullet to its claim plus one number; move cutoffs, taper depths, invariant thresholds and pick metadata to sec:fusion and sec:calibration; use the published-model residuals and the PNSN 1D baseline (0.092/0.187 s vs 0.131/0.263 s) so the intro agrees with the abstract. (S-IN.6, S-IN.11)
4. Introduce S0–S30 and L1–L3 in one clause at first use, define "invariant test", and add a citation for the 1D-monitoring statement once the PNSN 1D model reference is resolved (TODO at L1214). (S-IN.1, S-IN.8)
