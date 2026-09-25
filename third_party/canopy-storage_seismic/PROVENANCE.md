# canopy-storage_seismic: non-seismic_code (vendored)

- **Source:** https://github.com/koepflma/canopy-storage_seismic (Manuela Köpfli), folder `non-seismic_code/`.
- **Commit:** `292ebe48cd70e32a21ac09ff0b1505544ba5e67c` (main, 2026-09-25, "updated non-seismic code"); first
  vendored at `0ea36d4`, one commit earlier, which had no CHM scripts.
- **Licences:** code MIT (`LICENSE`, "Copyright (c) 2026 koepflma"). `LICENSE-DATA` (CC-BY 4.0) is copied
  with it; upstream applies it to `seismic_data/` only, which is not vendored.
- **Changes:** none. The files under `non-seismic_code/` are byte-identical to that commit; `SHA256SUMS` lists
  the checksum of every vendored file (`shasum -a 256 -c SHA256SUMS` in this folder), and
  `tests/test_canopy_pipeline.py` checks them. `environment.yml`
  is the upstream environment, kept for reference; this repository runs the code in the pixi environment
  `canopy` (`pixi.toml`).

## How this repository runs it

`scripts/28_canopy_pipeline.py` (S28, `pixi run -e canopy canopy`) copies `non-seismic_code/` to
`data/raw/canopy_storage/non-seismic_code/` and runs each script from its own folder, as upstream expects. The
scripts' relative paths (`../../output_non-seismic_code/...`) then resolve to
`data/raw/canopy_storage/output_non-seismic_code/`, inside the raw-data cache. The call order, services and
credentials are listed in `docs/canopy_pipeline.md`.

## Known differences from the delivered products

- `GEDI/02_grid_gedi_l2b_pai.py` writes `L2B_PAI_{max,count,ntracks}.tif`; the delivered `L2B_PAI_mean.tif`
  used by S19 is not produced by this commit.
- No script here produces the GEDI L4B biomass grids, the gridded lidar canopy height and vegetation cover, or
  the soil-map image. `CHM/01_download_lidar_tiles.py` and `CHM/02_process_chm.py` compute canopy height
  (mean DSM − DTM over about 10 m) only at the project's stations, from the WA DNR Lidar Portal's 2022–2023
  "Wali" DSM and DTM tiles; they read the project's station table, which is not vendored, so S28 does not run
  them. The 10 m grids S19 reads were made from the same tiles in QGIS (`CHM/README.md`).
- The scripts use their own box, lon −122.5 to −120.5 and lat 46.0 to 48.0, which contains the model domain.
