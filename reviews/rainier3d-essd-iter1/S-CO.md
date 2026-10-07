# [S-CO] CONCLUSIONS — iteration 1

Source: `docs/paper/rainier3d_paper.md` on main @ d61305c (read only, nothing rerun). Conclusions = lines 1228–1237;
Code and data availability = lines 1239–1250. Journal row: ESSD (profile `denolle-rainier3d.md`). Lead lens P1
(ESSD data reviewer). Every check below was made by reading the manuscript and, where stated, the repo files; no
script was rerun.

```
Pols 7-element score: 4/7 (elements 2 and 4 full; 1, 5, 6, 7 half; 3 missing)
Independently readable: PARTIAL (V0, "table rock", S−P, iMUSH, critical-zone columns undefined here)
New content introduced (element-8 failure): Y
  - "in rainier3d no event lies above the ground" (contradicts tbl:relocation, l.1172: 1 event, 12 m)
  - "median RMS falls from 0.119 to 0.109 s" (body and abstract: 0.107 s, l.1170, 1178, 31)
  - "V0 is raised by 31%" (stale: adopted calibration is x1.47, l.671, tbl:multipliers; 1.31 is the
    superseded no-critical-zone fit)
  - "regional Vs ... 5–9% too slow at 2–7 km" (tbl:bias gives 1.045–1.081, i.e. 4.5–8.1%; body text says 5–8%, l.676)
  - "One layer carries time, the mass-movement catalogue" (characterisation appears nowhere in the body and
    conflicts with l.55 "Only the GNSS product is refreshed on a schedule")
  - "a water budget on the critical-zone columns" as next step (phrase absent from body; body already runs an
    MRMS-driven Richards solver on those columns, S34, l.510–515)
Verbatim intro/abstract reuse: N
```

## Findings

| ID | Verdict | Location | Finding |
|---|---|---|---|
| S-CO.1 | PARTIAL | l.1232 | Readable alone only for a reader who has just read §Calibration. "V₀", "table rock", "S−P", "iMUSH" and "critical-zone columns" (l.1237) are not glossed. P1 and P4/P5 reading abstract then conclusions cannot decode the subsurface bullet. |
| S-CO.2 | PASS | l.1230 | Goal restated in one sentence, not copied from the intro. |
| S-CO.3 | FAIL | l.1230–1237 | No reminder of the problem the intro sets (l.48: monitoring on 1D models with station corrections; regional 3D models that do not resolve the edifice, its altered core or its glaciers). Without it the calibration and relocation results have no "why". |
| S-CO.4 | PASS | l.1232, 1237 | Method stated briefly: scripted, checksummed compilation; geology-driven model fused with regional tomography; Gauss–Newton calibration with 3D relocation; NonLinLoc relocation in both models. |
| S-CO.5 | PARTIAL | l.1232–1235 | Answers stated for subsurface and relocation; the iMUSH comparison is the one literature reference value. Missing the headline validation number that the abstract and intro both lead with (held-out RMS 0.120→0.092 s P, 0.316→0.186/0.187 s S; tbl:iterations l.662–667) and any number for strain (10 nanostrain/yr right-lateral, l.849) or the mass-movement catalogue (1,650 events, 463 debris-flow outlines, tbl:mass-counts). The critical zone (§sec:cz, its own `/cz` node and refitted calibration) is not mentioned at all, although it changed V₀ from 1.31 to 1.47. |
| S-CO.6 | FAIL | l.1232, 1235 | Of the four numbers given, two contradict the body and one is stale: (a) "no event lies above the ground" vs tbl:relocation l.1172 and abstract l.31 ("1, 12 m"); (b) median RMS 0.109 s vs 0.107 s (l.1170, 1178, abstract l.31); (c) V₀ +31% vs adopted x1.47 (+47%), l.671 and tbl:multipliers; (d) Vs 5–9% vs 5–8% (l.676) / 4.5–8.1% (tbl:bias). A P2 reader cross-checking against tbl:relocation will stop at (a). |
| S-CO.7 | PARTIAL | l.1237 | Two next steps given (digitised literature events; water budget on the critical-zone columns). The second is phrased as if no coupling exists, while §cz (l.509–515) already drives the columns with MRMS rain through a Richards solver (S34) and predicts dv/v; Limitations l.1223 says "no process of the model responds to precipitation", which also conflicts with S34. The highest-value fixes named in Limitations are absent: replacing `m1_placeholder` parameters, a laterally varying regional correction (l.1211), deep calibration coverage (l.1213), relocating the 500 older above-ground ComCat events (l.1219). |
| S-CO.8 | FAIL | l.1235, 1237 | New/unsupported content listed above under element-8. |
| S-CO.9 | FAIL | l.1237 | Three overgeneralisations. (i) "all but four are fetched by script": §data l.152–156 lists four groups, but l.182 names four *more* inputs staged from a project machine (DAS table, two KMZ overlays, Synoptic catalogue), and l.1225 adds the lidar grids made in QGIS and delivered GEDI L2B/L4B and soil map. The count is at least eight items, and "four" holds only if the canopy group is one. The abstract (l.25) repeats "four". (ii) "Every parameter names its source": true only formally; many name `m1_placeholder` (l.1208). The profile's never_change protects the Limitations' candour about placeholders; the conclusions should not undo it. (iii) "every product ... in the formats that seismological codes read": the eikonal/NonLinLoc/SPECFEM3D/PyLith/EMC writers apply to the velocity model and grids, not to `mass_movements`, `gnss` or `alteration` (tbl:products l.1084–1090). |
| S-CO.10 | PASS | l.1230 | No "In conclusion"; no verbatim reuse. |
| S-CO.11 | PARTIAL | l.1230–1237 vs l.25–43, 48–55 | Contribution framing matches (integration of subsurface, surface, geodetic, hydrologic layers on one grid). Number mismatches with the abstract on relocation (above-ground count, median RMS). Separately, the intro gives held-out S RMS 0.186 s (l.53) and the abstract 0.187 s (l.29): tbl:iterations has 0.186 at iteration 4 (held-out) and 0.187 at "final (all events)" — pick one and say which row. |

## Code and data availability (P1 lens)

| ID | Verdict | Location | Finding |
|---|---|---|---|
| S-CO.12 | FAIL (ESSD blocking) | l.1241 | No DOI. Products are GitHub release assets; Zenodo records are "to be deposited" with a TODO, and no `v1.0.0` software tag exists. ESSD requires a persistent identifier accessible to reviewers at submission. `scripts/27_zenodo_deposit.py` exists, so the deposit is mechanical. |
| S-CO.13 | FAIL | l.1241 vs l.1092 | Version mismatch: availability names `products-v1.0.0`; the caption of tbl:products carries "[TODO: sizes and contents of products-v1.1.0, the first release under this rule]". P1 cannot tell which release the paper describes. |
| S-CO.14 | FAIL | l.1241 | Licence of `relocated-catalog-2023-2025-v1` and `storms-dec2025-v1` is a TODO. Both are products the abstract advertises (relocated catalogue; storm in the viewer). Inputs with no recorded licence (CRESCENT Gen0, IceBoost v2, RGI 6.0, GlaThiDa, Synoptic, Fan 2017, WGS landslide inventory; l.1224, 1227) bear on whether the CC-BY 4.0 claim for derived products holds. |
| S-CO.15 | PARTIAL | l.1241 | `SHA256SUMS` is a release asset (`docs/products.md` l.5, `scripts/20_publish_products.py`), not a repo file; the sentence reads as if it sits next to `src/rainier3d/products.json`. Say "the release asset SHA256SUMS". Seven products verified in `src/rainier3d/products.json` (model, grids, strain_3d, edifice_load, alteration, mass_movements, gnss), matching the text. |
| S-CO.16 | FAIL (minor) | l.1245–1248 | "Two inputs require attribution notices" followed by three bullets. |
| S-CO.17 | PARTIAL | l.1250 | AI-assistant statement present and points to §ai; DOI check has a TODO on three keys taken from memory (brocher_2005, glathida, rgi60). Data sets appendix has five TODO rows without a citable reference (PNSN 1D, DAS table, soil-map image, National Map imagery, Synoptic licence): report under JOURNAL-SPECIFIC NOTES per the profile. |

## Tier feed

- **C1 (significance / ESSD uniqueness, usefulness, completeness):** the conclusions sell the integration but omit the critical zone and give no number for strain or mass movements, so the completeness case is weaker here than in the abstract. Missing problem statement (S-CO.3) leaves usefulness implicit.
- **C4 (evidence → conclusion alignment):** four numeric mismatches in five lines (S-CO.6), plus the "all but four" count (S-CO.9i), the abstract/intro S-RMS split (S-CO.11), and the precipitation-coupling contradiction among §cz, Limitations and Conclusions (S-CO.7). Each is a rewrite of a number, not new analysis.
- **C7 (data/code availability, ESSD policy):** no DOI and no reviewer-accessible persistent deposit (S-CO.12) is non-compliant as written; version mismatch (S-CO.13) and missing licences (S-CO.14) follow.

## Top fixes (ordered)

1. **Make the conclusions' numbers the body's numbers.** l.1235: "one event lies 12 m above the ground, against four pinned at the topography in the 1D model, and the median RMS of the 340 grade A and B events falls from 0.119 to 0.107 s" (tbl:relocation). l.1232: "V₀ is raised by 47% (×1.47; ×1.31 without the critical zone)" and "5–8% too slow at 2–7 km" (tbl:bias, l.676). Add the held-out RMS from tbl:iterations, choosing 0.186 or 0.187 s consistently with abstract and intro.
2. **Deposit before submission.** Run the Zenodo deposit (`docs/doi.md`, `scripts/27_zenodo_deposit.py`), tag software `v1.0.0`, put concept and version DOIs in l.1241, settle `products-v1.0.0` vs `v1.1.0`, and state the licence of the relocated-catalogue and storm releases.
3. **Correct the scope claims in l.1237.** Count the inputs not fetched by script the same way in §data (l.152, l.182), Limitations (l.1225), abstract (l.25) and here; replace "every parameter names its source" with a clause that admits the `m1_placeholder` values; restrict "formats that seismological codes read" to the model and grids. Replace "One layer carries time" (or drop it) so it agrees with l.55.
4. **Add one opening sentence of context and rewrite the future-work sentence.** Context: 1D monitoring models and kilometre-scale regional models do not resolve the edifice. Future work: draw from Limitations (lateral regional correction, placeholder replacement, deep and near-surface calibration, older above-ground events, digitised events), and phrase the hydrology step as extending the S34 Richards columns (lateral drainage, snow) rather than as new; fix l.1223 to match S34.
