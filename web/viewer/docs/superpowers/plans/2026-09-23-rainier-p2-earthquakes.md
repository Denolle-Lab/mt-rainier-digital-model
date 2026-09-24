# Rainier Atlas Phase 2 (Earthquakes) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the earthquake catalog beneath the mountain as three toggleable layers (glow cloud, density shells, dots), plus see-through ground, a terrain cut, an explorable underside, and an open-sided block frame. Nothing underground ever shows through solid ground.

**Architecture:** `data/rainier/quakes.py` adds `quakes.bin` and `quakes.json` to the bundle. On the site, each layer is a module under `site/src/scene/quakes/` that attaches to `RainierScene` through its `scene`, `U` and `ground` hooks. The density grid and shell thresholds are pure functions. Ground clipping reuses the `groundKm()` GLSL from phase 1. The approved reference is `mockup/index.html`.

**Tech Stack:** as in phase 1.

**Spec:** `docs/superpowers/specs/2026-09-23-rainier-atlas-design.md` (the Phase 2 section)

## Global Constraints

- Earthquakes come from USGS ComCat: min lat 46.58, max lat 47.12, min lon −122.16, max lon −121.36, starting 1980-01-01, min magnitude −2. Depth is taken as km below sea level, so `y = −depth`.
- Earthquake layers use one blue hue: ramp `#121e2e → #173a66 → #2d6fc0 → #6fa6ec → #dcebff`. Stations never use blue.
- Glow sprite diameter `0.16 + 0.052 · clamp(mag, 0, 4.5)` km; gain 0.07; additive blending.
- Shells: a 72³ grid over x, z ∈ [−30, 30] km and y ∈ [−20, 4.6] km; Gaussian blur σ (1.2, 1.6, 1.2) cells; trimmed above the ground; isosurfaces enclosing 70%, 45% and 20% of the mass. Colors and opacities: `#2d6fc0` at 0.16, `#6fa6ec` at 0.30, `#dcebff` at 0.85.
- Dots: `(1.6 + 1.1 · clamp(mag + 0.5, 0, 5))` px times the device pixel ratio; color (0.62, 0.77, 0.96) at alpha 0.55.
- Rule: no underground fragment is drawn above the ground surface (`groundKm() − 0.02`); events above ground are not drawn.
- See-through defaults to 0, range 0–90%. Above ground the terrain draws after the layers; below ground it draws before them.
- The block frame goes down to 20 km: floor grid every 10 km, four corner posts, and a depth ruler at 0, 5, 10, 15, 20 km. There are no side walls.
- Default layers: glow and shells on, dots off, cut off. Default view: pos (−40, 9, 74), target (0, −5, 0).
- 2D view hides all earthquake layers and the block frame.

## Review Focus

- **Straight above, with every layer on and see-through at 0.** No blue pixel inside the terrain's screen footprint. This is the spec's rule; covered by the e2e pixel test in Task 5.
- **The camera below ground with see-through above 0.** The layers must not be painted over by the terrain underside. Covered by the render-order unit test in Task 4 and the "From below" screenshot in Task 5.
- **An empty or tiny catalog** (a refreshed build with a network failure yields 0 events). Shells must not throw, and layers show nothing with the legend reading "0 earthquakes". Covered in Task 2 (thresholds of an empty field) and Task 1 (the build refuses fewer than 1,000 events).
- **The cut plane passes through a station or the summit patch.** Stations on the removed side hide, and summit tiles are cut the same as the overview. Covered in Task 4 (tile materials share the cut uniforms; tested by checking the uniform objects are the same).
- **Switching to 2D with layers on, then back.** The layers return in the same state. Covered in Task 4 (`setView` test on the layer state).

---

### Task 1: Earthquake data

**Files:**
- Create: `data/rainier/quakes.py`, `data/tests/test_quakes.py`
- Modify: `data/rainier/build.py` (add a `quakes` step and validation), then regenerate `site/public/atlas/quakes.bin` and `quakes.json`

**Interfaces:**
- Consumes: `fetch.get`, `extent`, the overview heights (for the above-ground flag)
- Produces:
  - `parse_catalog(csv_text) -> list[(lon, lat, depth_km, mag, time)]`
  - `build_quakes(out_dir, cache_dir, overview, get) -> dict`, which writes `quakes.bin` (Float32 records of `x, y, z, mag`)
  - `quakes.json`: `{"count", "drawn", "aboveGround", "from", "to", "magMin", "magMax", "depthP50", "depthP90", "source"}`
- [ ] Step 1: Failing tests:
  - Rows with an empty depth or magnitude are skipped.
  - x and z use `extent.to_x` and `to_z`, and `y = −depth`.
  - An event at depth −5 km (5 km above sea level) under 1.5 km terrain counts in `aboveGround`.
  - `validate` fails on fewer than 1,000 events.
- [ ] Step 2: Run `.venv/bin/pytest data -q`. Expected: FAIL.
- [ ] Step 3: Implement with the ComCat CSV query: `https://earthquake.usgs.gov/fdsnws/event/1/query?format=csv&minlatitude=46.58&maxlatitude=47.12&minlongitude=-122.16&maxlongitude=-121.36&starttime=1980-01-01&minmagnitude=-2&orderby=time-asc`. Seed the cache from `/tmp/rmock/quakes.csv`.
- [ ] Step 4: Run the tests, then `python -m rainier.build --only quakes`. Expected: PASS, and about 15,660 events.
- [ ] Step 5: Commit: "Data: earthquake catalog for phase 2".

### Task 2: Density grid and shell thresholds

**Files:**
- Create: `site/src/scene/quakes/density.js`, `density.test.js`

**Interfaces:**
- Produces:
  - `GRID = {res: 72, xz: 30, bottom: -20, top: 4.6}`
  - `splat(records: Float32Array, grid) -> Float32Array`
  - `blur3d(field, n, sigmas) -> Float32Array`
  - `trimAboveGround(field, grid, elevKm) -> void`
  - `massThresholds(field, fractions) -> number[]`
  - `worldOf(i, j, k, grid) -> [x, y, z]`
- [ ] Step 1: Failing tests:
  - `splat` puts one event at (0, −5, 0) into the cell nearest the center, and drops events outside the grid.
  - `blur3d` preserves the total mass away from the edges (within 1%).
  - `massThresholds` on a field of `[4, 3, 2, 1]` with fraction 0.7 returns 3.
  - It returns 0 thresholds for an all-zero field without throwing.
  - `trimAboveGround` zeroes the cells above a flat 1 km ground.
- [ ] Step 2: Run `npx vitest run`. Expected: FAIL.
- [ ] Step 3: Implement by porting from `mockup/index.html` (the `shells` builder and `blur3d`).
- [ ] Step 4: Run. Expected: PASS.
- [ ] Step 5: Commit: "Site: earthquake density grid and shell thresholds".

### Task 3: The three layers and the block frame

**Files:**
- Create: `site/src/scene/quakes/cloud.js`, `dots.js`, `shells.js`, `frame.js`, `quakeLayers.js`, `quakeLayers.test.js`
- Modify: `site/src/data/bundle.js` (load `quakes.bin` and `quakes.json`; add them to the Bundle as `quakes: {records: Float32Array, meta}`)

**Interfaces:**
- Consumes: `RainierScene.scene`, `.renderer`, `.camera`, `.ground` (`texture`, `rect`, `glsl`, `elevKm`); density.js
- Produces: `class QuakeLayers`:
  - `constructor(rs: RainierScene, quakes)`
  - `set(layer: "cloud" | "shells" | "dots", on: boolean)`, `get state()`
  - `setVisibleAll(on)`, used by 2D
  - `dispose()`
  - `frame.js` exports `makeFrame(extent) -> {group, ticks: [{label, pos: THREE.Vector3}]}`. The depth ruler sits at the south-west corner, `(XMIN − 0.7, d, ZMAX)`.
- [ ] Step 1: Failing test (Three objects without a WebGL context):
  - `QuakeLayers` with a fake `rs` (a THREE.Scene, a camera, and a ground stub) creates three objects.
  - `set("dots", true)` makes the dots visible.
  - `state` reflects the toggles, with defaults `{cloud: true, shells: true, dots: false}`.
  - The cloud material's fragment shader contains `groundKm(`.
  - The shell materials have `onBeforeCompile` set.
- [ ] Step 2: Run. Expected: FAIL.
- [ ] Step 3: Implement by porting the cloud, dots and shells code and the frame block from `mockup/index.html`. The per-fragment billboard placement uses a `uViewInv` bound to `camera.matrixWorld`. The pixel scale is `drawingBufferHeight / (2 · tan(fov / 2))`, updated on resize.
- [ ] Step 4: Run. Expected: PASS.
- [ ] Step 5: Commit: "Site: glow cloud, density shells, dots and block frame".

### Task 4: Ground controls: see-through, cut, underside ordering

**Files:**
- Create: `site/src/scene/groundControls.js`, `groundControls.test.js`, `site/src/ui/LayerPanel.jsx`, `LayerPanel.test.jsx`
- Modify: `site/src/scene/RainierScene.js`:
  - `setSeeThrough(pct)` and `setCut({on, angle, offset})`
  - the per-frame `under` flag and render order (the terrain after the layers when above ground, before them when below)
  - summit tile materials share `U.clip`, `U.clipOn`, `U.alpha` and `U.under`
  - `setView("2d")` calls `layers.setVisibleAll(false)` and restores the previous state on 3D
- Modify: `site/src/scene/stationPose.js` / `PLACES`: add `under: {pos: [-22, -48, 40], target: [0, -6, 0]}` and `side: {pos: [0, -2, 78], target: [0, -6, 0]}`, and change `home` to `{pos: [-40, 9, 74], target: [0, -5, 0]}`

**Interfaces:**
- Produces:
  - `terrainOrder(under: boolean) -> number`: `-1` when under, `10` otherwise
  - `cutUniform(angleDeg, offsetKm) -> [nx, 0, nz, offset]`
  - `isUnder(cam, elevKm) -> boolean`
  - `LayerPanel({scene, layers})`: toggles with keys G, S, D, X, T, the see-through slider, and the cut sub-controls
- [ ] Step 1: Failing tests:
  - `terrainOrder(true) === -1`.
  - `cutUniform(90, 2)` is [0, 0, 1, 2] ± 1e-9.
  - `isUnder([0, -1, 0], () => 0.5)` is true.
  - The summit materials share the `U.clip` object (identity).
  - LayerPanel: clicking "Dots" calls `layers.set("dots", true)`; key "g" toggles the cloud; keys typed into the slider are ignored.
  - The 2D round trip restores `{cloud: true, shells: false, dots: true}` after it was set.
- [ ] Step 2: Run. Expected: FAIL.
- [ ] Step 3: Implement by porting the see-through and cut logic from `mockup/index.html`.
  - Terrain materials become transparent when `see > 0` and write depth only when `see == 0`.
  - Skirts are discarded when under ground.
  - Stations hide when under ground or on the cut-away side (StationLayer reads `scene.U`).
- [ ] Step 4: Run. Expected: PASS.
- [ ] Step 5: Commit: "Site: see-through ground, terrain cut, underside ordering, layer panel".

### Task 5: Legend, defaults, end-to-end and deployment

**Files:**
- Modify: `site/src/ui/Legend.jsx` (the earthquake density ramp, the shell percentages, and the catalog line from `quakes.json`), `GoTo.jsx` (add From below and Side on), `App.jsx` (mount QuakeLayers and LayerPanel), `site/e2e/atlas.spec.js`, `README.md`

- [ ] Step 1: Failing e2e tests:
  - **(f) Solid-ground rule.** Jump to a camera straight above the summit at 60 km (pos (0, 60, 0.001), target (0, 0, 0)) with all layers on and see-through 0. Screenshot the canvas. Count the pixels inside the central 60% whose blue channel exceeds red by more than 60 and green by more than 20. Expected: 0.
  - **(g)** "From below" shows the shells: the count of those pixels is above 2,000.
  - **(h)** Toggling Cut hides the stations on the cut side.
  - **(i)** 2D hides the frame ticks, and 3D brings them back.
- [ ] Step 2: Run `npx playwright test`. Expected: FAIL on (f)–(i) before the wiring, PASS after.
- [ ] Step 3: Implement the legend and GoTo additions and the App wiring.
- [ ] Step 4: Run the unit and e2e tests. Expected: PASS. Take screenshots of the default, below, see-through 45% and summit views, and look at them.
- [ ] Step 5: Update the README with the earthquake section and credits. Push. After the deployment, run (a) and (f) against the live URL.
- [ ] Step 6: Commit: "Phase 2: legend, defaults, e2e, deploy".
