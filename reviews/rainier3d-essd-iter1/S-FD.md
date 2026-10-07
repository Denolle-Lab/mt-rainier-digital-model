[S-FD] FIGURES & DATA PRESENTATION
Iteration 1, full first review. Manuscript: docs/paper/rainier3d_paper.md on main @ d61305c (line numbers refer to this file as read in this session).
Target: ESSD data description paper (profile calibration row). Lead lens P1 (ESSD data reviewer); P4 and P6 secondary.
Every figure PNG/PDF the paper includes was opened and inspected (26 files). Figure-to-script mapping by grep of scripts/ and src/ (not rerun). No figure was regenerated.
Verification legend: [IMG] = read off the figure image; [TXT] = paper text only; [GREP] = repository search.

Counts: figures 26 (not 27: the 27th file in docs/paper/figures/, fig21_flood_event.png, is an orphan of the removed December 2025 flood section and is not included) · tables 32 · numbered display equations 17 (6 referenced in text)
Citation order: FAIL. 4 figures and 4 tables never cited; 2 figures and 1 table first cited out of order (S-FD.3).
Caption-interpretation flags: 3 strong (fig:fusion, fig:depthrock, in-figure panel title of fig:pnsn b), 5 mild (fig:surface, fig:terrain, fig:sectionB, fig:strainedifice, fig:canopy).
Color audit: CONCERN. One rainbow (turbo/jet-type) colormap on quantitative data (fig:alteration, four resistivity panels); two categorical maps without a legend (fig:map geology, fig:surface e land cover); red and orange-red unit colours that a deuteranope cannot separate (fig:sectionA d, fig:sectionB c); a diverging map used for one-signed data (fig:strainedifice). Everything else uses perceptually ordered maps (batlow/lajolla/oslo/roma-type).
Label/units completeness: PARTIAL. Units missing on fig:alteration (frequency in Hz, resistivity in Ω m, no panel letters); no x label and clipped y range on fig:strainseries; three coordinate conventions across map figures.

## Figure inventory (order of appearance in the file)

| # | id | file | line | first cited | script [GREP] | main or supplement (recommendation) |
|---|---|---|---|---|---|---|
| 1 | workflow | figures/fig0_workflow.pdf/.svg | 98 | 91 | scripts/23_paper.py (docs/paper/workflow.dot) | main |
| 2 | map | figures/fig1_map.png | 100 | 96 | scripts/10_report.py | main |
| 3 | glaciers | figures/fig2_glaciers.png | 244 | 242 | 10_report.py | supplement |
| 4 | surface | figures/fig8_surface_layers.png | 270 | 248 | 10_report.py | main |
| 5 | depthrock | figures/fig23_depth_to_rock.png | 293 | 291 | 10_report.py | supplement, or merge (c) into fig:surface |
| 6 | canopy | figures/fig14_canopy.png | 317 | 304 | 10_report.py | supplement (and licence, S-FD.12) |
| 7 | terrain | figures/fig22_terrain_geometry.png | 336 | 325 | 30_terrain_geometry.py | main |
| 8 | czsection | figures/fig24_cz_section.png | 499 | 489 | 10_report.py | main |
| 9 | alteration | ../alteration/fig1_em_alteration_maps.png (docs/alteration/) | 581 | 569 | 22_alteration_finn2001.py | main, redrawn |
| 10 | fusion | figures/fig3_fusion.png | 606 | 604 | 10_report.py | supplement (fig:sectionA shows the fused result) |
| 11 | calibration | figures/fig10_calibration.png | 694 | 671 | 16_relocation_figures.py | main |
| 12 | law | figures/fig11_geology_law.png | 696 | 671 | 16_relocation_figures.py | supplement |
| 13 | residuals | figures/fig12_relocation_residuals.png | 722 | never | 16_relocation_figures.py | supplement (tbl:models carries the numbers) |
| 14 | imush | figures/fig13_imush.png | 740 | never | 21_compare_imush.py | main if cited (independent quality check), else supplement |
| 15 | pnsn | figures/fig7_pnsn.png | 744 | 742 | 10_report.py | supplement |
| 16 | sectionA | figures/fig4_section_AA.png | 756 | 748 | 10_report.py | main |
| 17 | sectionB | figures/fig5_section_BB.png | 758 | 748 | 10_report.py | main |
| 18 | profiles | figures/fig6_profiles.png | 760 | 748 | 10_report.py | supplement |
| 19 | strainseries | ../gnss/strain_series.png (docs/gnss/) | 808 | 797 | none found [GREP] | supplement |
| 20 | strain | figures/fig15_strain.png | 828 | 793 | 10_report.py | main |
| 21 | strainwrsz | figures/fig16_strain_wrsz.png | 857 | 855 | 25_strain_volume.py | main |
| 22 | strainedifice | figures/fig17_strain_edifice.png | 878 | 868 | 25_strain_volume.py | supplement |
| 23 | strainorient | figures/fig18_strain_orientation.png | 891 | 881 | 25_strain_volume.py | supplement |
| 24 | mass | figures/fig16_mass_movements.png | 1053 | 239 | 24_mass_movements.py | main |
| 25 | relocated | figures/fig19_relocated_catalogs.png | 1186 | never | 26_relocate_catalog.py | main if cited |
| 26 | relshift | figures/fig20_relocated_shifts.png | 1188 | never | 26_relocate_catalog.py | supplement |

Proposed split: 13 in the main text (workflow, map, surface, terrain, czsection, alteration, calibration, imush, sectionA, sectionB, strain, strainwrsz, mass, relocated; drop one of imush/relocated if a 12-figure budget is wanted) and 12 to a supplement. ESSD sets no figure cap, but the review question is "does the article let a reader use the data". The main-text figures should show coverage and quality of each product released in tbl:products. Figures that show intermediate steps (fusion inputs, the crack-closure law, residual histograms, profiles, strain orientation at six levels) are method diagnostics, so they go to the supplement.

## Table inventory

32 tables: outline, grids, raw, ai, env, soil, canopy, terrain-mass, units, czlayers, rules, dmuthick, alteration, invariant, iterations, multipliers, bias, models, imush, strain, swarms, load, wrsz, edificestrain, hydro, wells, mass-counts, mass, products, formats, relocation, datasets.
Never cited: tbl:outline (l.71), tbl:ai (l.217), tbl:czlayers (l.467), tbl:datasets (l.1296).
Unresolved TODOs inside tables: tbl:swarms (l.801-802, two cells), tbl:products (caption l.1092), tbl:datasets (l.1266, 1270, 1271, 1275, 1288, 1294).

## Equation inventory

17 numbered: crack 366, vg 401, sigeff 403, hm 412, gassmann 422, blend 430, windex 471, alteration 565, fusion 592, residual 639, objective 641, gn 647, raykernel 653, tectdepth 902, resolved 909, boussinesq 919, compliance 926.
Referenced with @eq: crack, sigeff, fusion, objective, compliance, tectdepth (6). The other 11 are numbered and never referenced. Copernicus numbers every display equation, so this is acceptable. Note it only because two equations are also written out a second time inline (S-FD.9).

## Findings

S-FD.1 PARTIAL (each figure earns its place; ESSD balance). 26 figures and 32 tables is about twice what an ESSD data description carries. The surplus is mostly method diagnostics: fig:fusion (l.606) shows the same section as fig:sectionA (l.756) plus its two inputs; fig:law (l.696), fig:residuals (l.722), fig:pnsn (l.744), fig:profiles (l.760), fig:strainorient (l.891) and fig:relshift (l.1188) each support one or two sentences. On the other side, P1 looks for a coverage/quality figure for every released product. Those exist for model, alteration, strain_3d, mass_movements and gnss. They are missing for the `grids` product, which is a resampling and needs none, and for `edifice_load`, which fig:strain b covers. The relocated catalogue, a separate release (l.1241), has fig:relocated but it is never cited. Recommendation: the split in the inventory table, with a supplement (ESSD allows one) that keeps the scripts that draw each figure.

S-FD.2 PARTIAL (same data shown twice). Pairs where a table and a figure carry the same numbers:
- tbl:bias (l.687-692) and fig:calibration a (l.694);
- tbl:imush (l.730-738) and the dotted lines of fig:imush a-c (l.740);
- tbl:models (l.711-720) and the RMS labels of fig:residuals (l.722).
Text duplicates:
- tbl:hydro (l.970-983) repeats medians from tbl:env, tbl:soil and tbl:canopy;
- tbl:mass (l.1065-1072) repeats the bullet list at l.1057-1063;
- tbl:edificestrain (l.872-876) and tbl:load (l.817-824) give the same column beneath the summit at overlapping elevations, so they could be one table.
For ESSD, keep the tables (exact values for reuse) and move the twin figures to the supplement. Merge tbl:hydro into a pointer table (layer, product variable, section) without repeating the statistics.

S-FD.3 FAIL (citation order). pandoc-crossref numbers figures and tables in order of placement.
- Never cited: fig:residuals (l.722), fig:imush (l.740), fig:relocated (l.1186), fig:relshift (l.1188); tbl:outline, tbl:ai, tbl:czlayers, tbl:datasets.
- fig:mass is placed 24th but first cited at l.239 (Faults bullet, "[@fig:mass]a"), before Fig. 3. Either move the fault traces to fig:map or drop the forward citation and say "Sect. [@sec:mass]".
- fig:strain (placed 20th, l.828) is first cited at l.793, before fig:strainseries (19th, l.808, first cited l.797). Swap their placement.
- tbl:mass (l.1072) is first cited at l.1018, before tbl:mass-counts (l.1051, first cited l.1033). Swap their placement.
Copernicus requires every figure and table to be cited in order. The uncited figures are a likely technical-correction request.

S-FD.4 FAIL (captions descriptive, not analytical). Strong flags:
- fig:fusion (l.606): "The fused model keeps the regional long wavelengths and the geological contrasts: the Puget Group sedimentary block near 572–582 km, the Tatoosh and White River plutons, and the slow edifice." This is a result statement. Move it to l.604. The panel (c) title "Fused model: long wavelengths of b, short wavelengths of a" [IMG] is acceptable as a definition.
- fig:depthrock (l.293): "The order-of-magnitude gap between the two depths contains the water table." This is the conclusion of l.291. Drop it from the caption.
- fig:pnsn panel (b) title on the image: "Station terms explained by the 3D model" [IMG]. Replace with "Station-mean 3D − 1D delay against 1D residual".
Mild flags (explanations of artefacts or limitations; acceptable in ESSD, but they lengthen captions):
- fig:surface l.270, "comes from the canopy product itself";
- fig:terrain l.336, last sentence on effective resolution, inherited errors and adjustable radii. This repeats l.334 and is limitation text, not a description;
- fig:sectionB l.758, "marks the change from the Cascadia model to CRESCENT";
- fig:strainedifice l.878, "the confined overburden makes it vertical";
- fig:canopy l.317, "Straight edges ... are lidar tile boundaries".
Captions that describe less than the figure shows:
- fig:workflow l.98 says "Inputs (left) ... model chain (middle) ... checks and products (right)", but the graph [IMG] runs top to bottom: inputs at the top, products at the bottom. It also says "calibration (blue)", yet S4 and S5 are blue too. The graph omits S6-S8, S24-S26 and S28-S35, although the mass-movement catalogue, the relocated catalogue and the wells are released or described products.
- fig:calibration l.694 says "(b) Median and 5–95% range of Vp/Vs of the fused model", but four models are plotted [IMG], and the vertical "Qp = 2Qs limit" line (1.63) is not described.
- fig:czsection, fig:strain b: blank regions are not described. In fig:strain b, nodes above 1539 m are empty because the point-load field is singular there (l.814). Say so in the caption.
- fig:strainwrsz: the white patch in the NW corner of (a) and (b) [IMG] is unexplained. The caption says bars are "length scaled with the shear rate", but the bars look uniform [IMG].
- fig:profiles l.760: the profile locations (Longmire, WRSZ) are not given in coordinates or on fig:map.

S-FD.5 PARTIAL (labels, units, legends).
- fig:alteration [IMG]:
    - panel titles "33k", "4737", "4341", "837" have no Hz;
    - the four resistivity colorbars have no label (log10 Ω m);
    - no panel letters; the caption names the panels by content only;
    - white tick artefacts on the left edge of the 33k, 4737 and 4341 panels;
    - the map extent (about 581-603 km E, 5182-5197 km N) is a fraction of the box and is not stated.
- fig:map [IMG]:
    - no legend for the 14 surface model units; the caption names them only as "surface model units", so P4/P5 cannot read the background;
    - event depth reference (below sea level or below ground) not stated;
    - legend counts are not in the text and partly disagree with it (S-FD.11).
- fig:surface [IMG]:
    - panel (e) land cover has no class legend;
    - colorbars carry no label; units are in panel titles, which is acceptable, but (f) shows a hillshade under coloured streams that are hard to see at print size.
- fig:strainseries [IMG]:
    - no x-axis label, no panel letters;
    - y limits clip data in both panels (WRSZ at ±80, edifice at −1800 nanostrain); the 30-day median goes off-scale near 2023. This bears on the open TODO at l.806 about the 2335-nanostrain excursion.
- fig:relocated, fig:relshift [IMG]:
    - default matplotlib style;
    - axes "easting (km)" and "northing (km)" run 0-70 and 0-75 relative to the box corner, a third coordinate convention; the origin is not stated;
    - panel titles read "summit +-5 km";
    - fig:relshift has no (a)/(b) on the image although the caption uses them.
- fig:profiles, fig:strainorient: no panel letters.
- fig:law legend says "placeholder" while the caption says "table". Unit names are lower-case ("rainier andesite", "miocene intrusive").
- Unit names differ between tbl:units (l.374-389) and the legends of fig:sectionA d and fig:sectionB c [IMG]:
    - "eocene sedimentary" versus "Puget Group, Eocene sedimentary rocks";
    - "miocene sedimentary" versus "Mashel Formation";
    - "miocene volcanics" versus "Miocene volcanic rocks".
  A reader cannot map the unit codes stored in model.zarr to either list without configs/units.yaml. Add the code to tbl:units, or use one naming everywhere.

S-FD.6 PARTIAL (consistent scales across figures meant to be compared).
- Three horizontal coordinate conventions:
    - UTM km: fig:map, fig:fusion, fig:sectionA/B, fig:mass, fig:alteration;
    - km from the summit: fig:surface, fig:depthrock, fig:canopy, fig:terrain, fig:czsection, fig:strain, fig:strainwrsz, fig:strainedifice, fig:strainorient;
    - km from the SW box corner: fig:relocated, fig:relshift.
  Pick two at most (UTM for full-box maps, summit-relative for zooms) and state the summit UTM in every summit-relative caption.
- Vs colour range: 500-4000 m/s in fig:fusion and fig:sectionA b, but fig:czsection b uses a log scale of about 150-3500 m/s. That difference is reasonable, but say so.
- Water table: fig:surface b, c use a log 1-100 m scale. Fan et al. (2017) is deeper than 100 m in 27% of the box (l.987), so panel (c) saturates over a quarter of the cells and the caption's "same logarithmic scale" hides it. Extend the scale to 1000 m or mark the saturation (extend arrow).
- Vertical extent: fig:fusion and fig:sectionA/B stop at −12 km, while the model reaches −20 km (tbl:grids) and the CRESCENT switch lies in the hidden part of B-B′ for parts of the section. State the cut in the captions.

S-FD.7 CONCERN (colour).
- fig:alteration uses a turbo/jet-type rainbow, reversed (red = conductive), on log apparent resistivity in four panels [IMG]. This is the one clear failure. Replace it with a sequential perceptual map (e.g. batlow or lajolla, as elsewhere in the paper) with a labelled colorbar.
- fig:sectionA d and fig:sectionB c: "rainier andesite" (salmon) and "miocene intrusive" (brick red) differ mainly in hue on the red-green axis, so they are hard to separate for deuteranopes. Magma mush (magenta) against miocene intrusive is also close in a greyscale print. Change one hue or add hatching.
- fig:residuals: five overlapping step histograms, three of them blue/purple (S12 purple, S13 v1 light blue, S13 blue) [IMG]. They are unreadable in greyscale and close for tritanopes. Show fewer models, or use line styles.
- fig:strainedifice: a diverging symmetric-log map is used for strain that is negative everywhere (l.866-867). Half the colorbar is unused. A one-sided sequential map gains contrast.
- fig:fusion, fig:sectionA a-b, fig:sectionB a, fig:czsection b use a roma-type diverging map (brown-yellow-blue) for Vs, which has no meaningful midpoint. It is CVD-safe, so this is minor, but a sequential map would read more naturally.
- Not assessable at review resolution: colour-vision simulation of fig:mass b (red/yellow/black chevrons) and fig:strainorient (batlow-type log map with grey overlays). Run a CVD simulator on the final PDFs.

S-FD.8 PARTIAL (tables: who, what, where, when, how many, units, source).
Strengths: tbl:raw, tbl:env, tbl:soil and tbl:canopy each give source, native resolution and statistic with the window. Most tables name the output file that holds the numbers (`outputs/...`). P1 can trace them.
Gaps:
- tbl:products (l.1082-1092) has no DOI, version, format or licence column, and its caption is a TODO. It is the table P1 opens first.
- tbl:datasets (l.1254-1296) has no licence and no persistent-identifier column, and six rows are TODOs.
- tbl:raw lists no retrieval date or version per source, although the text freezes queries at 23 September 2026 (l.182). One column would serve P1 and P6.
- tbl:strain gives ± for dilatation only. The maximum shear and the azimuth of ε̇₁ have no uncertainty. tbl:wrsz has none.
- tbl:czlayers and tbl:rules carry units only in the cell text.
- tbl:invariant mixes signed and unsigned values (l.610-612: "+0.000" against "0.0002").
- tbl:swarms has two "[TODO: not reproduced]" cells (l.801-802). The table cannot go to review in that state.
- tbl:ai (l.205-217): the development record belongs with the AI statement or the supplement, not among the data tables, and it is uncited.
- tbl:outline (l.59-71): a navigation table is unusual in Copernicus papers and duplicates the TOC. Drop it.

S-FD.9 PARTIAL (equations).
- Two relations are written twice:
    - plane stress, inline at l.838 and as eq:tectdepth at l.902;
    - the confined overburden of the cone, at l.863 and l.929.
  Keep one and reference it.
- eq:sigeff (l.403) uses W before it is defined (eq:windex, l.471). Add "W, the weathering index of eq:windex".
- eq:gassmann (l.422): K_d (dry-frame modulus) and φ_g are named only implicitly. The Brie exponent is written $S^{e}$ with e = 3 (l.420), and e collides with Euler's e used in eq:crack.
- Inline Brocher relations (l.368, l.587) and the Q rule (l.369) are unnumbered but central. Number them so that tbl:units can point to them.
- Units are given for most constants. In eq:objective, σ_ph is defined at l.640 and λ_s is chosen at l.656. That is fine.
Cross-check S-ME for the physics.

S-FD.10 PARTIAL (data and code behind each figure).
- Every figure but one maps to a committed script [GREP]. docs/gnss/strain_series.png (fig:strainseries) has no writer in scripts/, src/ or .github/ [GREP for "strain_series"]. A copy sits in outputs/gnss/, so it was produced by some run, but the figure cannot be traced to code from the repository. P1 and S-RP will flag it.
- fig:alteration and fig:strainseries are pulled from docs/alteration/ and docs/gnss/ rather than docs/paper/figures/. This works only if pandoc's resource path includes docs/. The committed HTML embeds the images, so the build works today [read from rainier3d_paper.html, not rebuilt], but the layout is fragile for an ESSD upload, where all figures must be supplied as separate files.
- Captions name the stage (S-number) for most figures but not the product variable or file. For ESSD, add one clause per caption, e.g. "(`model.zarr`, node L1, variable vs)", so that a reader can redraw the figure from the deposit.
- docs/paper/figures/fig21_flood_event.png is an orphan (no reference in the paper). Delete it, or the supplement will pick up a figure of a removed section.

S-FD.11 FAIL (figure content against text numbers). Read off the images [IMG] and compared with the text [TXT]. The ones a referee will catch:

| Item | Figure says | Text or table says | Where |
|---|---|---|---|
| P picks | fig:pnsn a title "1828 picks" | 1823 P picks | l.29, 53, 618 |
| S RMS, Vs-only model (S12) | fig:residuals b "RMS 0.189 s" | 0.190 s | tbl:models l.715 |
| Events above ground, 1D model | fig:relocated bottom-middle "1 above ground" | "4, pinned at the mask" | tbl:relocation l.1172, l.1180 |
| Slides, debris slides | fig:mass b legend "(323)" | 324 | tbl:mass-counts l.1048, tbl:terrain-mass l.345 |
| 2025 nodes | fig:map legend "2025 nodes (240)" | 191 nodes in the domain (l.509); 813 geophone nodes in the viewer (l.1195) | l.509, l.1195 |
| Seismometers | fig:map legend "Seismometer (42)" | 46 permanent stations (l.509); 45 stations with picks (l.1157) | l.509 |
| Graded events | fig:relocated titles "344 events, A+B" in all three columns | 340 graded A/B in both models | tbl:relocation caption l.1176 |

The slide count of 323 matches the current outputs/mass_movements/events.csv, dated 5 October 2026 (S-AB F16), while the table cites the run of 2026-09-25. The figure and the table come from different runs of S24.
Related text-to-text inconsistencies found while checking figures (for C2; S-RE/S-CO may also list them):
- Conclusions l.1232, "V₀ is raised by 31%", against the adopted ×1.47 (l.673, tbl:multipliers); 31% is the superseded calibration without the critical zone.
- Conclusions l.1235: "median RMS falls from 0.119 to 0.109 s" against 0.107 (tbl:relocation), and "no event lies above the ground" against "1, 12 m" (tbl:relocation, abstract l.31).
- Limitations l.1212: top 300 m "21% faster in Vp and 30% in Vs", against 23% and 31% (l.677, l.750).
- Limitations l.1219: "12 events stop at the base", against 10 (l.1163, tbl:relocation).
- tbl:raw l.132: "the 91 calibration events", against 88 everywhere else.
- Conclusions l.1232, "regional Vs 5–9% too slow at 2–7 km", against tbl:bias factors 1.045-1.081 (4.5-8.1%) and l.676 "5–8%".

S-FD.12 CONCERN (licences of what the figures show; P1). Copernicus publishes figures under CC-BY 4.0.
- fig:surface b and fig:depthrock c show the Ma et al. (2026) water table, block-averaged by S2. Its licence is CC-BY-NC-ND 4.0 and the paper itself excludes the layer from the products because the licence forbids derivatives (l.189, l.991). A resampled map in a CC-BY figure is the derivative the paper withholds elsewhere.
- fig:canopy a, b show the Washington DNR "Wali" lidar layers, whose terms of reuse are "not yet confirmed" (l.190, tbl:canopy caption l.315).
Fix: obtain written permission and state it in the caption, or replace the panels: Fan et al. alone for the water table, and GEDI/ETH alone for canopy height and cover.

## Persona notes
- P1: stops at tbl:products (no DOI, TODO caption), at the four uncited figures, and at fig:strainseries (no script).
- P4: cannot read the geology on fig:map or the land cover on fig:surface e without legends.
- P6: meets three coordinate conventions and cannot map unit names between tbl:units, the section legends and model.zarr codes.

## Tier feed
- C2 (data quality, evidence): S-FD.11 (7 figure/text mismatches plus 6 text/text mismatches) and S-FD.12 (licence of displayed layers). One concern: fig:strainseries cannot be regenerated from committed code (S-FD.10).
- C5 (presentation): S-FD.1 (26 figures, 32 tables, about half method diagnostics), S-FD.3 (citation order and 8 uncited items), S-FD.4 (2 analytical captions, plus the workflow caption describing a layout the figure does not have), S-FD.5/6 (units, legends, three coordinate frames), S-FD.7 (rainbow map on fig:alteration).

## Top fixes (ordered)
1. Reconcile the numbers in S-FD.11. Redraw fig:pnsn, fig:residuals, fig:relocated and fig:mass from the same runs the tables cite, and correct the Conclusions and Limitations lines to the adopted model.
2. Cite every figure and table in placement order: cite or drop fig:residuals, fig:imush, fig:relocated, fig:relshift; swap fig:strain/fig:strainseries and tbl:mass/tbl:mass-counts; remove the forward citation of fig:mass at l.239. Then move the 12 diagnostic figures listed in the inventory to an ESSD supplement.
3. Redraw fig:alteration in the house style: panel letters, Hz and Ω m labels, a perceptual colormap, and extent stated. Add legends for the units on fig:map and the land-cover classes on fig:surface e. Put fig:strainseries under a committed script with axis labels and unclipped limits.
4. Resolve the licence of the displayed Ma et al. and DNR lidar panels (S-FD.12). Fill tbl:products with version, DOI, format and licence, and remove the TODO cells in tbl:swarms.
