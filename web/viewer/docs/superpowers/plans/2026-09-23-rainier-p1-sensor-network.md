# Rainier Atlas Phase 1 (Sensor Network) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the approved v3 mockup into a maintainable build: a Python data step that produces a static bundle, and a React + Vite + Three.js site that shows the Rainier seismic network on USGS terrain with the 1 m summit tiles, deployed to GitHub Pages.

**Architecture:** `data/` fetches public sources into `data/cache/` and writes `site/public/atlas/`. `site/` is a static React app whose 3D scene is a plain Three.js class (`RainierScene`) owned by one component, with HTML overlays for markers and panels. Pure logic (projection, tile selection, sight lines, grouping, search) lives in small modules with unit tests. Rendering code is ported from `mockup/index.html`, which is the approved reference.

**Tech Stack:** Python 3.12 + numpy + pytest. React 18.3.1, Three 0.169.0, Vite, Vitest, Testing Library, Playwright. The versions match `coszo-hub/RCA-Atlas/src/atlas_map/package.json`.

**Spec:** `docs/superpowers/specs/2026-09-23-rainier-atlas-design.md`

## Global Constraints

- Map center 46.8528°N, 121.7604°W. Local coordinates are equirectangular kilometers: `x = (lon − LON0) · 111.32 · cos(LAT0)`, `z = −(lat − LAT0) · 111.13`, `y` = elevation in km. Vertical scale 1×.
- Every ArcGIS export request uses square pixels in degrees: `width/height == Δlon/Δlat`.
- Overview area: lon −122.16 to −121.36, lat 46.58 to 47.12; 1800 × 1215 elevation samples; 4096 × 2765 imagery.
- Summit patch: pixel 9e-6°, 12288 × 8192 cells centered on the map center; levels at 8, 4, 2, 1 cells; tiles of 256 cells with a shared edge (257² Uint16 decimeters).
- Tile refinement at camera distance < 2.5 × tile width. The parent stays until all four children are ready.
- Navigation is copied from `RCA-Atlas/src/atlas_map`: drag moves; Ctrl/Cmd/Shift-drag or right-drag rotates; scroll zooms to the cursor; held arrows glide at 0.3 × distance per second; flights take 1.8 s with an eased arc (1.3 s to a point); reduced motion makes flights instant; the camera may go below ground.
- Station flight: 9 km out, 28° above the horizon, on the side away from the summit (current heading within 1 km of the summit), 1.8 s.
- Surfaces `#121211` / `#1a1a19`, hairlines 8–16% white, IBM Plex Sans and Mono with tabular figures; tokens copied verbatim.
- Glyph and color together for every instrument kind; no blue hue on stations (blue is reserved for earthquakes in phase 2).
- Bundle total under 600 MB. First frame needs about 8 MB.
- Vite `base` is `/rainier-seismic-atlas/`.

## Review Focus

- **The camera goes below ground and a station flight starts from there.** The flight must end above ground at the 9 km / 28° framing, not buried. This is covered by the `stationPose` tests in Task 10.
- **A station outside the map area (`onMap: false`) is searched or picked.** It must not fly the camera off the map. It opens the panel with "outside the map area". Covered in Task 12 (search and panel tests).
- **Summit tiles fail to load (404 or offline).** The coarser level stays and the view never has a hole. Covered in Task 9 (`selectTiles` with failed children).
- **Arrow keys pressed while the search box has focus.** They must not move the camera. Covered by the copied `isMoveKey` tests (Task 1) and the search test in Task 12.
- **Two co-located station codes (Longmire) and the regional stations.** Counts must reconcile: sites, stations and kinds in the header equal the bundle. Covered in Task 5 (merge test) and Task 12 (header test).

## File structure

```text
.gitignore
README.md
mockup/index.html, mockup/data.js         (moved from the root; LOD path → ../atlas/summit/)
.github/workflows/pages.yml
data/requirements.txt                     numpy, pytest
data/rainier/__init__.py
data/rainier/extent.py                    map constants, projection, square-pixel bbox math
data/rainier/geotiff.py                   uncompressed GeoTIFF reader (tiled or stripped, float32)
data/rainier/fetch.py                     cached HTTP GET (the only network code)
data/rainier/terrain.py                   overview elevation + imagery
data/rainier/summit.py                    summit patch pieces, seam check, level pyramid
data/rainier/stations.py                  FDSN parse, instrument kinds, sites, majors
data/rainier/build.py                     orchestrates, validates, writes manifest.json
data/major_stations.json
data/tests/test_*.py
site/package.json, site/vite.config.js, site/index.html, site/playwright.config.js
site/public/atlas/                        the bundle (terrain/, summit/, stations.json, manifest.json)
site/src/main.jsx, site/src/App.jsx
site/src/styles/tokens.css, app.css
site/src/test/setup.js
site/src/data/bundle.js, kinds.js, search.js, format.js
site/src/scene/geo.js, cameraMath.js, gridGeometry.js, ground.js, summitLod.js, occlusion.js
site/src/scene/terrainMaterial.js, RainierScene.js
site/src/overlay/ring.js, labels.js, StationLayer.js, overlay.css
site/src/ui/Header.jsx, Search.jsx, Controls.jsx, GoTo.jsx, StationPanel.jsx, Legend.jsx, Tooltip.jsx, Glyph.jsx, ui.css
site/e2e/atlas.spec.js
```

---

### Task 1: Restructure the repo and scaffold both halves

**Files:**
- Move: `index.html`, `data.js` → `mockup/`; `lod/` → `site/public/atlas/summit/`
- Modify: `mockup/index.html` (fetch `../site/public/atlas/summit/` locally; on Pages the mockup is served at `/mockup/` and the bundle at `/atlas/`, so use `../atlas/summit/`)
- Create: `.gitignore`, `data/requirements.txt`, `data/rainier/__init__.py`, `site/package.json`, `site/vite.config.js`, `site/index.html`, `site/src/main.jsx`, `site/src/App.jsx` (placeholder "Loading…"), `site/src/styles/tokens.css` and `app.css` (copied verbatim from RCA-Atlas), `site/src/test/setup.js` (copied), `site/src/scene/cameraMath.js` and `cameraMath.test.js` (copied; drop `viewPose` and its test, since Rainier has no region views)

**Interfaces:**
- Produces: `ease, moveStep, isTypingTarget, motionDuration, approach, isMoveKey` from `site/src/scene/cameraMath.js`.

- [ ] Step 1: `git mv index.html data.js mockup/`, `mkdir -p site/public/atlas && git mv lod site/public/atlas/summit`. In `mockup/index.html`, replace `fetch("lod/index.json")` with `fetch("../atlas/summit/index.json")` and the `lod/` prefixes in the tile and image URLs with `../atlas/summit/`.
- [ ] Step 2: Write `.gitignore`: `node_modules/`, `site/dist/`, `data/cache/`, `.venv/`, `__pycache__/`, `test-results/`, `playwright-report/`.
- [ ] Step 3: `site/package.json` with the same dependency versions as RCA-Atlas `atlas_map`, minus `uplot`. Scripts: `dev`, `build`, `preview`, `test` (`vitest run`), `e2e` (`playwright test`). `site/vite.config.js`: `base: "/rainier-seismic-atlas/"`, react plugin, dev server on 127.0.0.1:5176, test config copied (jsdom, setup file, include pattern).
- [ ] Step 4: Copy `cameraMath.js` and `cameraMath.test.js`; delete `viewPose` and its test and the `geo.js` import.
- [ ] Step 5: `cd site && npm install && npx vitest run`. Expected: the cameraMath tests PASS.
- [ ] Step 6: `python3 -m venv .venv && .venv/bin/pip install -r data/requirements.txt && .venv/bin/pytest data -q`. Expected: "no tests ran" (exit code 5 is fine at this step).
- [ ] Step 7: Commit: "Restructure: mockup/ and site/public/atlas/summit; scaffold data/ and site/".

### Task 2: Extent, projection and the GeoTIFF reader

**Files:**
- Create: `data/rainier/extent.py`, `data/rainier/geotiff.py`, `data/tests/test_extent.py`, `data/tests/test_geotiff.py`

**Interfaces:**
- Produces:
  - `LON0, LAT0, KX, KZ` (km per degree), `to_x(lon)`, `to_z(lat)`
  - `OVERVIEW = Box(west, south, east, north)`, `OVERVIEW_SIZE = (1800, 1215)`
  - `square_size(box, width) -> (width, height)`, which raises `ValueError` if the pixels would not be square
  - `SUMMIT = Box(...)`, `SUMMIT_PIXEL = 9e-6`, `SUMMIT_CELLS = (12288, 8192)`
  - `read_tiff(bytes) -> np.ndarray` (float32, rows north→south)
  - `write_tiff(array) -> bytes`, for tests only

- [ ] Step 1: Failing tests:

```python
# data/tests/test_extent.py
import math, pytest
from rainier import extent as E

def test_projection_origin_and_scale():
    assert E.to_x(E.LON0) == 0 and E.to_z(E.LAT0) == 0
    assert E.to_x(E.LON0 + 1) == pytest.approx(111.32 * math.cos(math.radians(E.LAT0)))
    assert E.to_z(E.LAT0 + 1) == pytest.approx(-111.13)   # north is −z

def test_overview_request_has_square_degree_pixels():
    w, h = E.square_size(E.OVERVIEW, 1800)
    assert (w, h) == (1800, 1215)
    assert (E.OVERVIEW.east - E.OVERVIEW.west) / w == pytest.approx((E.OVERVIEW.north - E.OVERVIEW.south) / h, rel=1e-3)

def test_square_size_rejects_a_box_that_cannot_be_square():
    with pytest.raises(ValueError):
        E.square_size(E.Box(0, 0, 1, 0.7777), 1000)   # 777.7 px tall is not a whole number of pixels

def test_summit_patch_is_centered_and_sized():
    b = E.SUMMIT
    assert (b.west + b.east) / 2 == pytest.approx(E.LON0) and (b.south + b.north) / 2 == pytest.approx(E.LAT0)
    assert (b.east - b.west) / E.SUMMIT_PIXEL == pytest.approx(12288)
    assert (b.north - b.south) / E.SUMMIT_PIXEL == pytest.approx(8192)
```

```python
# data/tests/test_geotiff.py
import numpy as np
from rainier.geotiff import read_tiff, write_tiff

def test_round_trip_stripped():
    a = np.arange(12, dtype=np.float32).reshape(3, 4)
    assert np.array_equal(read_tiff(write_tiff(a)), a)

def test_round_trip_tiled_with_partial_edge_tiles():
    a = np.random.default_rng(1).random((300, 520), dtype=np.float32)
    assert np.array_equal(read_tiff(write_tiff(a, tile=256)), a)
```

- [ ] Step 2: `.venv/bin/pytest data -q`. Expected: FAIL (module not found).
- [ ] Step 3: Implement.
  - `extent.py`: a `Box` namedtuple. `square_size` computes `h = w * (north − south) / (east − west)` and raises unless `abs(h − round(h)) < 1e-6 · h`.
  - Use exact overview bounds that satisfy the square-pixel rule: `Box(-122.16, 46.58, -121.36, 46.58 + 1215 * 0.8 / 1800)`. The north edge becomes 47.12; check it.
  - `SUMMIT = Box(LON0 − 6144 · p, LAT0 − 4096 · p, LON0 + 6144 · p, LAT0 + 4096 · p)`.
  - `geotiff.py`: the reader from the prototype (`/tmp/rmock/tifread.py`: IFD parse; tags 256, 257, 273, 279, 322–325; float32; uncompressed only). Raise `ValueError` for a compression tag other than 1. Add `write_tiff` for tests only: a minimal little-endian writer for the stripped layout and for a tiled layout that pads edge tiles.
- [ ] Step 4: `.venv/bin/pytest data -q`. Expected: PASS.
- [ ] Step 5: Commit: "Data: extent, square-pixel rule, GeoTIFF reader".

### Task 3: Cached fetch and the overview terrain

**Files:**
- Create: `data/rainier/fetch.py`, `data/rainier/terrain.py`, `data/tests/test_terrain.py`

**Interfaces:**
- Consumes: `extent.OVERVIEW`, `square_size`, `read_tiff`
- Produces:
  - `fetch.get(url, cache_path, opener=urllib.request.urlopen) -> bytes`. It reads the cache if present. It rejects HTML error bodies (content starting with `<`) with `FetchError`.
  - `terrain.build_overview(out_dir, cache_dir, get=fetch.get) -> dict`, the `terrain.json` content: `{cols, rows, x0, z0, dx, dz, min, max, source}`. It writes `terrain/overview.bin` (Int16 m, rows north→south) and `terrain/overview.jpg`.

- [ ] Step 1: Failing tests:
  - `fetch.get` returns cached bytes without calling the opener.
  - It raises `FetchError` on a body that starts with `b"<html"`.
  - `build_overview` with a fake `get` that returns `write_tiff(np.full((1215, 1800), 1500, np.float32))` for elevation and `b"\xff\xd8jpeg"` for imagery writes `overview.bin` of 1800 × 1215 × 2 bytes, all 1500. `terrain.json` has `dx ≈ 0.8 · KX / 1800` and `x0 = to_x(west)`.
  - The requested URLs contain `size=1800,1215` and `size=4096,2765`.
- [ ] Step 2: Run. Expected: FAIL.
- [ ] Step 3: Implement.
  - The URLs are the prototype's (the 3DEP `exportImage`, with `pixelType=F32`, `interpolation=RSP_BilinearInterpolation`, `format=tiff`; USGSImageryOnly `export` as `jpg`), and both use `bboxSR=4326&imageSR=4326`.
  - NODATA (below −100 m, or not finite) is filled with the grid minimum.
- [ ] Step 4: Run. Expected: PASS.
- [ ] Step 5: Commit: "Data: cached fetch and overview terrain".

### Task 4: Summit pyramid

**Files:**
- Create: `data/rainier/summit.py`, `data/tests/test_summit.py`

**Interfaces:**
- Consumes: `extent.SUMMIT`, `SUMMIT_PIXEL`, `SUMMIT_CELLS`, `read_tiff`, `fetch.get`
- Produces:
  - `assemble(pieces: dict[(r, c)] -> ndarray, piece=2048) -> ndarray`
  - `seam_steps(dem, piece) -> list[float]`
  - `pyramid(dem, out_dir, tile=256, factors=(8, 4, 2, 1)) -> list[level dicts]`
  - `build_summit(out_dir, cache_dir, get=fetch.get) -> dict`, the `summit/index.json` content in exactly the mockup's format:

```json
{"patch": {"west_km", "north_km", "width_km", "height_km"}, "tile": 256,
 "levels": [{"level", "cell_x_km", "cell_z_km", "tiles_x", "tiles_z", "chunk_w", "chunk_h"}]}
```

- Imagery chunks: `summit/img/img{level}_{r}_{c}.jpg`, of size `min(level_w, 3072) × min(level_h, 2048)`.

- [ ] Step 1: Failing tests on a synthetic 64 × 96 DEM with `tile=8` and `factors=(4, 2, 1)`:
  - Tile `(level 0, 0_0)` has 9 × 9 Uint16 samples equal to `round(mean(block) · 10)`.
  - Adjacent tiles share their edge column: the last column of `0_0` equals the first column of `0_1`.
  - The last tile row and column are padded by edge replication.
  - `seam_steps` on two pieces offset by 200 m reports about 200. `build_summit` raises `ValueError("summit seam")` when any seam step exceeds 2 m.
  - For the real constants, `cell_x_km` of level 3 is about 0.000685 and `cell_z_km` is about 0.00100.
- [ ] Step 2: Run. Expected: FAIL.
- [ ] Step 3: Implement from the prototype's build (`/tmp/rmock/lod`). Pieces are 2048² elevation requests laid out as 4 rows × 6 columns. Cache names are `dem_{r}_{c}.tif` and `img{level}_{r}_{c}.jpg`, so the existing downloads can seed `data/cache/summit/`.
- [ ] Step 4: Run. Expected: PASS.
- [ ] Step 5: Commit: "Data: summit tile pyramid with seam check".

### Task 5: Stations, instrument kinds, sites and majors

**Files:**
- Create: `data/rainier/stations.py`, `data/major_stations.json`, `data/tests/test_stations.py`

**Interfaces:**
- Consumes: `fetch.get`, `extent.to_x`, `extent.to_z`, `extent.OVERVIEW`
- Produces: `parse_channels(text) -> list[dict]`, `kind_of(code) -> str | None` (None for state-of-health channels; raises `KeyError` for an unknown code), `build_stations(cache_dir, get) -> dict`. `stations.json`:

```json
{"asOf": "2026-09-23", "kinds": ["seismometer", "geophone", "infrasound", "accelerometer", "gnss", "tiltmeter", "strainmeter"],
 "sites": [{"id": "UW.LON", "name": "Longmire", "codes": ["UW.LON", "UW.LO2", "UW.LON9"], "lat", "lon", "x", "z", "elev",
            "kinds": ["seismometer", "accelerometer", "tiltmeter"], "since": "2009-01-28", "onMap": true, "major": "Longmire, broadband + accelerometer + tiltmeters",
            "stations": [{"code": "UW.LON", "network": "UW", "operator": "Pacific Northwest Seismic Network", "siteName": "Longmire, WA, USA", "elev": 853, "depth": 0,
                          "since": "2019-06-19", "instruments": [{"kind": "seismometer", "band": "broadband", "channels": ["HHE", "HHN", "HHZ"], "rate": 100}]}]}],
 "excluded": [{"code": "C0.PALI", "reason": "duplicate of CC.PALI"}], "counts": {"stations", "sites", "onMap"}}
```

- Kind table (2-letter prefix):
  - BH, HH → seismometer, broadband
  - EH → seismometer, short-period
  - CH → geophone
  - BD, HD, CD → infrasound
  - EN, HN → accelerometer
  - GA, GE, GN, GS, GP, GL → gnss
  - HA, HK → tiltmeter
  - BS, LS → strainmeter
- State-of-health ignore list: AC, CP, DE, DS, HU, LC, LD, LH, LI, LK, LN, LO, LP, LR, LW, ME, OC, QB, QD, QG, QL, QR, QW, RA, RC, RD, RE, RK, RR, RS, SB, SC, SD, SI, SM, SN, SP, SR, SS, ST, SW, VA, VB, VC, VD, VE, VF, VH, VK, VM, VP, VS, VV.
  - The LD and LI channels at CC.PR04 (humidity, rainfall) count as state of health in phase 1.
  - LN at NP stations is a low-rate accelerometer; ignore it, because HN covers the kind.
- Operators: CC → USGS Cascades Volcano Observatory; UW → Pacific Northwest Seismic Network; NP → USGS National Strong-Motion Project; PB → EarthScope borehole network.
- Excluded: the SY network, and C0.PALI (a duplicate of CC.PALI).
- Sites: codes within 150 m join a site. The site id and name come from the code with the earliest `since`. The name is the FDSN SiteName, trimmed of ", WA, USA" and similar suffixes.

- [ ] Step 1: Failing tests:
  - `kind_of("HHZ") == "seismometer"`, `kind_of("VM1") is None`, and `kind_of("XYZ")` raises `KeyError`.
  - A three-line synthetic channel text for LON, LO2 and LON9 (same coordinates) merges into one site with kinds seismometer, accelerometer and tiltmeter, id "UW.LO2" (earliest since 2009), and name "Longmire".
  - The SY and C0.PALI rows are excluded and recorded.
  - A station at lon −122.3 has `onMap False`.
  - Majors come from `major_stations.json` by code.
- [ ] Step 2: Run. Expected: FAIL.
- [ ] Step 3: Implement. Queries:
  - channel level: `https://service.earthscope.org/fdsnws/station/1/query?latitude=46.853&longitude=-121.760&maxradius=0.45&endafter=<asOf>&level=channel&format=text`
  - station level (for SiteName): the same with `level=station`
  - Parse the pipe-separated text.
  - `data/major_stations.json` holds the nine majors with the spec's descriptions: STAR St. Andrews Rock; RCM Camp Muir; RCS Camp Schurman; MILD Mildred Point; PARA Paradise; RER Emerald Ridge; FMW Mount Fremont; LON Longmire; OBSR Observation Rock.
- [ ] Step 4: Run. Expected: PASS.
- [ ] Step 5: Commit: "Data: stations, instrument kinds, sites, majors".

### Task 6: Build, validation, manifest and the real bundle

**Files:**
- Create: `data/rainier/build.py`, `data/tests/test_build.py`
- Generate: `site/public/atlas/terrain/*`, `site/public/atlas/summit/*` (replacing the moved mockup tiles), `site/public/atlas/stations.json`, `site/public/atlas/manifest.json`

**Interfaces:**
- Consumes: `build_overview`, `build_summit`, `build_stations`
- Produces:
  - `validate(out_dir, terrain, summit, stations) -> list[str]`, the error list (empty means valid)
  - CLI: `python -m rainier.build --out site/public/atlas --cache data/cache [--only terrain,summit,stations]`
  - `manifest.json`: `{"built": ISO time, "sources": [{"name", "url", "fetched", "license"}], "sizeBytes"}`

- [ ] Step 1: Failing tests for `validate`:
  - A station count that doesn't match (`counts.stations` ≠ number of station entries) yields an error.
  - A bundle directory over the byte limit yields "bundle too large" (pass `limit=100` for the test).
  - Summit level 0 against overview RMS > 30 m yields an error (synthetic arrays).
- [ ] Step 2: Run. Expected: FAIL.
- [ ] Step 3: Implement.
  - `main()` runs the builders, then validates. It exits 1 and prints the errors if validation fails.
  - It writes `manifest.json` last.
- [ ] Step 4: Run the unit tests. Expected: PASS.
- [ ] Step 5: Seed the cache so the build does not re-download 400 MB:
  - `mkdir -p data/cache/summit data/cache/overview`
  - `cp /tmp/rmock/lod/raw/* data/cache/summit/`
  - `cp /tmp/rmock/dem.tif data/cache/overview/dem.tif`
  - `cp /tmp/rmock/img.jpg data/cache/overview/img.jpg`
  - Cache file names must match the builders' names.
- [ ] Step 6: Run `cd data && ../.venv/bin/python -m rainier.build --out ../site/public/atlas --cache cache`. Expected: it validates and prints the counts (52 stations; sites; 39 on map) and a total size under 600 MB.
- [ ] Step 7: Commit the bundle and code: "Data: build, validation, manifest; generate the phase 1 bundle".

### Task 7: Site data layer: bundle loader, kinds, format

**Files:**
- Create: `site/src/data/bundle.js`, `kinds.js`, `format.js` and their tests; `site/src/scene/geo.js` and its test

**Interfaces:**
- Produces:
  - `loadBundle(base = import.meta.env.BASE_URL + "atlas/") -> Promise<Bundle>`. The Bundle is `{terrain: {meta, heights: Int16Array, image: HTMLImageElement}, summit: indexJson, stations: stationsJson, siteById, majors: site[], base}`. It rejects with `BundleMissingError` on a 404 of `terrain/terrain.json`.
  - `KINDS`: an ordered array of `{key, label, color, glyph}`.
  - `fmtElev(m)` gives "3,076 m"; `fmtSince(date)` gives "since 2019".
  - `toX`, `toZ`, `fromX`, `fromZ`, `LON0`, `LAT0`, `KX`, `KZ`.
- `KINDS`, in fixed order; the colors must pass `validate_palette.js` against `#121211` in dark mode, adjacent pairs:

| key | label | color | glyph |
|---|---|---|---|
| seismometer | Seismometer | #d95926 | triangle |
| geophone | Geophone | #c98500 | circle |
| infrasound | Infrasound | #d55181 | hexagon |
| accelerometer | Accelerometer | #199e70 | square |
| gnss | GNSS | #a58be0 | diamond |
| tiltmeter | Tiltmeter | #d9d6cc | bar |
| strainmeter | Borehole strainmeter | #8fae5a | cross |

- [ ] Step 1: Failing tests:
  - `toX(LON0 + 1)` is about 76.16.
  - `fmtElev(3076.4)` is "3,076 m".
  - `loadBundle` with a mocked `fetch` builds `siteById` and `majors` in `major_stations.json` order.
  - A 404 raises `BundleMissingError`.
  - `KINDS` keys equal the `stations.json` `kinds` list.
- [ ] Step 2: Run `npx vitest run`. Expected: FAIL.
- [ ] Step 3: Implement.
- [ ] Step 4: Run the palette validator: `node <dataviz>/scripts/validate_palette.js "#d95926,#c98500,#d55181,#199e70,#a58be0,#d9d6cc,#8fae5a" --mode dark --surface "#121211"`. Adjust failing steps and update the table.
- [ ] Step 5: Run the tests. Expected: PASS.
- [ ] Step 6: Commit: "Site: bundle loader, instrument kinds, formatting, projection".

### Task 8: Grid geometry and ground sampling

**Files:**
- Create: `site/src/scene/gridGeometry.js`, `gridGeometry.test.js`, `ground.js`, `ground.test.js`

**Interfaces:**
- Produces:
  - `gridArrays(n, m, posAt(c, r) -> [x, z, sx, sz], heights: Float32Array, uvAt(c, r) -> [u, v], skirtKm = 0) -> {position, uv, normal, skirt, index}`. These are the mockup's `gridGeometry` arrays without Three.
  - `gridGeometry(...) -> THREE.BufferGeometry`, a thin wrapper.
  - `makeGround(meta, heights) -> {elevKm(x, z) | null, texture: THREE.DataTexture, rect: THREE.Vector4, glsl: string}`. The texture holds 2 × 2 block maxima in km. `glsl` defines `float groundKm(vec2 xz)`.
- [ ] Step 1: Failing tests:
  - A 3 × 2 grid gives 6 vertices, 2 × 1 × 6 indices, and a normal of (0, 1, 0) on flat heights.
  - A tilted plane `h = x` gives a normal ∝ (−1, 1, 0).
  - `skirtKm = 0.05` adds `2·(n + m)` vertices, each 0.05 below its edge source, with `skirt = 1`.
  - `elevKm` interpolates bilinearly and returns null outside the grid.
  - The ground texture's max-pooling keeps a one-sample spike.
- [ ] Step 2: Run. Expected: FAIL.
- [ ] Step 3: Implement by porting `gridGeometry` and the height texture from `mockup/index.html`.
- [ ] Step 4: Run. Expected: PASS.
- [ ] Step 5: Commit: "Site: grid geometry and ground sampling".

### Task 9: Summit level of detail

**Files:**
- Create: `site/src/scene/summitLod.js`, `summitLod.test.js`

**Interfaces:**
- Consumes: `gridGeometry`, the summit index
- Produces:
  - `tileBounds(index, k, ty, tx) -> {x0, z0, ex, ez}`
  - `selectTiles(index, cam: [x, y, z], state(k, ty, tx) -> "ready" | "loading" | "failed" | undefined, heightRange(k, ty, tx) -> [lo, hi]) -> {show: key[], want: key[]}`, with keys like `"k/ty_tx"`. It is pure.
  - `class SummitLod { constructor(index, base, makeMaterial(texture) -> Material, group: THREE.Group); update(camera) -> finestLevel | -1; get allRootsReady(); dispose() }`. It has at most six requests in flight, drops queued tiles unwanted for 30 frames, and evicts beyond 360 tiles (never a shown tile), releasing image chunks by reference count.
- [ ] Step 1: Failing tests with a tiny index (2 × 1 roots, 3 levels, 1 km tiles):
  - A camera 50 km away shows the 2 roots and wants only the roots.
  - A camera 0.5 km above root `0/0_0` with all children ready shows the 4 level-1 children of root 0 and root `0/0_1`.
  - The same camera with one child "loading" shows root `0/0_0` and wants all 4 children.
  - A child "failed" keeps the parent shown.
  - A shown tile is never evicted (unit-test the eviction helper `evictable(tiles, shown, frame)`).
- [ ] Step 2: Run. Expected: FAIL.
- [ ] Step 3: Implement. Port from `mockup/index.html` (`select`, `pump`, `request`, `getChunk`, and the eviction block), with the selection logic moved into `selectTiles`.
- [ ] Step 4: Run. Expected: PASS.
- [ ] Step 5: Commit: "Site: summit level-of-detail selection and loader".

### Task 10: The scene: terrain, styles, 2D, navigation and flights

**Files:**
- Create: `site/src/scene/terrainMaterial.js`, `site/src/scene/RainierScene.js`, `site/src/scene/stationPose.js`, `stationPose.test.js`

**Interfaces:**
- Consumes: cameraMath, gridGeometry, ground, SummitLod, bundle
- Produces:
  - `stationPose(site: {x, z, y}, cam: [x, y, z]) -> {pos, target}` (9 km, 28°, away from the summit)
  - `PLACES`: `{key: {label, pos, target}}` for home, summit, paradise, carbon, white, nisqually
  - `terrainMaterial(U, map, {hole}) -> ShaderMaterial`. Uniforms: `uStyle` (0 photo, 1 mono, 2 contours, eased), `uFlat` (0–1), `uClip`, `uClipOn`, `uAlpha`, `uHole`, `uHoleOn`, `uUnder`.
  - `class RainierScene`:
    - `constructor(canvas, bundle)`
    - properties: `camera`, `controls`, `ground`, `frame: {dist, under, finest}`, `onFrame`
    - `flyTo(placeKey)`, `flyToSite(site)`, `jumpTo(placeKey)`, `setView("3d" | "2d")`, `setStyle("photo" | "mono" | "contours")`, `project(x, y, z)`, `dispose()`
    - hooks for phase 2: `scene`, `U`
- [ ] Step 1: Failing tests for `stationPose`:
  - A site at (5, 2.0, 0) gives a camera 9 km away, at elevation angle 28° ± 0.5°, on +x.
  - A site within 1 km of the summit keeps the heading from `cam`.
  - The pose is above the ground height of the site.
- [ ] Step 2: Run. Expected: FAIL.
- [ ] Step 3: Implement `stationPose` and `PLACES`.
  - Home (phase 1): pos (−34, 30, 58), target (0, 0.5, 2), framing the terrain from above. Phase 2 moves home to the block view.
  - Summit: (−0.55, 4.72, 0.95) → (0.05, 4.33, 0).
  - Paradise, Carbon, White and Nisqually: target at the place (Paradise 46.786, −121.735; Carbon River 46.99, −121.92; White River 46.90, −121.64; Nisqually 46.74, −121.80), with the camera 12 km out at 35° from the south-west.
- [ ] Step 4: Implement `terrainMaterial`: the mockup's photo shader, plus:
  - mono: luminance of a neutral hillshade
  - contours: the Axial fragment code (100 m lines, 500 m heavy) over a dark fill with faint shade
  - `uFlat` multiplies `position.y` by `(1 − uFlat)` in the vertex shader
- [ ] Step 5: Implement `RainierScene`.
  - Port the renderer, lights, base terrain, SummitLod and near-plane tracking from the mockup.
  - Port the OrbitControls configuration, key handlers, `_fly` and `_tick` verbatim from `atlas_map/src/scene/AtlasScene.js`, with `maxPolarAngle = Math.PI`.
  - `setView` copies AtlasScene's `setView`, with `uFlat` approached at speed 5 and 2D locking the polar angle.
  - `flyToSite` uses `stationPose` with `ground.elevKm`.
  - Set `window.__rainier = this` in development and test builds.
- [ ] Step 6: `npx vitest run`. Expected: PASS. Then `npm run dev`, open the page, and check terrain, summit tiles and the flights.
- [ ] Step 7: Commit: "Site: scene, terrain styles, 2D, copied navigation, station framing".

### Task 11: Station markers

**Files:**
- Create: `site/src/overlay/ring.js`, `ring.test.js`, `labels.js`, `labels.test.js` (both copied from RCA-Atlas and adapted), `site/src/scene/occlusion.js`, `occlusion.test.js` (copied verbatim), `site/src/overlay/StationLayer.js`, `overlay.css`

**Interfaces:**
- Consumes: RainierScene (`project`, `frame`, `camera`, `ground`), bundle
- Produces: `ringSvg(kinds: string[], size) -> string` (one arc segment per kind, in `KINDS` order and color). `class StationLayer`:
  - `constructor(container, bundle, scene, {onHover(site, ev | null), onClick(site)})`
  - `update()`, `setSelected(id)`, `dispose()`
  - Markers behind terrain fade to 12% with no label or hover. All markers hide when `scene.frame.under`.
  - Labels show codes. Collisions are resolved by `place()` with priority major 2, other 1.
- [ ] Step 1: Failing tests:
  - `ringSvg(["seismometer", "infrasound"], 16)` has 2 `path.seg` elements with the two colors.
  - A single kind gives a full circle.
  - The copied occlusion and label tests pass unchanged.
- [ ] Step 2: Run. Expected: FAIL.
- [ ] Step 3: Implement.
- [ ] Step 4: Run. Expected: PASS.
- [ ] Step 5: Commit: "Site: station ring markers with occlusion and labels".

### Task 12: Interface: header, search, controls, go-to, station panel, legend, tooltip

**Files:**
- Create: `site/src/data/search.js` and test; `site/src/ui/Header.jsx`, `Search.jsx`, `Controls.jsx`, `GoTo.jsx`, `StationPanel.jsx`, `Legend.jsx`, `Tooltip.jsx`, `Glyph.jsx` (add a `cross` shape), `ui.css`, tests for Header, Search, StationPanel and GoTo; modify `App.jsx`

**Interfaces:**
- Consumes: bundle, RainierScene, StationLayer
- Produces:
  - `searchStations(bundle, q) -> [{id, title, sub}]`: matches code, network code, or site name, case-insensitive; majors rank first; at most 8 results.
  - `StationPanel({site, bundle, onClose})`
  - `links(station) -> [{label, url}]`:
    - EarthScope MDA `https://ds.iris.edu/mda/{net}/{sta}`
    - StationXML `https://service.earthscope.org/fdsnws/station/1/query?network={net}&station={sta}&level=response`
    - PNSN `https://pnsn.org/seismograms/{net}/{sta}` for UW
    - USGS CVO `https://www.usgs.gov/volcanoes/mount-rainier/science` for CC
    - dataselect for the last hour of the first vertical channel
- [ ] Step 1: Failing tests:
  - Searching "muir" returns UW.RCM first.
  - Searching "pali" returns CC.PALI once (the duplicate is excluded).
  - The panel for Longmire lists three codes and the instrument lines "Broadband seismometer · HHE HHN HHZ · 100 Hz".
  - A PB station has no PNSN link.
  - An `onMap: false` site shows "outside the map area" and no fly button.
  - Header counts equal the bundle's `counts`.
  - Pressing ArrowUp in the search box moves the list selection and does not call `scene.flight`. Assert that `isMoveKey` is false for that event.
  - GoTo renders six places and nine major stations.
- [ ] Step 2: Run. Expected: FAIL.
- [ ] Step 3: Implement.
  - Layout per the spec: header with search at top left; controls with View and Style at top right; GoTo at bottom left; legend at bottom right; the panel slides in on the right at 440 px (`--right-inset` changes, as in RCA-Atlas).
  - The tooltip reuses the `.tip` styles.
- [ ] Step 4: Run. Expected: PASS.
- [ ] Step 5: Commit: "Site: header, search, controls, go-to, station panel, legend".

### Task 13: End-to-end, performance, deployment

**Files:**
- Create: `site/playwright.config.js`, `site/e2e/atlas.spec.js`, `.github/workflows/pages.yml`
- Modify: `README.md`

- [ ] Step 1: Write the Playwright spec against `vite preview` (webServer in the config, base path included):
  - (a) On load, at least 30 visible `.station` markers, and the header shows the counts.
  - (b) Clicking "RCM" in Go to, then waiting until `window.__rainier.frame.finest >= 1`: the camera distance to the target is 9 ± 0.5 km, and `#panel` shows "Camp Muir".
  - (c) Holding ArrowUp for 1 s moves `controls.target`. A plain drag changes the target. A Ctrl-drag changes the azimuth but not the target.
  - (d) Flying to "Summit" reaches `finest === 3` within 15 s.
  - (e) Toggling 2D sets `uFlat` to 1 within 2 s.
- [ ] Step 2: Run `npx playwright test`. Expected: PASS. Take screenshots of home, a station and the summit, and look at them.
- [ ] Step 3: Performance: in the dev page, log the average frame time over 5 s of orbiting (a scripted drag). Expected: under 16.7 ms on this machine. Record the number in the README.
- [ ] Step 4: Write the workflow. On push to main: checkout (with `lfs: false`), setup-node 22, `npm ci && npm run build` in `site/`, `cp -R mockup site/dist/mockup`, then `actions/upload-pages-artifact` (path `site/dist`) and `actions/deploy-pages`. Switch Pages to workflow builds: `gh api -X PUT repos/yaoderek/rainier-seismic-atlas/pages -f build_type=workflow`.
- [ ] Step 5: Update the README (what it is, the live link, how to build data and site, sources and licenses). Push. Wait for the deployment, then run the Playwright smoke test (a) and (b) against the live URL.
- [ ] Step 6: Commit: "Phase 1: e2e, Pages workflow, README".
