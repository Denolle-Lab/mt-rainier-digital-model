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

## What the literature gives the design

Three bodies of work were surveyed on 2026-10-02; every DOI below was resolved at doi.org and its title and authors
checked (list at the end).

| Line of work | What it contributes | Transfer to Rainier |
|---|---|---|
| US critical-zone geophysics: Flinchum, Holbrook, Riebe, St. Clair, Rempe | Layered weathering profile (soil, saprolite, fractured rock, fresh rock) imaged by refraction; porosity and water storage from rock physics, granular model for saprolite and penny-crack differential effective medium for fractured rock; depth to fresh rock predicted from curvature, topographic stress or drainage | The layering and the rock-physics laws transfer. The velocity thresholds (saprolite base 1.2 to 1.9 km/s, fresh rock 4.0 to 4.55 km/s) come from granite and schist and are priors only: jointed andesite and breccia may never reach 4 km/s near the surface |
| Volcanic and Cascades analogues: Pasquet et al. 2022 (Guadeloupe), Karlstrom et al. 2025 (Oregon Cascades), Jefferson, Tague and Grant (High Cascades hydrology) | Catchment-scale water table and weathering front on volcanic rock; the deep critical zone shrinks from more than 1 km to metres over about 1 Myr as lavas age | Lava-flow age becomes the permeability prior: deep, vertically conductive on young edifice flows; shallow, lateral flow on Tertiary units |
| European mountain hydrogeophysics: GFZ Potsdam (Illien, Sens-Schönfelder), ISTerre Grenoble (Larose, Le Breton), Strengbach (Lesparre, Pasquet), Fribourg and Aachen (Hauck, Wagner) | dv/v calibrated against groundwater-reservoir models in mountain catchments and on Merapi; seasonal dv/v of 1 to 6% on landslides, growing with frequency; velocity-threshold layers fed into a distributed hydrological model; Vp/Vs jump at the water table | The dv/v-to-reservoir calibration fits our permanent stations, DAS and storm directly. The Vp/Vs water-table mapping and joint ERT-seismic inversion need new field data |
| Coupling physics: Lu and Likos, Lu, Godt and Wu, Hertz–Mindlin, Dvorkin and Nur, Gassmann and Brie, Solazzi et al. 2021, Shi et al. 2026, Shen et al. 2024 | A drained chain from pressure head to suction stress to effective stress to frame moduli to Vs and Vp, already used for DAS dv/v of soil moisture by this group (Shi et al. 2026) | Applies column by column; the same effective stress gives the infinite-slope factor of safety (Lu and Godt 2008, Iverson 2000) |

## Model design

One column per 100 m cell, from the ground (or the glacier bed) to the base of the top L1 cell, five layers:

| Layer | Thickness from | Hydraulic | Frame and seismic |
|---|---|---|---|
| 1. Soil | SOLUS100 soil thickness (≤ 2 m) | POLARIS van Genuchten θr, θs, α, n and ksat | Hertz–Mindlin with the Dvorkin–Nur soft-sand bound; porosity from SOLUS bulk density |
| 2. Quaternary cover (drift, lahar, alluvium) | map-unit thickness (S1, DMU) | texture-based van Genuchten, placeholder | as layer 1 |
| 3. Weathered volcanic rock (the saprolite equivalent) | parameterised: competing estimators below | permeability decreasing with depth; lava age sets the scale | granular model, stiffer contacts |
| 4. Fractured rock | to the depth where Vp reaches the fresh-rock prior | fracture permeability by unit and alteration | penny-crack differential effective medium, aspect-ratio prior 0.016 (Flinchum et al. 2022) |
| 5. Fresh rock | joins L1 | L1 unit | L1 Vp, Vs |

**Depth of layers 3 and 4.** Three estimators compete, each scored against the 23 borehole bedrock picks
(median 40.5 m) and, on the volcano, against node-array dispersion:
- curvature regression (Flinchum et al. 2025), refitted here, not reused;
- topographic stress (St. Clair et al. 2015; Moon et al. 2017 code) with the regional stress;
- drainage-controlled weathering (Rempe and Dietrich 2014).

SoilGrids enters only as a weak prior: its median (19.6 m) is half the borehole median. Two resets apply: where ice
covered the ground at the Last Glacial Maximum the weathering clock starts at deglaciation, and thick drift thins
the weathered layer (Wang et al. 2020); lava-flow age sets the permeability-depth scale (Karlstrom et al. 2025).

**Equations, per column.** State: pressure head h(z, t).
1. **Water.** Mixed-form Richards equation, ∂θ(h)/∂t = ∂z[K(h)(∂h/∂z + 1)] − S_lat. Top: hourly precipitation
   (MRMS for the storm; climatology to add), less interception, snow or glacier melt and evapotranspiration. Bottom:
   the water-table prior as h = 0, or free drainage. S_lat: a Dupuit hillslope sink K sinβ / L, calibrated against
   river discharge.
2. **Effective stress.** σ′ = σ_tot − σ_s, with σ_tot from the column weight (SOLUS bulk density, rock fragments, pore
   water, slope correction) and the suction stress σ_s from the van Genuchten parameters in closed form (Lu, Godt
   and Wu 2010); below the water table σ′ = σ_tot − u_w.
3. **Frame.** Hertz–Mindlin moduli from σ′, porosity, coordination number C and slip fraction f; d ln Vs = (1/6)
   d ln σ′ at fixed C and f. The stress exponent is calibrated, because Hertz–Mindlin overpredicts shear stiffness
   (Makse et al. 1999) and field data often show larger exponents.
4. **Vp.** Gassmann with a Brie patchy fluid modulus, valid at 1 to 60 Hz in the Biot low-frequency limit.
5. **Observables.** dv/v in each frequency band as the depth integral of δVs/Vs weighted by the Rayleigh phase-velocity
   kernel (disba) on the reference profile, extended below 50 m by L1; coda dv/v with the Obermann et al. mixture of
   surface- and body-wave kernels; HVSR peak and dispersion from the same profile.
6. **Slope stability.** Infinite-slope factor of safety with suction stress (Lu and Godt 2008), tested on the
   mass-movement catalogue, with TRIGRS (Baum et al. 2008) as a benchmark.

**Placeholders** (`m1_placeholder` until sourced or calibrated): coordination number and slip fraction; grain
moduli and density by texture; Brie exponent; cohesion and friction angle; hydraulic and elastic properties of
layers 2 to 4; lateral drainage length; thermoelastic coefficients; dynamic-capillary and hysteresis terms (needed
for the storm, Shi et al. 2026); a healing term after earthquakes.

**Vertical grid.** The Richards solver needs 1 to 5 cm nodes in the top 1 to 2 m during a storm, growing to 2 to 5 m
at 50 m: about 80 to 120 nodes, solved at run time. `model.zarr` stores the layer parameters on about 25 nodes in a
`/cz` node.

## What each observation can see

| Observation | Depth sampled | Use |
|---|---|---|
| Permanent-station dv/v, by frequency band | 2 to 4 Hz: upper ~500 m (Clements and Denolle 2023); higher bands, processed with noisepy and codameter, sample tens of metres | the deep reservoir at low frequency and the weathered layers at high frequency |
| DAS dv/v, up to 40 Hz on the Rainier fibre | ~2.5 to 7 Hz: top ~20 m dominant (Shen et al. 2024); 40 Hz: the top few metres | the soil and weathered layers, saturation and suction |
| Node-array dispersion and HVSR (240 sites, 2025) | 0 to ~60 m | layer thicknesses and Vs; waveforms restricted |
| Wells and boreholes (S31) | water table, lowland bedrock depth | layer 3 depth and the water-table prior |
| River discharge under the storm | catchment storage | lateral sink and permeability |
| Mass movements | failure surfaces, metres | strength and pore pressure |

Frequency-dependent seasonal dv/v on landslides (1 to 6%, Le Breton et al. 2021) and snow loading (several % at
15 to 25 Hz, Davos) set the expected signal sizes; snow must be modelled or masked.

## Code

| Code | Licence | Use |
|---|---|---|
| disba | BSD-3 | dispersion curves and depth kernels |
| Landlab (GroundwaterDupuitPercolator, LandslideProbability) | MIT | lateral flow, stability checks |
| openRE (Ireson et al. 2023) | GPL-3.0 | reference 1D Richards solver; copyleft, so reimplement rather than vendor |
| TRIGRS | USGS release | stability benchmark |
| pastas | MIT | empirical impulse-response baseline for wells |
| Denolle-Lab/farmDAS (Shi et al. 2026) | CC BY-NC 4.0 | the closest implementation of the Hertz–Mindlin suction chain; the non-commercial licence blocks vendoring |

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

## Consistency with the subsurface model (2026-10-03)

The critical zone is now part of the subsurface model, not a separate set of columns. S4 builds it (`pixi run s4`,
`rainier3d.cz.medium`, `rainier3d.cz.level`, `configs/cz.yaml` `medium`), S5 writes it as the `/cz` node of
`model.zarr`, and the station synthetics (S33, S34) read their columns from the same code.

| Before | Now |
|---|---|
| Two velocity models in the top 60 m: L1 rock from the ground down, and stand-alone columns | One: L1 cells that reach into the top 150 m are the travel-time average of the columns inside them (density and porosity by thickness, permeability in log space). In the top 50 m of L1, Vs is halved at the median (0.50; 10 to 90%: 0.29 to 0.93) |
| S4 saturated from the ground; columns with their own water table | One water table and one effective stress: S4's crack-closure pressure and the columns use the water table of `medium.water_table`, at the glacier bed under ice. Below 50 m, Vs changes by less than 2% |
| Hertz–Mindlin above, crack closure below, a log-linear stitch between | One medium: a weathering index W (1 in soil, cover and weathered rock, falling to 0 across the fractured zone) blends the granular frame and S4's rock law, at the same effective stress, by a Hill average of the moduli. Where W = 0 the medium is the rock law. At the base of the fine columns (150 m), Vs is 0.97 to 1.00 times the L1 cell below (median 0.989) |
| Alteration ignored near the surface | The rock end-member carries S4's alteration and magma factors |
| No hydraulic properties | Porosity, log10 permeability and the weathering index in every cell of L1–L3; van Genuchten parameters, saturation and effective stress in `/cz`. Fresh rock follows the crustal permeability–depth curve of Ingebritsen and Manning (1999), capped at 10⁻¹² m² |

**Weathering drivers** (placeholders, `medium.weathering`). The depth of the weathered layer starts from the
SoilGrids prior and is multiplied by 0.5 on glacial drift and alluvium and 0.3 on lahar deposits (young surfaces
restart the weathering clock), by 0.5 on consolidated rock at the surface (edifice, cap, pluton and supracrustal
units, which weather slower than the profiles behind SoilGrids), and by 1.2 under forest taller than 20 m (roots
deepen weathering); under present glaciers there is no weathered layer and the bed is fractured rock.

**The structure for a water budget.** A groundwater or land-surface model can now run on the model without new
geometry: layer boundaries per column (`z_soil`, `z_cover`, `z_weathered`, `z_fractured`), porosity and
permeability through the critical zone and L1–L3, van Genuchten parameters, the water table, and the state variables
(pressure head, saturation, effective stress) that link water to seismic velocity. The water budget itself (lateral
flow, snow, evapotranspiration) and the calibration of these placeholders are the next research project.

**Water table.** The published model uses Fan et al. (2017), because the Ma et al. (2026) licence forbids
derivatives. At the stations Fan is bimodal: within 1 m of the ground at 61% of the DAS channels, 37% of the nodes
and 21% of the permanent stations, and more than 100 m down under ridges (90th percentile 112 to 200 m). The wells
of S31 fit Ma better (median misfit 7.1 m against 12.3 m). A water table fitted to the S31 wells (for example on
height above the nearest drainage) would be licence-free and local; it is the most influential state variable of the
critical zone.

**Invariant.** `test_physical_ranges` bounds each law, not each cell (decision of 2026-10-05). Cells with no
critical zone (weathering index 0, consolidated unit) keep the rock bound Vp/Vs ≤ 3; their maximum is 2.07 in L1.
Cells that contain critical zone (W > 0 or an unconsolidated unit; 85,665 in L1, 3 in L2) may reach 5, because
a saturated granular layer reaches 4 to 4.5 (Pasquet et al. 2015); their maximum is 4.70, in the top L1 cell,
where a saturated weathered layer a few metres thick dominates the travel-time average of Vs.

## Build plan and status

| Step | Status (2026-10-02) | Code | Result |
|---|---|---|---|
| 1. Forward model at the stations (synthetic) | built, on the model's columns | `pixi run s33` (`rainier3d.cz.sites`, `.medium`, `.level`, `.synthetics`) | 365 sites (46 permanent, 191 nodes, 128 DAS channels); 7 on glaciers not computed. Quarter-wavelength resonance (median): 5.9 Hz at the permanent stations, 5.4 Hz at the nodes, 4.7 Hz on the DAS. Half the Vs sensitivity lies within 8.5 to 12 m at 10 Hz and 4 to 5 m at 40 Hz. A water table 1 m shallower (clamped at the ground) lowers dv/v at 40 Hz by 0.09% (permanent), 0.31% (nodes) and 0.17% (DAS), medians; the response depends mostly on the water-table depth |
| 2. Weathering-depth estimators | scored, none adopted | `pixi run s35` | On the 23 borehole bedrock picks no estimator beats the median of the others (mean absolute error 24.7 m): SoilGrids 26.8 m, terrain regression 27.4 m, curvature regression 28.5 to 30.8 m. All picks lie in the Puget lowland (155 to 310 m), where they measure glacial drift over bedrock, not a weathering profile; the depth on the volcano has to come from the seismic data (step 4). SoilGrids stays the prior |
| 3. Hydrology through the storm (synthetic) | built | `pixi run s34` (`rainier3d.cz.richards`) | 1D Richards over the top 30 m at each site under the hourly MRMS rain of 5 to 14 December 2025; 350 sites solved, 8 failed at the minimum time step; mass balance within 0.0002 mm. Median rain 200 to 290 mm, no runoff (POLARIS ksat exceeds the rain rate). Lowest dv/v (median over sites): about −0.06% at 5 Hz, −0.5 to −0.75% at 10 Hz, −0.9% at 20 Hz, −1.1 to −1.2% at 40 Hz. At 20 and 40 Hz dv/v recovers between rain pulses as suction returns; at 5 and 10 Hz it only decreases, because the column has no lateral drainage yet |
| 4. Calibration | rock calibration refitted; critical-zone calibration interface built | `pixi run s13` (critical zone in every trial model), `rainier3d.cz.calibrate` | S13 with the critical zone: held-out RMS 0.0926 s (P) and 0.1861 s (S), against 0.0924 and 0.1877 s without it; V0 ×1.40 (was 1.31), P* ×1.33 (was 0.91), Vs ×0.970; the regional bias is unchanged. Adopted in `configs/velocity_calibration.yaml` (the previous one is `velocity_calibration_v2.yaml`). The critical-zone parameters wait for near-surface data (dispersion, dv/v) |
| 5. Forcing | not started | | PRISM normals and SNOTEL snow; snow and rain are not separated yet, which matters above the snow line in December |

Next in the model itself: the lateral drainage sink (Dupuit, calibrated on the gauges), snow, and evapotranspiration.

**Decisions for the authors.** Reimplement the suction chain from the equations (clean BSD licence) or ask Qibin Shi
to relicense the farmDAS model code (for example MIT) so it can be vendored under `third_party/`. Field data that
would constrain layers 3 and 4 most: two or three active refraction lines with Vp and Vs across a ridge–valley pair
and a lahar or drift contact, and seismic logs or casing depths in a few lowland wells.

## References (DOIs resolved at doi.org, 2026-10-02)

- **Critical-zone structure.** Flinchum et al. 2018, Hydrol. Process., 10.1002/hyp.13260; Flinchum et al. 2018,
  JGR Earth Surface, 10.1029/2017JF004280; Flinchum, Holbrook and Carr 2022, Front. Water, 10.3389/frwa.2021.772185;
  Flinchum et al. 2024, GRL, 10.1029/2023GL105946; Flinchum et al. 2025, JGR Earth Surface, 10.1029/2025JF008346;
  Holbrook et al. 2014, ESPL, 10.1002/esp.3502; St. Clair et al. 2015, Science, 10.1126/science.aab2210; Moon et al.
  2017, JGR Earth Surface, 10.1002/2016JF004155; Riebe, Hahm and Brantley 2017, ESPL, 10.1002/esp.4052; Rempe and
  Dietrich 2014, PNAS, 10.1073/pnas.1404763111; Rempe and Dietrich 2018, PNAS, 10.1073/pnas.1800141115; Wang et al.
  2020, EPSL, 10.1016/j.epsl.2020.116517; Grana et al. 2026, Rev. Geophys., 10.1029/2025RG000912.
- **Volcanic and Cascades.** Pasquet et al. 2022, GRL, 10.1029/2022GL098433; Karlstrom et al. 2025, PNAS,
  10.1073/pnas.2415155122; Jefferson, Grant and Rose 2006, WRR, 10.1029/2005WR004812; Tague and Grant 2004, WRR,
  10.1029/2003WR002629.
- **European mountain hydrogeophysics.** Illien et al. 2021, AGU Advances, 10.1029/2021AV000398; Illien et al. 2022,
  JGR Solid Earth, 10.1029/2021JB023402; Sens-Schönfelder and Wegler 2006, GRL, 10.1029/2006GL027797; Le Breton et
  al. 2021, Earth-Sci. Rev., 10.1016/j.earscirev.2021.103518; Mainsant et al. 2012, GRL, 10.1029/2012GL053159;
  Pasquet et al. 2015, J. Appl. Geophys., 10.1016/j.jappgeo.2014.12.005; Lesparre et al. 2024, HESS,
  10.5194/hess-28-873-2024; Wagner et al. 2019, GJI, 10.1093/gji/ggz402; Lecocq et al. 2017, Sci. Rep.,
  10.1038/s41598-017-14468-9.
- **Coupling physics and dv/v.** Lu and Likos 2006, J. Geotech. Geoenviron. Eng., 10.1061/(ASCE)1090-0241(2006)132:2(131);
  Lu, Godt and Wu 2010, WRR, 10.1029/2009WR008646; Lu and Godt 2008, WRR, 10.1029/2008WR006976; Iverson 2000, WRR,
  10.1029/2000WR900090; Baum et al. 2008, USGS OFR, 10.3133/ofr20081159; Dvorkin and Nur 1996, Geophysics,
  10.1190/1.1444059; Makse et al. 1999, PRL, 10.1103/PhysRevLett.83.5070; Biot 1956, JASA, 10.1121/1.1908239; Brie
  et al. 1995, SPE, 10.2118/30595-MS; van Genuchten 1980, SSSAJ, 10.2136/sssaj1980.03615995004400050002x; Solazzi
  et al. 2021, JGR Solid Earth, 10.1029/2021JB022074; Shi et al. 2026, Science, 10.1126/science.aec0970; Shen et al.
  2024, Nat. Commun., 10.1038/s41467-024-50690-6; Clements and Denolle 2018, GRL, 10.1029/2018GL077706; Clements and
  Denolle 2023, JGR Solid Earth, 10.1029/2022JB025553; Obermann et al. 2013, GJI, 10.1093/gji/ggt043; Ireson et
  al. 2023, GMD, 10.5194/gmd-16-659-2023.
