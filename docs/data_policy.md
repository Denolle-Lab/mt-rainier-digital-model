# Data policy: what is published, what users fetch themselves

rainier3d publishes three things:

1. **The pipeline.** All code and configuration are in this repository (BSD-3-Clause). The 3D viewer in `web/viewer/` is MIT.
2. **The derived, aggregated products.** These are published under CC-BY-4.0 and downloaded with `rainier3d fetch` / `rainier3d export` (Python API: `rainier3d.api`):
   - the fused Vp/Vs/density/Q model on its three levels;
   - the surface layers on the 100 m grid;
   - GNSS velocities and strain;
   - the edifice-load stress.

   Checksums and download URLs are in `src/rainier3d/products.json`.
3. **Recipes, not copies, for inputs we may not redistribute.** The pipeline fetches every input from its original archive. When an input needs an account or has a restrictive licence, users provide their own credentials and rebuild that layer locally.

The rule applied by `scripts/20_publish_products.py`: a variable whose provenance (`gaia:source_keys`) includes a source marked `redistribute_derived: false` in `configs/sources.yaml` is left out of the published archive. It is listed in the catalog's `excluded` field and in the archive's `excluded_variables` attribute.

## Inputs by tier

| Tier | Inputs | What is published | What a user needs to rebuild |
|---|---|---|---|
| Open, redistributable | USGS 3DEP, CVM v1.7, ComCat, NHDPlus (v2.1 and HR), NLCD 2021 (public domain); WA DNR GeMS geology; SOLUS100 and ETH canopy height (CC-BY-4.0); Copernicus Sentinel-2 (open, with attribution); PANGA and UNR GNSS (open, with acknowledgement) | derived layers and products | nothing |
| Open, login needed to download | GEDI L2B / L3 / L4B (NASA Earthdata login); Sentinel-2 LAI (Copernicus Data Space account) | derived layers (NASA and Copernicus data carry no redistribution restriction; cite them) | their own account, to rerun S19 from source |
| Restricted licence | Ma et al. 2026 water-table depth (CC-BY-NC-ND-4.0: no derivatives) | **not published** (`redistribute_derived: false`); the 3D viewer shows it as a visualisation only | nothing: the Zenodo record is open; `pixi run s2 -- --ma` rebuilds the layer |
| Licence not yet documented | canopy-storage lidar canopy height and vegetation cover (lidar source unknown); soil-map image (source and legend unknown) | **not published** until documented | the delivered files (ask the canopy-storage project) |
| Licence field not recorded in `configs/sources.yaml` | CRESCENT Gen0, IceBoost v2 / OGGM, RGI 6.0, GlaThiDa, Synoptic, Fan et al. 2017 ("free for research purposes") | published for now | – |

**To do before a public product release:** record the licence of every source in the last row. Synoptic, whose network terms vary by provider, and Fan et al. 2017 are the ones most likely to need `redistribute_derived: false`.

## Accounts a user may need

| Account | Needed only for |
|---|---|
| NASA Earthdata login (free) | rebuilding the GEDI layers (S19 inputs, via the canopy-storage scripts) |
| Copernicus Data Space account (free) | rebuilding the Sentinel-2 LAI mosaic |
| HydroGEN PIN (free) | the Ma et al. uncertainty (IQR) layer, which is not used yet |
| Manual ScienceBase download | CVM v1.7 L3 (below 10.8 km), which is not used yet |

Nobody needs an account to use the published products.

## Attribution

Cite the model as Denolle et al. (2026) (see `products.json`), plus the sources of the layers you use. `configs/sources.yaml` gives each one's DOI or URL. Also include:
- "Contains modified Copernicus Sentinel data 2023/2025" for Sentinel-2 layers;
- "GPS time series provided by the Pacific Northwest Geodetic Array, Central Washington University" for the GNSS products.
