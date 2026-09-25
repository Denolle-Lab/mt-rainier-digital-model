# canopy-storage_seismic: non-seismic_code (vendored)

- **Source:** https://github.com/koepflma/canopy-storage_seismic (Manuela Köpfli), folder `non-seismic_code/`.
- **Commit:** `0ea36d47df80759b82f413c0c696813f1a8093e1` (main, 2026-09-25, "update readme").
- **Licences:** code MIT (`LICENSE`, "Copyright (c) 2026 koepflma"). `LICENSE-DATA` (CC-BY 4.0) is copied
  with it; upstream applies it to `seismic_data/` only, which is not vendored.
- **Changes:** none. The files under `non-seismic_code/` are byte-identical to that commit. `environment.yml`
  is the upstream environment, kept for reference; this repository runs the code in the pixi environment
  `canopy` (`pixi.toml`).

## How this repository runs it

`scripts/26_canopy_pipeline.py` (S26, `pixi run -e canopy canopy`) copies `non-seismic_code/` to
`data/raw/canopy_storage/non-seismic_code/` and runs each script from its own folder, as upstream expects. The
scripts' relative paths (`../../output_non-seismic_code/...`) then resolve to
`data/raw/canopy_storage/output_non-seismic_code/`, inside the raw-data cache. The call order, services and
credentials are listed in `docs/canopy_pipeline.md`.

## Known differences from the delivered products

- `GEDI/02_grid_gedi_l2b_pai.py` writes `L2B_PAI_{max,count,ntracks}.tif`; the delivered `L2B_PAI_mean.tif`
  used by S19 is not produced by this commit.
- No script here produces the GEDI L4B biomass grids, the lidar canopy height and vegetation cover
  (`CHM/README.md` describes a manual QGIS workflow) or the soil-map image.
- The scripts use their own box, lon −122.5 to −120.5 and lat 46.0 to 48.0, which contains the model domain.
