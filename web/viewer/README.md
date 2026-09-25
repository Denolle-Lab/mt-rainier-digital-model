# Mount Rainier Seismic Atlas: 3D viewer

Live: https://denolle-lab.github.io/mt-rainier-digital-model/ (deployed from this repository)

Written by Derek Yao in [yaoderek/rainier-seismic-atlas](https://github.com/yaoderek/rainier-seismic-atlas) and merged
here on 24 September 2026. His commit history is kept. The MIT licence in `LICENSE` and the notices in
`THIRD_PARTY_NOTICES.md` cover this directory; the rest of the repository is BSD-3-Clause. The approved single-file
mockup stays in the original repository.

A 3D map of the active seismic stations on and around Mount Rainier, on USGS terrain with 1 m lidar at the summit
that loads as you zoom, with the earthquake catalog beneath the mountain as toggleable layers. Built from the Cascadia
Offshore Sensor Atlas's design system and navigation.

**Earthquakes** (phase 2): glow cloud (G), density shells (S) enclosing 70 / 45 / 20% of events, and dots (D) sized by
magnitude; a see-through slider and a cut (X) for the ground; the camera can go below the ground ("From below").
Nothing underground is ever drawn above the ground surface, so solid ground hides it completely.

**Navigation:** drag to move · Ctrl/⌘-drag or right-drag to rotate · scroll to zoom · arrow keys to glide ·
Go to places and major stations · click a station for its instruments and data links.

**Layout:** the map comes first. The title bar (with search) and Go to stay on screen; everything else opens from the
dock of icon buttons at the top right: **Layers** (view, style, earthquake layers, ground), **Surface model**, **Legend**
(the sensor filter, earthquakes, mass movements) and **Help**. A panel stays open until its button is clicked again,
open panels stack, and closing one keeps its settings. On a phone the same panels are bottom sheets.

## Layout

```text
data/      Python build step: fetches public sources (cached in ../../data/raw/viewer_cache/) and writes site/public/atlas/
site/      React + Vite + Three.js site; site/public/atlas/ is the data bundle (not in git)
docs/      design spec and implementation plans (from the original repository)
```

## Build

From the repository root:

```sh
pixi run viewer-data-test   # tests of the data build
pixi run viewer-data        # terrain, imagery, stations, quakes -> web/viewer/site/public/atlas (~400 MB of downloads the first time)
pixi run s11                # rainier3d model layers -> web/viewer/site/public/atlas/model
cd web/viewer/site && npm ci && npm test && npm run dev   # http://127.0.0.1:5176/mt-rainier-digital-model/
npx playwright test                                         # end-to-end against a production build
```

The data bundle is not committed. `pixi run viewer-bundle` packs it into `outputs/viewer-atlas-bundle.tar.gz`, which is
uploaded as a release asset under the tag in `DATA_RELEASE`. Pushing to `main` (changes under `web/viewer/`) builds the
site with that bundle and deploys it to GitHub Pages (`.github/workflows/viewer-pages.yml` at the repository root). To
publish new data, make a new release and update `DATA_RELEASE`.

Measured on an Apple M5 Max (Chrome, ANGLE Metal): 16.7 ms mean frame time while orbiting (60 fps).

## Model surface layers (rainier3d)

The **Surface model** panel drapes one 2D layer of the
[rainier3d](https://github.com/Denolle-Lab/mt-rainier-digital-model) model on the terrain at a time:
- imagery: a Sentinel-2 true-colour median composite (August to September 2025);
- geology (model units) and the model's surface hydrothermal alteration;
- glacier ice thickness and NDSI (snow and ice);
- soil thickness;
- water-table depth, from Ma et al. 2026 and from Fan et al. 2017;
- canopy height, NDVI and land cover;
- Vs in the top 100 m of rock, from the S-calibrated model.

`W` toggles the NHDPlus HR stream network. Hovering the ground (or tapping it on a phone) reads the layer's value at that point.

**Below ground.** The same panel shows the fused velocity model (Vs, Vp, Vp/Vs, density, model units):
- on a vertical **section along the terrain cut**, which switches the cut on and has its own direction and position sliders;
- on a horizontal **depth slice** at a chosen elevation.

Both sample one 3D texture per property (`model/volume/*.u8`, 500 m × 250 m cells). A quadratic fit maps scene
coordinates to the UTM grid to within 0.001 cells, and anything above the ground is hidden.

**Navigation help.** A "How to move" card opens on the first visit, and again from **?**. It gives mouse, trackpad
and touch gestures. The pad at the bottom rotates, tilts, zooms and turns north up without any gesture.

**Phones.** Below 700 px wide the panels become bottom sheets, opened one at a time from a tab dock (Layers, Model, Legend,
Go to). Station details open as a sheet from the bottom.

The layers are the model's 100 m surface grid, reprojected onto the overview box in square-degree pixels, so the
same texture lookup (world x/z to lon/lat) serves the overview mesh and the 1 m summit tiles. The bundle lives in
`site/public/atlas/model/` and is written by the model repository, not by `data/`:

```sh
pixi run s11   # from the repository root; writes web/viewer/site/public/atlas/model
```

The model layers are optional: without `model/layers.json` the viewer shows the terrain, stations and quakes only. Imagery and colour-ramp
layers are WebP (lossy, with alpha) and categorical layers are PNG. The bundle is about 22 MB, and each layer
loads only when it is picked.

## Data

| Layer | Source | License |
|---|---|---|
| Terrain, 60 × 60 km | USGS 3DEP elevation, 1800 × 1215 samples (≈35–50 m) | public domain |
| Summit, 8.4 × 8.2 km | USGS 3DEP 1 m lidar in 8 / 4 / 2 / 1 m tiles | public domain |
| Imagery | USGS The National Map, USGSImageryOnly | public domain |
| Stations | EarthScope FDSN station service, active channels as of the build date | open |
| Earthquakes | USGS ComCat (PNSN), 1980 onward, depth in km below sea level | public domain |

Stations are "active" when their channels have no end date in the metadata; that is not a live health check.
Both ArcGIS export services silently widen a request whose pixels are not square in degrees, so every request
here uses square-degree pixels (`data/rainier/extent.py`).

## License

Code: MIT, see `LICENSE`. Data and third-party components keep their own terms, see `THIRD_PARTY_NOTICES.md`.
