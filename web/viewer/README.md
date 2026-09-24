# Mount Rainier Seismic Atlas

Live: https://yaoderek.github.io/rainier-seismic-atlas/ · original mockup: [/mockup/](https://yaoderek.github.io/rainier-seismic-atlas/mockup/)

A 3D map of the active seismic stations on and around Mount Rainier, on USGS terrain with 1 m lidar at the summit
that loads as you zoom, with the earthquake catalog beneath the mountain as toggleable layers. Built from the Cascadia
Offshore Sensor Atlas's design system and navigation.

**Earthquakes** (phase 2): glow cloud (G), density shells (S) enclosing 70 / 45 / 20% of events, and dots (D) sized by
magnitude; a see-through slider and a cut (X) for the ground; the camera can go below the ground ("From below").
Nothing underground is ever drawn above the ground surface, so solid ground hides it completely.

**Navigation:** drag to move · Ctrl/⌘-drag or right-drag to rotate · scroll to zoom · arrow keys to glide ·
Go to places and major stations · click a station for its instruments and data links.

## Layout

```text
data/      Python build step: fetches public sources (cached in data/cache/) and writes site/public/atlas/
site/      React + Vite + Three.js site; site/public/atlas/ is the committed data bundle
mockup/    the approved single-file mockup
docs/      design spec and implementation plans
```

## Build

```sh
uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -r data/requirements.txt
cd data && ../.venv/bin/pytest -q
../.venv/bin/python -m rainier.build --out ../site/public/atlas --cache cache   # ~400 MB of downloads the first time
cd ../site && npm install && npm test && npm run dev    # http://127.0.0.1:5176/rainier-seismic-atlas/
npx playwright test                                      # end-to-end against a production build
```

Pushing to `main` builds the site and deploys it to GitHub Pages (`.github/workflows/pages.yml`).
The data bundle is committed because CI does not download from USGS; rebuild it rarely.

Measured on an Apple M5 Max (Chrome, ANGLE Metal): 16.7 ms mean frame time while orbiting (60 fps).

## Model surface layers (rainier3d)

The **Surface model** panel drapes one 2D layer of the
[rainier3d](https://github.com/Denolle-Lab/mt-rainier-virtual-3d-model) model on the terrain at a time:
- imagery: a Sentinel-2 true-colour median composite (August to September 2025);
- geology (model units) and the model's surface hydrothermal alteration;
- glacier ice thickness and NDSI (snow and ice);
- soil thickness;
- water-table depth, from Ma et al. 2026 and from Fan et al. 2017;
- canopy height, NDVI and land cover;
- Vs in the top 100 m of rock, from the S-calibrated model.

`W` toggles the NHDPlus HR stream network. Hovering the ground (or tapping it on a phone) reads the layer's value at that point.

**Phones.** Below 700 px wide the panels become bottom sheets, opened one at a time from a tab dock (Layers, Model, Legend,
Go to). Station details open as a sheet from the bottom.

The layers are the model's 100 m surface grid, reprojected onto the overview box in square-degree pixels, so the
same texture lookup (world x/z to lon/lat) serves the overview mesh and the 1 m summit tiles. The bundle lives in
`site/public/atlas/model/` and is written by the model repository, not by `data/`:

```sh
cd ../mt-rainier-virtual-3d-model && pixi run s11 -- --atlas ../rainier-seismic-atlas/site/public/atlas
```

The bundle is optional: without `model/layers.json` the site runs exactly as before. Imagery and colour-ramp
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
