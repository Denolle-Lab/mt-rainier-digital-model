```
[S-CD] CITATION & IDEA DIVERSITY  (surfaced, not scored)
```

Manuscript: `docs/paper/rainier3d_paper.md` on `main` @ d61305c; bibliography `docs/references.bib`; registry
`docs/citations.csv`. Read-only pass. All counts below were computed by parsing the paper's Pandoc `@key` citations
(cross-reference labels `sec:`, `tbl:`, `fig:`, `eq:` removed, HTML comments stripped) and joining them to the bib
entries. Field, country and venue labels were assigned by hand from the bib metadata, not from OpenAlex (no OpenAlex
query was run): every inferred label is flagged for human check.

**Profile citation_values:** axes on = geographic, temporal, venue, self-citation, discipline | CDS optional |
self-cite flag yes | identity inference no | underrepresented-group surfacing no | stretch: comparable community and
volcano models, ESSD precedents, FAIR literature.

## Counts

| Quantity | Value | Source |
|---|---|---|
| Distinct keys cited in the paper | 118 | parse of paper |
| Citation instances | 258 | parse of paper |
| Bib entries | 178 | `docs/references.bib` |
| Bib entries not cited in the paper | 60 | join |
| Cited keys missing from the bib | 0 | join |
| Kind of cited item: journal article / USGS or agency report / book / data set, service or software | 63 / 12 / 4 / 39 | bib `@type` plus hand check |
| `[TODO: ...]` markers in the paper | 19 (9 about a citation, licence or DOI) | `grep TODO` |

## S-CD.1 Self-citation (flag_over_self_citation: yes)

| Definition | Keys | Share of 118 keys | Share of 258 citations |
|---|---|---|---|
| Papers with Denolle as author | `ni2023`, `kharita_2026`, `clements_denolle_2023`, `shi_2026` | 4 (3.4%) | 6 (2.3%) |
| Plus group-produced data or code with no named author (Gaia Hazlab repositories, co-author Köpfli's canopy grids) | + `seis_hydro_2_sed`, `synoptic_catalog`, `canopy_lidar_chm` | 7 (5.9%) | 12 (4.7%) |

Verdict: not over-self-cited. Each Denolle paper is cited where its product is used (PNSN picks and catalogue,
relocation, the December 2025 flood work). No flag.

One related observation, not a self-citation issue: `canopy_lidar_chm` points to
`https://github.com/koepflma/canopy-storage_seismic` marked "(private)" in its `howpublished` field and is
`verified = no` in `docs/citations.csv`. A cited source that readers cannot open is a P1 (ESSD data reviewer)
problem. Passed to S-FD and S-RP.

## S-CD.2 Temporal spread

Literature only (79 keys: articles, reports, books). Data-set entries are excluded because their `year` field holds
the access year of a live service (2025 or 2026), not the vintage of the data.

| Publication years | Count |
|---|---|
| before 1980 | 7 |
| 1980–1999 | 21 |
| 2000–2009 | 8 |
| 2010–2019 | 20 |
| 2020–2023 | 11 |
| 2024–2026 | 12 |

Range 1949 (Mindlin) to 2026; median 2014. No recent-skew and no frozen-classic flag: the pre-2000 block is the
mechanics canon (Mindlin, Biot, Hill, Walton, van Genuchten) and the Rainier field record (Crandell, Fiske, Scott,
Vallance, Hoblitt), both used for what they established.

Thin decade: 2000–2009 has 8 references. Not a defect on its face; it is where the Rainier geophysics literature
between Moran 1999 and Ulberg 2020 would sit, which S-CD.8 and fix F3 come back to.

Data-set dating: 5 cited `@misc` entries have no year at all (`canopy_lidar_chm`, `earthscope_gnss`, `nhdplus_v21`,
`seis_hydro_2_sed`, `synoptic_catalog`). Copernicus reference style needs a year or access date. P4 and P5 will ask
for the vintage of each layer, which an access year does not give.

## S-CD.3 Venue concentration

| Measure (79 literature keys) | Value |
|---|---|
| Distinct venues | 47 |
| Top venue: JGR Solid Earth | 9 (11%) |
| USGS series combined (Open-File Report, Professional Paper, SIR, other USGS) | 11 (14%) |
| Normalised Shannon entropy of venue shares | 0.94 (1 = every reference in a different venue) |

No concentration flag. Among the 39 data and service entries, US federal agencies (USGS, NASA DAACs, NOAA via
MRMS) and Washington State agencies (DNR, Washington Geological Survey, Department of Ecology: 6 entries) dominate.
That follows from the domain and from the ESSD requirement to cite the originating archive; it is not a choice the
authors could easily diversify.

## S-CD.4 Geographic spread (inferred, human-verify)

First-author or issuing-body country, assigned by hand from names, publishers and known institutions; not resolved
from affiliations.

| Country of first author or issuing body | All 118 keys | 79 literature keys |
|---|---|---|
| USA | 101 | 68 |
| Switzerland | 5 | 3 |
| France | 3 | 3 |
| UK | 3 | 3 |
| European Space Agency | 2 | 0 |
| Italy | 1 | 0 |
| China / Netherlands (SoilGrids, ISRIC) | 1 | 1 |
| International consortium (RGI) | 1 | 0 |
| Industry (Brie et al., SPE) | 1 | 1 |

About 86% US-led. Expected for a site-specific data paper on a US volcano that cites US archives, and not a
deficiency. Where non-US work enters it is through global products (SoilGrids, RGI, GlaThiDa, IceBoost, ETH canopy
height, Sentinel-2) and methods (Kissling 1994 VELEST, Lomax 2000 NonLinLoc, Solazzi 2021, Pasquet 2015, Heap and
Violay 2021). The opt-in suggestions in F4 would widen this only where the citation does a job in the paper.

Human-verify: every country in this table; `iceboost_v2` (Maffezzoli) assigned to Italy, `shen_2015_strain`
assigned to the US, `soilgrids_bdticm_article` split China/Netherlands.

## S-CD.5 Interdisciplinary reach (informational, inferred)

23 field labels across the 118 keys. Top ten:

| Field (hand-assigned) | Keys |
|---|---|
| Seismology | 31 |
| Volcanology | 9 |
| Hydrology | 9 |
| Critical-zone geophysics | 9 |
| Remote sensing and vegetation | 8 |
| Cryosphere | 6 |
| Rock physics | 6 |
| Geology (maps, faults, boreholes) | 5 |
| Geodesy | 5 |
| Soil science | 4 |

The remaining 13 labels (geomorphology, landslides, soil physics, contact mechanics, granular physics, meteorology,
hydrogeology, airborne EM, volcanic hazard, snow and avalanche, topography, land cover, statistics) hold 1 to 4 keys
each. This breadth matches the ESSD audience in the profile: each of personas P2 to P6 finds the primary literature
of their own layer cited.

## S-CD.6 In-text concentration

| Measure | Value |
|---|---|
| Keys cited exactly once | 53 of 118 (45%) |
| Share of the 258 citations carried by the 10 most-cited keys | 24% |
| Share carried by the 20 most-cited keys | 39% |
| Most cited | `dnr_gems_100k` 11, `fan2017_wtd` 8, `comcat_uw` 6, `usgs_3dep` 6, `iceboost_v2` 6 |

No ornamental pattern. The once-cited keys sit next to the equation, parameter or product they source (the
granular-media and critical-zone subsections, the calibration solver), which is the pattern a data paper should
have. The most-cited keys are input archives, as expected.

## S-CD.7 Identity axes

Disabled by the profile (`gender_race_inference: no`). Not computed.

## S-CD.8 Reference-combination novelty: high (strength signal)

The reference list joins bodies of work that are rarely cited together: regional community velocity models (CVM
v1.7, CRESCENT Gen0, Brocher 2005), contact and granular mechanics (Mindlin 1949, Walton 1987, Makse 1999),
critical-zone seismic refraction (Holbrook 2014, St. Clair 2015, Flinchum 2018 and 2025), continental water-table
modelling (Fan 2017, Ma 2026), spaceborne canopy structure (GEDI L2B, L3, L4B; Lang 2023), landslide and lahar
inventories, and GNSS strain-rate estimation (Blewitt 2016, Shen 2015). On one grid with one calibration, this is
atypical recombination in the Teplitskiy sense. For ESSD it supports the profile's stated contribution: the
integration of subsurface, surface, geodetic and hydrologic layers.

The gap is on the other side. The paper cites no comparable integrated model to position against (S-CD.10).
A reader cannot tell from the references whether the combination is new or simply uncited.

## S-CD.9 Heterodoxy note for C1

Two moves will look unfamiliar to a volcano seismologist (P2) and should be judged as unfamiliar, not unsound:
granular contact mechanics and effective stress (Walton, Mindlin, Makse, Lu and Likos) used to set near-surface
seismic velocities of a volcanic edifice, and critical-zone refraction literature used to bound regolith velocity.
Both are cited to their primary sources and sit inside the profile's research lineage (rock-physics relations,
scripted compilation). The one place where unfamiliar shades toward unsupported is the attenuation rule and the
unit parameter table, which carry `[TODO: literature source]` markers (lines 369 and 370): those are sourcing gaps,
not heterodoxy.

## S-CD.10 Stretch: comparable models and positioning (profile request)

The Introduction (lines 46–60) cites 6 keys (`hoblitt_1998`, `scott_1995`, `cvm17_article`, `crescent_gen0`,
`dnr_gems_100k`, `comcat_uw`). A search of the paper for SCEC, community fault or velocity models of other regions,
other volcanoes (Kīlauea, Etna, Campi Flegrei, Yellowstone), digital-twin efforts, ESSD precedents and FAIR returned
nothing beyond the two Cascadia models, one mention of Mount St. Helens (iMUSH validation) and the sentence "a
digital model rather than a digital twin" (line 55), which has no citation. Absent categories:

| Category | Cited now | What a reviewer will look for (candidates, verify before citing) |
|---|---|---|
| Community velocity and fault models elsewhere | none | SCEC CVM-S4.26 (Lee et al. 2014), CVM-H (Shaw et al. 2015), SCEC Community Fault Model (Plesch et al. 2007); New Zealand Velocity Model (Eberhart-Phillips et al. 2010); Japan Integrated Velocity Structure Model (Koketsu et al. 2012) |
| 3D models or digital-twin efforts at instrumented volcanoes | none | Kīlauea, Etna or Campi Flegrei 3D velocity or multi-parameter models; the EU DT-GEO project (digital twins for geophysical extremes, volcano component) as the referent for "digital twin" |
| ESSD precedents for multi-layer regional compilations | none | 2 or 3 ESSD data papers that grid several layers on one domain; GlaThiDa 3.0 (Welty et al. 2020, ESSD) is already in scope through `glathida` |
| Data reuse and FAIR | none | Wilkinson et al. 2016 (Scientific Data); Stall et al. 2019 (Nature) |
| Prior Rainier and Cascades subsurface imaging already in the bib but uncited | none of these | `mcgary2014`, `bedrosian2018` (magnetotellurics), `delph2018`, `obermann2013`/`sensschonfelder2006` if the ambient-noise layer is mentioned |

All candidate references in this table are from memory and unchecked: confirm year, venue and DOI with Crossref
before adding any.

## In-text and reference-list consistency

- Cited keys missing from the bib: none (118 of 118 resolve).
- `docs/citations.csv` lists 4 keys as cited in the paper that the paper does not cite as `@key`: `pnsn_1d_wa`,
  `m1_placeholder`, `das_paradise_nisqually`, `soil_map_image`. All four are named in the text or the Data sets
  appendix as registry keys with a `[TODO: citable reference]`. Either give them bib entries or correct the
  `cited_in` field.
- DOIs recorded as "from memory" in `docs/citations.csv` for three cited keys: `brocher_2005`, `glathida`, `rgi60`.
  The paper flags this itself at line 1250.
- `synoptic_catalog` is the only cited key with an empty `verified` field.
- The bib holds RGI 7.0 (`rgiconsortium2023`) and two global ice-thickness products (`farinotti2019`, `millan2022`),
  all uncited, while the paper uses RGI 6.0 and IceBoost v2. A P5 reader will ask why RGI 6.0 rather than 7.0 and
  how IceBoost compares with the two consensus products. Citing them where the choice is made answers both.
- Citation-related `[TODO]` markers (line numbers in `docs/paper/rainier3d_paper.md` @ d61305c):

| Line | Missing item |
|---|---|
| 155, 1214, 1266 | Identity and citation of the PNSN 1D model (P3 Puget Sound or C3 Cascades); no bib entry for `pnsn_1d_wa` |
| 369 | Literature source for the attenuation rule Q_S = 0.05 V_S, Q_P = 2 Q_S |
| 370 | Published range behind each unit parameter in `configs/petrophysics.csv` |
| 557 | Depth reference (below sea level or below summit) of the Moran 1999 low-velocity body |
| 1158 | Podvin and Lecomte (1991), the eikonal solver used by Grid2Time; no key in `configs/sources.yaml` or the bib |
| 1250 | DOIs of `brocher_2005`, `glathida`, `rgi60` taken from memory |
| 1270 | DAS channel table, no citable reference |
| 1271, 1275 | Licence of `synoptic_catalog` and SoilGrids |
| 1288, 1294 | Soil-map image and USGS imagery: no source key |

## Citation Diversity Statement (optional in the profile; draft if wanted)

> The references of this paper were chosen for the data, parameters and methods each layer uses. Of 118 cited
> works, 4 (3%) have the corresponding author as a co-author. About 86% of the cited works have a first author or
> issuing body in the United States, which reflects a site-specific model of a US volcano built from US federal and
> Washington State archives; global products and methods from European and Asian groups are cited where the model
> uses them. Countries were assigned by hand and were not verified against author affiliations. We did not infer the
> gender or race of cited authors.

## Tier feed

- **C6 (citations and context), primary:** self-citation low and justified; temporal, venue and discipline spread
  broad; geographic base narrow for reasons the domain explains. The real C6 gap is positioning (S-CD.10) and 9
  open citation TODOs, two of which source model parameters (lines 369, 370) and one a solver (line 1158). Do not
  lower a tier for the geographic imbalance alone.
- **C1 (significance and novelty), guardrail:** reference-combination novelty is high and is the paper's ESSD
  contribution. C1 should credit it. Without comparable models cited, a referee cannot confirm uniqueness, so F1
  is what makes the C1 case checkable.

## Fixes (in priority order)

- **F1.** Add one positioning paragraph to the Introduction (after line 53) citing 3 to 5 comparable integrated
  models: one SCEC community model, one other-region community velocity model, one or two volcano 3D or digital-twin
  efforts, and give the "digital model rather than a digital twin" sentence (line 55) a referent.
- **F2.** Close the 9 citation TODOs listed above. Podvin and Lecomte (1991) and the Q-rule source are quick; the
  per-unit parameter ranges (line 370) are tracked placeholder work and can stay flagged in Limitations if not done.
- **F3.** Cite the Rainier and Cascades subsurface imaging already in the bib (`mcgary2014`, `bedrosian2018`,
  `delph2018`) where the alteration and magma-body geometry are introduced (around lines 557–583). This also fills
  the thin 2000–2019 Rainier-geophysics stretch.
- **F4.** Opt-in, never required: cite `farinotti2019` and `millan2022` next to IceBoost, and state why RGI 6.0 is
  used instead of `rgiconsortium2023` (RGI 7.0). Add one ESSD multi-layer precedent and one FAIR reference in
  the data-compilation section (line 102). These also widen the geographic base with references that do work.
- **F5.** Give a year or access date to the 5 undated data entries, mark which data-set years are access years, and
  reconcile the 4 `cited_in` rows of `docs/citations.csv` that the paper does not cite as `@key`.

**Human-verify:** every country (S-CD.4) and field label (S-CD.5) was hand-assigned without OpenAlex; the four
self-citations were identified by the string "Denolle" in bib author fields, so a Denolle paper with a malformed
author field would be missed; every candidate reference in S-CD.10 and F1 is from memory and needs a Crossref check
before it enters the bib.
