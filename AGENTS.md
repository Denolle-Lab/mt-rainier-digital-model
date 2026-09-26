# AGENTS.md

Conventions for anyone (human or agent) changing this repo.

- **Environment:** `pixi run ...` only. Never create venvs. Add dependencies with `pixi add`.
- **One domain:** every grid comes from `rainier3d.config.domain.load_domain()`. Never hard-code
  bounds, spacing or the CRS (EPSG:32610 horizontal, NAVD88 elevation positive up).
- **Numbers need sources:** every parameter in `configs/` names a key from `configs/sources.yaml`.
  An unsourced value uses `m1_placeholder`, and replacing placeholders is tracked work.
- **Categorical rasters:** uint8, nearest-neighbour only. Map symbols reach model units only
  through `configs/units.yaml` rules; the generated `configs/crosswalk_geology.json` is committed
  for review.
- **Data stays out of git:** `data/` and `outputs/` are ignored. Raw downloads are cached under
  `data/raw/<source>/`. Commit code, configs and small tables.
- **Storage:** zarr v3, `consolidated=False`, xarray DataTree with one node per level
  (`rainier3d.io.store`).
- **Before a PR:** run `pixi run all` and `pixi run test`. Invariants in `tests/test_invariants.py`
  run against the built model. Report any that fail; do not loosen tolerances to make them pass.
- **Style:** ruff, line length 110. Match the comment density of the surrounding code.
- **3D viewer (`web/viewer/`, MIT, by Derek Yao):** React + three.js, tested with `npm test` (vitest) and
  `npx playwright test` in `web/viewer/site`. Its map data (`web/viewer/site/public/atlas/`) is never committed; it
  is built with `pixi run viewer-data` + `pixi run s11` and deployed from the release asset named in
  `web/viewer/DATA_RELEASE`. Keep the MIT `LICENSE` and `THIRD_PARTY_NOTICES.md` in that directory.
- **Vendored code (`third_party/`):** kept byte-identical to the upstream commit named in its `PROVENANCE.md`,
  with the upstream `LICENSE` files. Adapt it from the runner script (e.g. `scripts/28_canopy_pipeline.py`),
  not by editing the vendored files.
