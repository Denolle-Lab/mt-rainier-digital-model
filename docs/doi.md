# DOI strategy

rainier3d publishes two kinds of object: the code, which is the pipeline, the client and the 3D viewer, and the
derived data products. They change on different schedules and are cited for different reasons, so each gets its
own Zenodo record. Every record has a concept DOI that always resolves to the latest version, and one version
DOI per release. Papers cite the version DOI of exactly what they used.

| Record | Zenodo type | Licence | What a version contains | When a version is made |
|---|---|---|---|---|
| rainier3d software | software | BSD-3-Clause (code), MIT (`web/viewer/`) | source archive of a `vX.Y.Z` tag | a software release |
| rainier3d derived products | dataset | CC-BY 4.0 | the assets of a `products-vX.Y.Z` GitHub release, `SHA256SUMS`, `docs/products.md` | a products release |

**The data record depends on the software record.**
- Each data version records the software version that made it (`isCompiledBy`) and the DOIs of its inputs
  (`isDerivedFrom`, generated from `configs/sources.yaml`).
- After publication, the ESSD article is added as `isDescribedBy`.
- Each software version points to the data record with `isSupplementedBy`.

## What gets a DOI and what does not

| Object | DOI | Why |
|---|---|---|
| Fused model, grids, strain, edifice load, alteration, mass-movement catalogue | yes: data record, each products release | derived data that others reuse and cite |
| GNSS product | the dated snapshot inside each products release | the weekly refresh (`gnss-latest`) changes every Monday. Its bytes are reproducible from the manifest, but a DOI per week would dilute citation. |
| Pipeline, client, viewer code | yes: software record, each `vX.Y.Z` tag | citable code for the methods |
| Paper | assigned by ESSD | the ESSD Discussions preprint and the final article each get their own DOI |
| Viewer data bundles (`viewer-data-*`) | no | a rendering of the products, rebuilt by S11 from a data version |
| Restricted inputs (Ma et al. water table, canopy-storage lidar, soil-map image) | no | not redistributed (`docs/data_policy.md`) |

## Why deposit through the API, not the GitHub webhook

Zenodo's GitHub integration archives every published release of a repository. This repository also publishes:
- `products-*`, `viewer-data-*` and `hydrothermal-alteration-em-v1` releases;
- the weekly `gnss-latest` refresh.

Through the webhook, each of those would become a software version. The deposit is therefore done by
`scripts/27_zenodo_deposit.py` through the Zenodo REST API, only for:
- `vX.Y.Z` tags, into the software record;
- `products-vX.Y.Z` tags, into the data record.

It creates each new version from the previous one, so the concept DOI stays the same.

## Version numbers

- **Products.** Semantic: products-vMAJOR.MINOR.PATCH.
  - MAJOR: a change of grid or format;
  - MINOR: a new product, or a change in values (new calibration, new data);
  - PATCH: metadata only.
- **Software.** Its own `vX.Y.Z`. The data record names the software version that built it.
- **In the repository.** `src/rainier3d/products.json` carries the version DOI of each product once deposited,
  and `CITATION.cff` carries the concept DOIs.

## Steps (maintainer)

1. Create a Zenodo personal access token with the `deposit:write` and `deposit:actions` scopes. Keep it in the
   environment, never in the repository: `export ZENODO_TOKEN=...`. Test first on the Zenodo sandbox
   (sandbox.zenodo.org, a separate token), with `--sandbox`.
2. **Software, first version:**
   ```bash
   git tag v1.0.0 && git push origin v1.0.0
   pixi run python scripts/27_zenodo_deposit.py software --tag v1.0.0 --dry-run   # check the metadata
   pixi run python scripts/27_zenodo_deposit.py software --tag v1.0.0             # draft on Zenodo
   ```
3. **Data, first version:**
   ```bash
   pixi run python scripts/27_zenodo_deposit.py data --tag products-v1.0.0 --software-doi <version DOI of step 2>
   ```
4. Review each draft on zenodo.org and publish it there. The script leaves drafts unpublished, because a
   published DOI cannot be deleted.
5. Record the concept DOIs in `CITATION.cff` and the version DOIs in `products.json`. Then cite them in the
   paper's Code and data availability section.

Later versions repeat steps 2–5, with `--concept <record id>` so the new version joins the existing record.

## Before the first deposit

- **WGS landslide inventory.** It states no licence (`docs/data_policy.md`). Confirm with the Washington
  Geological Survey that derived polygons may be redistributed under CC-BY, or drop them from the
  `mass_movements` product.
- **ORCID iDs.** Add all six authors' ORCIDs to `CITATION.cff`; the deposit script reads authors from it.
- **Grant.** Give the Paros Geohazard Center gift as the funding reference (Zenodo `grants` does not list
  private gifts; state it in `notes`).
