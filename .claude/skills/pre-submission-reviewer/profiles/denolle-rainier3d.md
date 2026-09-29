# Author profile: Marine Denolle, rainier3d (ESSD)

Created 2026-09-28 for `docs/paper/rainier3d_paper.md`, a data description paper for Earth System Science Data
(ESSD, Copernicus). Voice fields follow `profiles/denolle.md`; lineage, audience and citation values are specific
to this paper. The two sections after the YAML block (journal calibration and readership personas) are extensions
that the schema in `references/author_profile.md` does not define; how the orchestrator uses them is stated in each.

```yaml
name: Marine Denolle (rainier3d, ESSD)
register: plain; first person allowed; minimal hedging; opinions stated directly
favored_phrasing: "digital model" (never "digital twin": the paper states it assimilates no time-dependent data); "rebuild"; stage labels S1 to S22 and level labels L1 to L3 as terms of art; "placeholder" for unsourced parameters (configs/sources.yaml key m1_placeholder); "held-out events"; "invariant test"
banned_phrasing: the group plain-voice list (no LLM-tell vocabulary; no em-dashes)
sentence_rhythm: mixed, with short emphatic sentences among longer ones; leave my cadence
never_change: clear non-native phrasing; the reader-addressed subsections of the December 2025 flood section ("For atmospheric scientists", "For hydrologists and geomorphologists", ...); numbers stated with their source (data, parameter file, window, script); the Limitations section's candour about placeholders
research_lineage: regional community velocity models (USGS Cascadia velocity model v1.7, CRESCENT Gen0, Brocher 2005 rock-physics relations); Mount Rainier hazard and edifice studies (Hoblitt 1998, Scott 1995, Vallance and Scott 1997, Finn 2001, Sisson 2011, Moran 1999, Ulberg 2020); open geospatial archives (USGS 3DEP, Washington DNR geologic map, RGI 6.0, NHDPlus HR); deterministic, scripted data compilation with checksummed caches
novelty_appetite: balanced; ESSD judges uniqueness and usefulness of the data, not novelty of interpretation. Defend the integration of subsurface, surface, geodetic and hydrologic layers on one grid as the contribution; flag interpretive claims that go beyond what the data description supports
citation_values:
  surface_axes: [geographic, temporal, venue, self_citation, discipline]
  citation_diversity_statement: optional
  flag_over_self_citation: yes
  surface_underrepresented_group: no
  gender_race_inference: no
  stretch: surface comparable community and volcano models the paper could position against (SCEC community velocity and fault models; 3D models or digital-twin efforts at other instrumented volcanoes); ESSD precedents for multi-layer regional data compilations; data-reuse and FAIR literature where the paper claims reproducibility
audience: ESSD readers who will download and reuse the data without contacting the authors, across seismology, geodesy, hydrology, cryosphere, atmospheric science and hazard practice; push accessibility hard, because most readers are expert in one layer and new to the others
```

## Journal calibration (ESSD)

The calibration table in `SKILL.md` (Step 2) has no ESSD row, and its fallback (the GRL standard) is wrong for a
data paper. For this manuscript the orchestrator uses the row below and passes it to every subagent in place of the
calibration row. It sets the bar, it does not relax it: reproducibility (C3, S-RP) and evidence to conclusion
alignment (C4) apply in full.

| Journal | Significance bar | Presentation standard | Data/code policy |
|---|---|---|---|
| **ESSD** | Uniqueness, usefulness and completeness of the data set; the article must let a reader use the data without contacting the authors. Interpretation is secondary and should not outrun the data | Structured description of the data, methods, uncertainties and known limitations; figures and tables that show coverage and quality; Copernicus template with a Code and data availability section | Data deposited in a persistent repository with a DOI and accessible to reviewers at submission; versioning stated; licence stated; a data set behind a login or "upon request" is non-compliant |

Map ESSD's three review questions onto the rubric: significance (uniqueness, usefulness, completeness) to C1; data
quality (accessible through the stated identifier, uncertainties quantified, methods adequate) to C2 and C3;
presentation quality (structure, figures, whether the article suffices to use the data) to C5. Report in
JOURNAL-SPECIFIC NOTES any data set cited in the Data sets appendix that has no persistent identifier.

## Readership personas

Six readers who represent the ESSD audience for this paper. They are reading lenses, not additional scorers and not
a replacement for the section subagents. The orchestrator passes this block with the profile; each subagent reads
its section through the personas listed against it and names the persona when a finding comes from one ("P4 cannot
find ..."). In the report, add a READERSHIP block after the section findings: for each persona, one line on whether
the paper serves them and the single change that would help most. Personas never override integrity, and a gap
for one persona is a usability finding (C5), not a soundness finding, unless the missing item is also needed to
verify the data.

**P1. ESSD data reviewer.** Topical editor or referee for ESSD, generalist in solid-Earth data. Opens the Code and
data availability section and the Data sets appendix first, then follows the DOI. Checks that the deposited
products match what the paper describes (variables, units, grids, CRS, version), that each derived layer states
its uncertainty, that placeholder parameters are listed and bounded, and that the article is self-sufficient.
Stops reading when a product named in the text is not in the deposit, or when rebuilding requires a file the
public cannot obtain (the four inputs read from local or delivered copies).
Sections: all; lead lens for S-FD, S-RP, S-CO.

**P2. Volcano seismologist.** Locates earthquakes and runs tomography at Cascade volcanoes; knows the PNSN catalogue,
the Cascadia velocity model and 1D station-correction practice. Wants the calibration and validation numbers with
their event selection, the held-out split, what "relocated in the published model" means, and how the model
compares to independent tomography beneath Rainier. Will ask whether the gain in RMS residual survives a different
event selection or a different pick weighting, and whether the model is fit for waveform modelling above 1 Hz at
the stated grid spacing.
Sections: Subsurface model, Calibration, Validation, Locating earthquakes. Lens for S-ME, S-RE.

**P3. Geodesist and volcano deformation modeller.** Uses GNSS velocities, strain rate and edifice-load stress to
set boundary conditions for deformation models. Wants station selection, reference frame, velocity uncertainties,
the smoothing that produces the strain field, and how daily strain during the summit swarms is separated from
noise. Will ask whether the 3D strain in the model volume is data or an extrapolation, and how its uncertainty
grows with depth.
Sections: Geodetic strain and stress at depth. Lens for S-ME, S-RE, S-DI.

**P4. Hydrologist and geomorphologist.** Works on floods, sediment transport, lahars and debris flows in the
Nisqually, Puyallup, Carbon and White river basins. Wants the geohydrology layers (water-table depth, soil,
hydrography), the mass-movement inventory with its completeness by type and date, and the December 2025 flood
data: gauges, precipitation product, virtual sensors and their time stamps. Will ask what each layer's resolution
and vintage are, and whether the mass-movement catalogue can be joined to the terrain and precipitation grids
without resampling artefacts.
Sections: Surface layers, Geohydrology, Mass movements, December 2025 floods. Lens for S-RE, S-FD.

**P5. Cryosphere and atmospheric scientist.** Studies Rainier's glaciers, snowpack and orographic precipitation.
Wants ice thickness and outlines with their dates and sources (RGI 6.0, GlaThiDa, the ice-thickness product), the
precipitation and meteorological products for the storm, and the vegetation and land-cover layers that condition
snow and runoff. Will ask how glacier change since the outline dates affects the surface and subsurface layers,
and whether the event data can drive or evaluate a regional atmospheric or hydrologic model.
Sections: Surface layers (elevation, glaciers, vegetation), December 2025 floods. Lens for S-RE, S-DI.

**P6. Hazard practitioner and data engineer.** Two readers who share one question, "can I load this and trust
it?": a hazard analyst at a state or federal agency who needs lahar-relevant layers and knows GIS but not zarr, and
a research software engineer who will script access, rebuild the model and feed it to a wave-propagation or
hazard code. Wants the product list, formats (zarr v3, DataTree levels), CRS and vertical datum (EPSG:32610,
NAVD88 positive up), licensing and redistribution terms, the client and viewer, and the exact rebuild command with
its runtime and storage. Will ask what breaks when an upstream archive changes, and how versions of the model are
named and cited.
Sections: Domain, grids and workflow; A deterministic data compilation; Accessing the model; Limitations. Lens for
S-IN, S-RP, S-FD.
