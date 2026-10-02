# A critical-zone model for rainier3d: what the data support

Status: assessment of 2026-10-02, branch `critical-zone-layers`. Numbers come from the S2 run of that day
(`outputs/soil_layers_summary.json`, `data/processed/surface_layers.zarr`, `soil_profile.zarr`) unless a section of the
paper is named.

## Verdict

A first seismic, mechanical and hydrological model of the critical zone is feasible now as stacked one-dimensional
columns on the 100 m surface grid, from the ground to the top of L1. The top 2 m are well described: two soil products
cover 97% of the box and agree on porosity, although both are trained on US soil-survey data and are not
independent. The part that matters most for water and for seismic
velocity, 2 m to about 50 m, has no direct data. Its thickness differs by an order of magnitude between the two
estimates, and no data set gives its permeability or strength. Build the model with that layer parameterised and
let the observations the project already holds (storm response, seismic velocity changes, mass movements) constrain
it, rather than waiting for a regolith map.

## Why 0 to 50 m is a separate problem

The geophysical model starts at the scale of tens of metres. L1 cells are 250 m wide and 50 m thick
(`configs/domain.yaml`, profile m1), so the whole critical zone, from soil to the base of the weathered rock, sits
inside the top L1 cell or two. The surface layers describe the top 2 m. Nothing in between carries a depth axis.

| Depth below ground | What the model holds | Source | Constraint |
|---|---|---|---|
| 0 to 1.5 m | clay, sand, silt, bulk density, rock fragments, organic carbon at 7 depths | SOLUS100, 100 m | good; empty below the lithic contact |
| 0 to 2 m | ksat, θs, θr, van Genuchten α and n in 6 layers | POLARIS, 30 m | good; values exist below the lithic contact too |
| 1.41 m (median) | lithic contact, capped at 2.01 m | SOLUS100 | good to 2 m, blind below |
| 19.6 m (median) | depth to bedrock | SoilGrids 2017, 250 m | weak: global model trained on well logs |
| 10.1 m (median) | water table | Ma et al. 2026 (paper Sect. Geohydrology) | moderate; Fan et al. 2017 gives 23 m |
| top 30 m | Vs30 | USGS hybrid map, ~900 m | weak: 56.9% of the box carries two class values |
| 0 to 150 m | alteration index | 1996 EM survey, edifice only | moderate |
| from 25 m elevation, 50 m cells | Vp, Vs, ρ, Q by unit; Vs of the top 100 m of rock | L1 | good at its own scale |

The median water table (10.1 m) lies below the median soil (1.41 m) and above the median SoilGrids bedrock
(19.6 m). The unsaturated zone and the top of the saturated zone therefore sit mostly in the poorly known layer.

## Cross-checks between sources (S2)

| Check | Value |
|---|---|
| SoilGrids depth to bedrock / SOLUS soil thickness, median | 13.9 |
| Cells where SoilGrids bedrock is deeper than 5 m | 100% |
| Cells where the Ma et al. 2026 water table is below the SOLUS soil and above the SoilGrids bedrock | 92.8% |
| Cells where SOLUS restriction is more than 10 cm above the lithic contact | 42.6% |
| Porosity from SOLUS bulk density (ρs = 2.65 g cm⁻³) vs POLARIS θs, medians | 0.63 vs 0.65 |
| Correlation of those two porosities | r = 0.68 |
| Vs30 cells at 686 m/s and at 464 m/s | 50.0% and 6.9% |
| Glacier cells left empty | 2.6% |

The two soil products agree, as expected from their shared training data. The two depth-to-rock estimates do not, and they measure different things: SOLUS the
soil profile of the surveys, SoilGrids an absolute depth to the R horizon. On a volcano mantled by tephra, lahar and
glacial deposits, both can be right in places. A regolith thickness must come from the model's own observations.

## Proposed structure

One column per 100 m cell, from the ground (or the glacier bed) to the base of the top L1 cell, with three layers.

| Layer | Thickness | Hydraulic | Mechanical | Seismic |
|---|---|---|---|---|
| Soil | SOLUS soil thickness (≤ 2 m) | POLARIS van Genuchten profile | unit weight from bulk density and water content; strength from texture (pedotransfer, to choose) | granular contact model with effective stress and saturation |
| Regolith | to a parameterised depth, prior between the SOLUS and SoilGrids values | permeability decreasing with depth, as fitted in the Oregon Cascades by Saar and Manga (2004, doi:10.1029/2003JB002855) and for the crust by Ingebritsen and Manning (1999, doi:10.1130/0091-7613(1999)027<1107:GIOAPD>2.3.CO;2) | as soil, denser | Vs rising from the soil value to the bedrock value |
| Weathered bedrock | to the base of the top L1 cell | fracture permeability by unit and alteration | L1 unit properties | L1 Vs, reduced by alteration |

Storage: a new node of `model.zarr` (for example `/cz`) on the surface grid with a depth axis of about 25 nodes, fine
in the soil (0, 0.05, 0.15, 0.3, 0.6, 1, 1.5, 2 m, matching SOLUS and POLARIS) and growing geometrically to 50 m. The
parameters that are choices go in a config with `m1_placeholder`, as elsewhere.

## Observations that can calibrate the poorly known layer

| Observable | Held in rainier3d | What it constrains |
|---|---|---|
| River response to the December 2025 storm | MRMS hourly precipitation, 7 USGS gauges and 3 virtual sensors (paper Sect. December 2025 floods) | regolith storage and permeability |
| Seasonal and storm velocity changes (dv/v) | permanent UW and CC stations; Paradise–Nisqually DAS, 3,191 channels | saturation and effective stress in the top tens of metres, as in Clements and Denolle (2018, doi:10.1029/2018GL077706) |
| Resonance and dispersion | 2025 node array Z5, 240 stations | thickness and Vs of the soft layer (HVSR); waveforms are restricted, station metadata open |
| Slope failures | 1,650 mass-movement events and 466 flow deposits (paper Sect. Mass movements), slope and relief (S30) | strength and pore pressure, through an infinite-slope factor of safety |
| Seasonal loading | GNSS annual areal strain, median 15 nanostrain | water storage, weakly |
| Wells and boreholes (S31) | 5,591 water levels (142 at or above 600 m) and 23 bedrock picks, frozen at 2026-09-23 | water-table depth (Ma et al. 2026: median absolute misfit 7.1 m, Spearman 0.27) and lowland depth to rock (median 40.5 m, against 22.4 m from SoilGrids) |

## Gaps, in order of value

1. **Regolith thickness between 2 and 50 m.** No map at this scale. The 23 borehole picks are lowland only; the
   node array and DAS are the best constraint on the volcano. The map-unit descriptions now set the thickness of
   eight Quaternary units (S1).
2. **Permeability and strength below the soil.** GLHYMPS 2.0 (global, lithology-based) would give a prior for
   permeability; strength needs a choice of pedotransfer functions.
3. **Climate forcing.** Only the December 2025 storm is held. PRISM 800 m normals are the obvious addition; the PRISM
   web service changed its call syntax in 2025 and S2 does not read it yet.
4. **Snow.** End-of-season NDSI only. Snow water equivalent at the 11 SNOTEL sites of the sensor inventory is
   available.
5. **Under the glaciers.** No soil or regolith data on 2.6% of the box.

## Next steps

1. Add PRISM normals (precipitation, temperature) to S2.
2. Build the `/cz` column node with the three layers and the placeholder regolith depth.
3. Forward-model Vs(z) and its sensitivity to saturation in each column; compare with HVSR at the Z5 sites once
   waveforms are accessible.
4. Run a 1D Richards model per column under the December 2025 storm and compare the summed response with the gauges.
