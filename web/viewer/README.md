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
