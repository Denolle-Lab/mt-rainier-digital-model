# Mount Rainier Seismic Atlas: design

Date: 2026-09-23
Status: approved 2026-09-23
Scope: phase 1 (the sensor network on real terrain) and phase 2 (earthquakes beneath it). Each phase gets its own implementation plan.

## Purpose

A visual demo. Someone opens a web page and sees Mount Rainier in real detail, with the seismic network that watches it placed where the stations actually are. They can fly to a station, zoom to 1 m detail at the summit, and in phase 2 look underneath the mountain at where its earthquakes happen.

It reuses the look, navigation and building blocks of the Cascadia Offshore Sensor Atlas (the Axial Seamount map in `coszo-hub/RCA-Atlas`, `src/atlas_map`), in a fresh repo.

**What the user asked for**

- A 3D map of the sensor network around, on and under Rainier, reusing the Axial framework and design system.
- Real terrain, not false color: aerial imagery on high-resolution elevation, with the 1 m lidar at the summit loaded as you zoom in.
- Stations sit on the surface. There are no below-ground slices of the network.
- Earthquakes come after the sensor network. They are drawn by density, with glow cloud, density shells and dots as separate toggles, plus a toggleable cut. Solid ground must never let them show through. The underside can be explored by moving the camera below the ground.
- The default view shows the whole mountain, the surrounding area and the earthquakes.
- Navigation matches the Axial atlas: drag to move, Ctrl-drag to rotate, arrow keys, and camera flights. Major stations are in the go-to list.
- Hosted on GitHub Pages from a personal repo.

**Assumed, open to correction**

- The audience is people being shown the demo, not scientists doing analysis. So there is no live data, no data downloads and no chat.
- A snapshot of the stations and earthquake catalog, refreshed by rerunning the build, is good enough.
- Desktop browsers come first. Touch works but isn't tuned.

**Success**

- Within five seconds of opening the page, a viewer sees the mountain and its stations.
- Within a minute, without instructions, they have flown to a station and zoomed onto the summit crater at 1 m detail.
- In phase 2, one toggle shows the column of earthquakes under the summit and the separate zone to the west. Nothing underground ever shows through solid ground.

The approved mockup is live at https://yaoderek.github.io/rainier-seismic-atlas/. Its source is `index.html` at the root of this repo. The design below turns it into a maintainable build.

## What the data supports

All sources are public and were checked on 2026-09-23.

**Stations.** The EarthScope FDSN station service lists 52 active stations (channels with no end date) within 50 km of the summit, from four networks. Two sources were excluded: `C0.PALI`, which duplicates `CC.PALI` under a Colorado network code, and the synthetic `SY` network.

| Network | Operator | Active stations | Role |
|---|---|---:|---|
| CC | USGS Cascades Volcano Observatory | 32 | seismometers with infrasound, many along the river drainages |
| UW | Pacific Northwest Seismic Network | 17 | long-running summit and flank stations, Longmire tiltmeters, regional broadband |
| NP | USGS strong-motion network | 2 | accelerometers |
| PB | EarthScope borehole network | 1 | B941 strainmeter at 153 m depth |

Instrument kinds come from channel codes. Station-health channels are ignored. Every station except B941 sits in a vault 0–2 m deep.

| Kind | Channel codes | Stations |
|---|---|---:|
| Seismometer, broadband | BH, HH | 40 |
| Seismometer, short period | EH | 6 |
| Geophone | CH | 21 |
| Infrasound | BD, HD, CD | 21 |
| Accelerometer | EN, HN | 12 |
| GNSS | GA, GE, GN, GS, GP, GL | 10 |
| Tiltmeter | HA, HK | 1 |
| Borehole strainmeter | BS, LS | 1 |

39 of the 52 stations fall inside the terrain area described below. The other 13 are in the regional ring, 25–50 km out.

**Earthquakes.** The USGS ComCat catalog (PNSN) has 15,660 events in the terrain area since 1980, from M −1.6 to M 4.9. Depths: median 2 km, 90% shallower than 11.3 km, 99% shallower than 18.4 km. Some events have negative depths, meaning above sea level: they are inside the volcano.

**Terrain.**

- USGS 3DEP elevation and USGS The National Map imagery (`USGSImageryOnly`), both public domain, served by ArcGIS REST export endpoints.
- 3DEP has 1 m lidar over the summit, confirmed by a test download: both summit craters and crevasse fields are visible.

**Server quirk found while prototyping.** Both ArcGIS export endpoints quietly change the area returned when the requested image's shape doesn't match the requested area's shape in degrees. Requests must use square pixels in degrees: width ÷ height = Δlon ÷ Δlat. Otherwise adjacent pieces overlap, and the seams were off by 170–400 m in the prototype.

## Architecture

A static site with no server, built from a data step that runs locally.

```text
data/                Python build step: fetches public sources and writes the static bundle
site/                the website (React + Vite + Three.js), deployed to GitHub Pages
site/public/atlas/   the bundle the build step writes and the site loads
mockup/              the approved v3 mockup, kept for reference
```

```text
3DEP + imagery ─┐
EarthScope FDSN ┼─► data/build.py ─► site/public/atlas/ ─► vite build ─► GitHub Pages
USGS ComCat ────┘
```

### Build step: `data/`

Python 3.12 with numpy and nothing else. The prototype reads GeoTIFF with a small reader for uncompressed tiled files, which is what the 3DEP export returns. Each script caches its downloads under `data/cache/`, which is git-ignored, and runs offline when the cache is present.

| Module | Does | Output |
|---|---|---|
| `extent.py` | the fixed map area and projection constants: center 46.8528°N, 121.7604°W; equirectangular kilometers; the square-degree pixel rule | none |
| `terrain.py` | overview elevation (0.8° × 0.54°, 1800 × 1215 samples, about 35–50 m) and overview imagery (4096 × 2765 JPEG) | `terrain/overview.bin` (Int16 m), `terrain/overview.jpg`, `terrain/terrain.json` |
| `summit.py` | the summit patch: 12288 × 8192 samples at 9e-6° (about 0.69 m × 1.0 m), fetched as 2048² pieces with seams checked (mean step under 2 m, or the build fails), then reduced to four levels | `summit/{0..3}/{ty}_{tx}.bin` (Uint16 decimeters, 257² samples with a shared edge), `summit/img/…jpg`, `summit/index.json` |
| `stations.py` | EarthScope FDSN channel query; instrument kinds from the table above; co-located codes merged into sites | `stations.json` |
| `quakes.py` | ComCat query for the map area since 1980 (phase 2) | `quakes.bin` (Float32 x, y, z, magnitude), `quakes.json` (count, time span, magnitude range, as-of date) |
| `build.py` | runs the above and writes `manifest.json` with every source URL, query and fetch date | `manifest.json` |

Rules:

- **Sites.** Station codes within 150 m of each other are one site, the same rule as the Axial atlas. This merges the Longmire codes `UW.LON`, `UW.LO2` and `UW.LON9` into one site. A site takes the name of its longest-running station.
- **Major stations** are a reviewed list in `data/major_stations.json`, each with a one-line description. The starting list comes from the mockup, with the names corrected from FDSN site names: STAR (St. Andrews Rock), RCM (Camp Muir), RCS (Camp Schurman), MILD (Mildred Point), PARA (Paradise), RER (Emerald Ridge), FMW (Mount Fremont), LON (Longmire), OBSR (Observation Rock).
- **Stations outside the terrain area** stay in `stations.json` with `onMap: false`.
- **Earthquakes above the ground surface** at their position are kept in the data and counted in `quakes.json`. The site doesn't draw them.

Validation. The build fails if any of these fails:

- The station count reconciles: active stations returned, minus the excluded sources, equals the stations in `stations.json`.
- Every channel code maps to a kind or to the state-of-health ignore list. An unknown code fails the build.
- Summit pieces meet with a mean step under 2 m.
- The summit patch's 8 m level agrees with the overview elevation to within 30 m RMS over the patch.
- Total bundle size stays under 600 MB, leaving room under GitHub Pages' 1 GB limit.

### Site: `site/`

React 18, Vite and Three.js 0.169, the same stack and versions as `src/atlas_map`. The scene is a plain Three.js class owned by one React component, as in `AtlasScene.js`. Markers, labels and panels are HTML over the canvas.

**Copied from `src/atlas_map`, with its tests:**

- `styles/tokens.css`
- `scene/cameraMath.js`: `ease`, `moveStep`, `isMoveKey`, `isTypingTarget`, `motionDuration`, `approach`
- The `OrbitControls` setup, flight code and key handling from `AtlasScene.js`
- The `Controls.jsx` segmented-control pattern

**New units:**

| Unit | Responsibility | Depends on |
|---|---|---|
| `scene/RainierScene.js` | renderer, camera, controls, frame loop, flights, near-plane tracking | cameraMath, the layers below |
| `scene/baseTerrain.js` | overview mesh and material (photo, mono or contour style; cut; see-through; summit hole; dark underside) | terrain bundle |
| `scene/summitLod.js` | quadtree tile selection as a pure function of camera and tile states, plus a loader with a request queue, an in-flight cap and LRU eviction | `summit/index.json` |
| `scene/ground.js` | height texture and GLSL `groundKm()`, used by every underground layer | terrain bundle |
| `scene/stationMarkers.js` | projects station sites to screen positions each frame, hides markers behind terrain, handles hover and click | `stations.json`, base terrain |
| `scene/quakes/{cloud,shells,dots}.js` | the three earthquake layers (phase 2) | `quakes.bin`, ground |
| `ui/Header`, `ui/GoTo`, `ui/StationPanel`, `ui/LayerPanel`, `ui/Legend` | panels | scene API |

Each unit can be tested without WebGL. Tile selection, key motion, grouping and ground sampling are pure functions.

## Phase 1: the sensor network

### Terrain

- **Overview.** A 60 × 60 km area centered on the summit: 3DEP elevation draped with USGS imagery, at 1× vertical scale.
- **Summit.** An 8.4 × 8.2 km patch at 8, 4, 2 and 1 m.
  - Tiles are 256 cells with a shared edge.
  - A tile splits into its four children when the camera is closer than 2.5 tile widths. At that distance 1 m is about one screen pixel.
  - The parent stays visible until all four children have loaded, so there are never holes.
  - The overview gets a hole where the patch is, but only after every 8 m tile has loaded.
- **Skirts.** Tile edges carry downturned skirts that hide cracks between levels. Skirts render as dark rock and are dropped when the camera is below ground.
- **Surface style.** Photo (default), Mono (grey hillshade) or Contours (dark fill with 100 m lines, heavier every 500 m). These are the Axial atlas's three styles, with Photo replacing its false-color Depth ramp.
- **View.** 3D or 2D, flattening over 0.8 s as in the Axial atlas. There is no vertical exaggeration control; Rainier reads well at 1×.

### Stations

- **Markers.** Each site is a ring with one segment per instrument kind, the same ring as the Axial atlas.
  - Seven kind colors: seismometer, geophone, infrasound, accelerometer, GNSS, tiltmeter, strainmeter. Short-period and broadband seismometers share the seismometer color and differ by segment stroke.
  - Each kind also has a glyph, so identity never rests on color alone. The palette is checked with the dataviz validator against `#121211`.
- **Labels.** Visible labels show the station code. Where labels collide, major stations win.
- **Hidden stations.** A marker behind terrain fades to 12% and loses its label and hover, tested by walking the sight line across the height grid, as in the Axial atlas. Markers hide when the camera is below ground.
- **Hover** shows the site name, codes, network and operator, elevation, instrument kinds and running since.
- **Click** opens the station panel and flies to the station.

### Station panel

- Site name, codes, operator and elevation.
- Instrument kinds with their channels, for example "Broadband seismometer · HHZ HHN HHE · 100 Hz".
- Running since, and "active per EarthScope metadata as of <date>".
- Links:
  - EarthScope station page and FDSN StationXML
  - PNSN station page for UW stations
  - the Mount Rainier pages of USGS CVO for CC stations
  - a copyable FDSN dataselect URL for the last hour of the vertical channel

There's no live waveform in phase 1.

### Navigation

Copied from the Axial atlas:

- Drag moves the view across the terrain.
- Ctrl/Cmd/Shift-drag or right-drag rotates.
- Scroll zooms toward the cursor.
- Holding an arrow key glides across the terrain at a speed that scales with zoom. Modified arrows and arrows typed into a field are ignored.
- Any drag or arrow cancels a flight. Flights take 1.8 s along an eased arc; flights to a point take 1.3 s. Under reduced motion, flights jump to their end.

For Rainier:

- The camera may go below the ground: the polar limit is removed.
- The near plane follows the zoom, so both 1 m detail and the 60 km overview keep depth precision.
- **Go to** lists places (Whole area, Summit crater, Paradise, Carbon River, White River, Nisqually) and the major stations.
- Flying to a station frames it from 9 km out, 28° above the horizon, on the side away from the summit, so the mountain rises behind it. Stations within 1 km of the summit keep the current heading. The flight takes 1.8 s.
- **Search** finds a station by code or site name and flies to it.

### Layout

As in the Axial atlas:

- **Top left:** title and counts (stations, sites, instrument kinds), plus the current summit detail level.
- **Top right:** terrain controls (View, Style) and the layer toggles.
- **Bottom left:** Go to.
- **Bottom right:** legend and credits.
- **Right side:** the station panel slides in and leaves the scene interactive.
- **Top bar:** search.

## Phase 2: earthquakes beneath

### Layers

Each layer toggles on its own. Glow cloud and shells are on by default.

- **Glow cloud.**
  - Every event is a soft additive sprite about 160–400 m across, larger for bigger magnitudes.
  - Dense zones build into light, in a single blue hue that never appears on stations.
  - Each fragment is placed on the sprite's plane in world space and dropped if it would sit above the ground.
- **Density shells.**
  - A 72³ density grid over the map volume, from 20 km depth to the summit, smoothed and trimmed to below the ground surface.
  - Three nested isosurfaces enclose 70%, 45% and 20% of all events, from pale and translucent outside to near-opaque inside.
  - Fragments above the ground are dropped.
- **Dots.** One point per event, sized by magnitude, with fixed screen size. Events above the ground are not drawn.
- **Legend.** One density ramp and the shell percentages. The source line gives the catalog, count and time span.

### Ground

- **See-through.** A slider from 0 to 90%, default 0.
  - Above ground, a see-through ground is drawn over the underground layers, so they read as beneath it.
  - Below ground, the ground is drawn first, so the layers stay in front.
- **Cut away terrain.** A toggle with direction and position. It removes the terrain on one side of a vertical plane. The layers are not cut.
- **Block frame.**
  - The map area is an open-sided block down to 20 km: a faint floor grid, corner posts and a depth ruler (sea level, 5, 10, 15, 20 km).
  - There are no side walls. The open sides are how the default view shows the earthquakes without see-through.
- **Rule.** Nothing underground is ever visible through solid ground from above. This is tested with a screenshot from straight above, with every layer on and see-through at 0: no underground pixels outside the open sides.

### Default view and places

- **Default view.** The whole block from the south-west, slightly above ground level. The mountain and stations sit on top, and the earthquakes show through the open front.
- **Go to** gains "From below" (under the floor, looking up) and "Side on" (level with sea level).

## Visual system

From `tokens.css`:

- **Surfaces.** `#121211` and `#1a1a19`, hairlines at 8–16% white.
- **Type.** IBM Plex Sans and IBM Plex Mono with tabular figures.
- **Glow.** None in the interface. The glow cloud is data.
- **Motion.** Flights, the 2D flatten and the station panel are the only large motions, and all respect reduced motion.

## Errors and degraded states

- **No WebGL.** A static message and the station list as a table.
- **Summit tile fails to load.** The coarser level stays visible. After three failures the detail readout says "summit detail limited".
- **Slow connection.** The overview and stations appear first, and the summit fills in. The first frame needs only `terrain.json`, `overview.bin`, `overview.jpg`, `stations.json` and the twenty-four 8 m summit tiles, about 8 MB.
- **Stale snapshot.** The credits show the as-of date for stations and earthquakes.

## Testing

- **Build step (pytest).** Square-pixel request math, seam check, level reduction and tile slicing on a small synthetic grid, channel-code mapping, site merging, station count reconciliation, above-ground earthquake flagging.
- **Site (vitest).**
  - The copied cameraMath tests.
  - Tile selection: correct levels at given distances; a parent is kept until its children are ready; eviction never removes a displayed tile.
  - Ground sampling and hidden-marker math.
  - Panel states.
- **End to end (Playwright against `vite preview`).**
  - Load and see stations.
  - Fly to RCM and reach 1 m detail within 10 s.
  - Hold an arrow key, drag, and Ctrl-drag, checking the camera moved as expected.
  - Phase 2: toggle each layer; cut; see-through; the solid-ground rule screenshot.
- **Performance target.** 60 fps orbiting on an Apple-silicon laptop. First frame within 3 s on a 50 Mbit/s connection.

## Deployment

- The repo is `yaoderek/rainier-seismic-atlas`, public, because GitHub Pages on a personal account needs it.
- A GitHub Actions workflow runs `vite build` and deploys `site/dist` to Pages. The data bundle is committed under `site/public/atlas/` because CI does not fetch from USGS.
- Rebuilding the summit tiles rewrites about 290 MB. Regenerate rarely. If history grows past about 2 GB, move the tiles to an orphan data branch.
- Phase 1 replaces the mockup at the site root. The mockup moves to `/mockup/`.

## Out of scope

- Live waveforms, live status and data downloads.
- Chat or the Graph-RAG answer service.
- Temporary deployments (the 2025 node array Z5, the 2020–2023 summer arrays, the Nisqually bedload arrays). They would make a good "past deployments" layer later.
- A time slider or animation of earthquakes.
- Subsurface models: velocity or conductivity.
- Terrain beyond the 60 km area.

## Risks and open questions

- **Earthquake depth datum.** The mockup treats ComCat depth as kilometers below sea level. The negative depths support that, but PNSN's datum should be confirmed before phase 2 ships.
- **"Active" is metadata, not health.** Stations are active when their channels have no end date. A dead station still shows as active.
- **Upstream politeness.** A summit rebuild makes about 50 requests to USGS services. Rebuild rarely, with at most four at a time.
- **Imagery age and season.** The USGS imagery mosaic mixes years. Snow cover differs across tile boundaries in places.
