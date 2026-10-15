# [S-RP] REPRODUCIBILITY & OPEN SCIENCE (iteration 1, ESSD, maximum stringency)

Manuscript: `docs/paper/rainier3d_paper.md` on `main` @ d61305c (1313 lines, 22 `[TODO` markers).
Mode: read-only. Nothing was rerun, rebuilt or downloaded. Each finding says how it was checked:
**[V-file]** read in the repository at d61305c, **[V-gh]** read from `gh release view` / `gh api` / `git` on
7 October 2026, **[V-api]** Zenodo public search API, **[P]** read only from the paper.

**Verdict.** As it stands, a stranger cannot get the model that the paper describes, and cannot cite it by a
persistent identifier. The rebuild route is largely documented and mostly runs on public archives, which is a real
strength. But the published products (`products-v1.0.0`, 25 Sept 2026) predate the model in the text by 121 commits.
At least ten inputs exist only on a project machine, not the four the abstract states, and no Zenodo record exists.
ESSD would return this at the data-availability check, before review.

```
Inventory: data statement [present] | data sets in Appendix A [37 rows, 19 with a DOI or a data/article DOI in
           configs/sources.yaml, 18 with none] | code cited [Y, GitHub URL only; DOI N] | driver [Y: bash block
           in Sect. "Rebuilding", incomplete] | env file [Y: pixi.toml + pixi.lock, osx-arm64 and linux-64]
           | external binaries [NonLinLoc, unpinned, outside pixi]
```

---

## PASS 1: Compliance checklist

| Item | Result | Location and evidence |
|---|---|---|
| S-RP.1 Data availability section | PASS | "Code and data availability", l.1239–1250 [V-file] |
| S-RP.2 Primary data with persistent DOI | **FAIL** | Derived products are GitHub release assets with no DOI [V-gh]. Zenodo search for "rainier3d" returns 0 records [V-api]. 18 of 37 Appendix A rows have no `doi`/`data_doi` in the registry [V-file]; 3 rows are TODO with no reference at all (PNSN 1D, DAS table, soil-map image) plus TNM imagery with no registry key |
| S-RP.3 DOIs well formed, in reference list | PARTIAL | Bibliography generated from `configs/sources.yaml` (`pixi run bib`) [V-file]. 3 DOIs recorded as "taken from memory" (`brocher_2005`, `glathida`, `rgi60`), TODO l.1250. IceBoost paper DOI "not verified" in registry l.247 [V-file]. All to be resolved by a human |
| S-RP.4 Code with persistent DOI | **FAIL** | Code cited as a bare GitHub URL (l.1241). No `v*` software tag exists (tags listed, none `v1.0.0`) [V-gh]. `CITATION.cff` says `version: "1.0.0"`, `date-released: "2026-09-25"` with no matching tag and no DOI [V-file]. `scripts/27_zenodo_deposit.py` exists but has not been run (`docs/doi.md` steps 2–5 open) [V-file] |
| S-RP.5 Versions pinned | PARTIAL | `pixi.lock` pins everything in the pixi environments [V-file]. The paper names no Python or library version (`pixi.toml`: Python >=3.12,<3.14). NonLinLoc (Grid2Time, NLLoc; GPL-3) is an external binary at `$RAINIER3D_NLL_BIN` or `~/.local/nonlinloc`, with no version or commit anywhere (`src/rainier3d/catalog/nll.py` l.3–4, 21) [V-file]. pykonal builds from sdist and crashed two S13 runs, so S13 was run outside `pixi run` (`docs/joint_calibration.md` l.296) [V-file] |
| S-RP.6 End-to-end driver | PARTIAL | Bash block l.164–178 [P]. It omits S13/S14 (deferred to `docs/joint_calibration.md`), S20, S21, S25, S26, S29, S30, S33–S35 [P]. `pixi.toml` has no task for S19, S20, S21, S26 [V-file]. `pixi run platform` is placed before S25/S26/S29/S30 have run, and the paper says a missing product stops it (l.182) |
| S-RP.7 Derived data archived separately from code | **FAIL** | Products live in releases of the code repository, not a data repository [V-gh]. The relocated catalogue and the storm summaries are pre-release / release assets without a version DOI [V-gh] |
| S-RP.8 FAIR | **FAIL** | F: no DOI. A: public, no login [V-gh]. I: zarr v3, CF netCDF, GeoPackage, CSV [P, V-gh asset names]. R: CC-BY 4.0 stated for `products-v1.0.0` (release body) [V-gh]; paper still has "[TODO: licence of these two releases]" (l.1241) although both release notes state CC BY 4.0 [V-gh] |
| S-RP.9 Restrictions stated and justified | PARTIAL | Ma 2026 (CC-BY-NC-ND), WA DNR lidar, soil-map image: stated and justified (l.188–191) [P]. The registry flags a **fourth** source, `soilgrids_bdticm`, `redistribute_derived: false` [V-file]; the paper says three (l.188) and its Appendix row is "[TODO: licence]". Licences "to verify" or absent for CRESCENT Gen0, RGI 6.0, IceBoost v2, GlaThiDa, Synoptic, EarthScope FDSN/GNSS, Z5, Ecology wells, WGS subsurface DB [V-file]. Restricted layers are rendered into public `viewer-data-*` and `storms-dec2025-v1` bundles (the storms release note says the Ma water table is "displayed ... not redistributed as data") [V-gh] |
| S-RP.10 Seeds / nondeterminism | PASS | No random draw in `src/` or the stage scripts; the only RNG is `scripts/bench_eikonal.py` with seed 0 [V-file]. Held-out split is deterministic: "events alternating in origin-time order" (`configs/velocity_calibration.yaml` l.133) [V-file]. Nondeterminism comes from live archives instead (see R9) |
| S-RP.11 Compute environment | PARTIAL | Platforms stated (l.111) [P], matching `pixi.toml` [V-file]. Runtime given only for S13 (26 min, 10-core laptop). No total runtime or disk (raw cache alone is 5.93 GB by `docs/data_manifest.csv` [V-file]; the paper says 5.16 GB). No NonLinLoc build instructions |

---

## PASS 2: Constructive reconstruction dry-run

Protocol a stranger would follow from the paper, with what each step lacks. "Input" = identity and public access;
"Param" = parameters; "Out" = expected output stated.

| # | Step (stage) | Input | Op | Param | Seq | Out | Gap |
|---|---|---|---|---|---|---|---|
| 0 | Environment: `pixi install` | ok | ok | partial | ok | – | NonLinLoc not in env or paper; pykonal sdist crash |
| 1 | Surface stack (S1): 3DEP via py3dep, GeMS, IceBoost, RGI, GlaThiDa | public, live | ok | ok | ok | ok | 3DEP and IceBoost have no version DOI; 3DEP is updated in place |
| 2 | Environmental layers (S2) | public, live; Ma optional | ok | ok | ok | ok | NDVI 0.46 not reproducible (TODO l.267) |
| 3 | Vegetation (S19 + S28) | **delivered files** in `~/Downloads` (`configs/canopy_products.yaml`) | ok | ok | no pixi task for S19 | ok | upstream `koepflma/canopy-storage_seismic` is **private** (`gh api` → `private: true`) [V-gh] |
| 4 | Alteration (S22) | public (USGS OFR 2000-27) | ok | thresholds placeholder | ok | ok | – |
| 5 | 3D geology (S3) | configs | ok | magma-body depth reference unverified (TODO l.557) | ok | ok | – |
| 6 | Rock physics + critical zone (S4) | configs | ok | 16 rows `m1_placeholder`, no per-unit range (TODO l.370); Q rule unsourced (TODO l.369) | ok | ok | provenance gap, values present |
| 7 | Fusion (S5) | **CVM v1.7 by hand** (captcha); **CRESCENT local copy** | ok | cutoffs placeholder | ok | ok | both have DOIs; manual step documented |
| 8 | Calibration (S13) | ComCat picks (revisable, cached, not deposited); events in `configs/validation_events.csv` [V-file] | ok | in `docs/joint_calibration.md` | outside bash block | committed `configs/velocity_calibration.yaml` | rebuilder can skip it by using the committed result |
| 9 | Validation vs 1D (S6, S14) | **PNSN 1D table from a local file of another repo, identity unknown** | ok | ok | ok | ok | reference model not citable |
| 10 | GNSS (S17, S18) | public; `as_of` 2026-09-01 [V-file] | ok | placeholders in `configs/gnss.yaml` | ok | partial | WRSZ 20 and edifice 106 nanostrain: "no script computes it" (TODO l.801–802); 1500 vs 2335 nanostrain (l.806) |
| 11 | Strain in volume (S25) | S18 output | ok | ok | **absent from bash block** | ok | – |
| 12 | Mass movements (S24) | public; ESEC v3 not scripted | ok | ok | ok | ok | trigger field absent (TODO l.1030) |
| 13 | Relocation (S26) | ComCat picks; NonLinLoc binary | ok | full control lines (l.1155–1159) | **no pixi task, not in bash block** | `outputs/catalog/summary.json` | NLLoc version absent; Podvin–Lecomte uncited (TODO l.1158) |
| 14 | Storm (S29), terrain (S30), wells (S31), CZ synthetics (S33–S35) | public | ok | ok | S29, S30, S33–S35 not in bash block | ok | – |
| 15 | Publish (S20) | built stores | ok | `configs/products.yaml` | **no pixi task** | REBUILD.md, inputs.csv | not present in the only products release |
| 16 | Platform (S32) | **DAS table, smart-sensing station folder, I-432 KMZ, soil-poster KMZ from `~/Downloads` / `~/GitHub`** (`configs/platform.yaml` l.12–23) | ok | `as_of` 2026-09-23 | needs S2–S30 first | SHA256SUMS in bundle | – |
| 17 | Deposit (S27) | – | ok | – | – | – | not run |

### REPRODUCTION-STOP blocks

```
REPRODUCTION-STOP [S-RP.R1] at step "Deposit (S27)"
  Missing: Input identity & access (persistent identifier for data and code)
  Manuscript says: "are to be deposited on Zenodo as two versioned records (docs/doi.md) [TODO: concept and
    version DOIs; no v1.0.0 software tag exists yet]" (l.1241)
  Evidence: no v* tag [V-gh]; Zenodo search "rainier3d" = 0 records [V-api]; CITATION.cff has no DOI [V-file]
  Consequence: ESSD requires the data DOI, accessible to reviewers, at submission. P1 stops here. A GitHub
    release can be deleted or retagged, so the paper cannot pin what it describes.
  Severity: BLOCKING
```

```
REPRODUCTION-STOP [S-RP.R2] at step "Publish (S20)"
  Missing: Expected output (the deposited product is not the product described)
  Manuscript says: Table tbl:products caption "[TODO: sizes and contents of products-v1.1.0, the first release
    under this rule]" (l.1092); "Each release also carries REBUILD.md ... and inputs.csv" (l.1094)
  Evidence [V-gh, V-file]:
    - only products release is products-v1.0.0, created 2026-09-25, tag commit b98d61f; 121 commits to d61305c;
      no products-v1.1.0 exists
    - its 8 assets are 7 archives + SHA256SUMS; no REBUILD.md, no inputs.csv
    - since b98d61f, S4, S5, S13, src/rainier3d/properties/assign.py, geomodel/rules.py, fusion/build.py
      changed, and the critical zone (PR #40) and the Vp/Vs bound (PR #42) were merged: the critical-zone
      section (l.445–517) describes a model not in any release
    - products.json at HEAD: model `excluded` = [surface/water_table_depth] only, whereas the text says all
      resampled third-party fields are left out; mass_movements description includes faults and 1998 lahar
      zones, which the text says are left out
  Consequence: a reader who downloads the cited product cannot reproduce the paper's numbers (e.g. 11,738
    cells below Vp/Vs = sqrt(8/3), held-out RMS) and cannot tell which commit made what they hold. P1 stops.
  Severity: BLOCKING
```

```
REPRODUCTION-STOP [S-RP.R3] at step "Calibration (S13) / Relocation (S26)"
  Missing: Expected output (headline numbers disagree across paper, doc and release)
  Evidence:
    | Quantity | Abstract | Intro l.53 / Validation l.707 | CZ para l.502 | Conclusions l.1235 | docs/joint_calibration.md | relocated-catalog release |
    |---|---|---|---|---|---|---|
    | Held-out S RMS after (s) | 0.187 | 0.186 | 0.1866 | – | 0.188 | – |
    | Held-out P RMS before/after (s) | 0.120/0.092 | 0.120/0.092 | 0.0921 | – | 0.121/0.093 | – |
    | Median RMS rainier3d, grades A+B (s) | 0.107 | tbl l.1170: 0.107 | – | 0.109 | – | 0.109 |
    | Located of 370, rainier3d | – | tbl: 354 | – | – | – | 353 |
    | Above the ground, rainier3d | 1 (12 m) | tbl: 1 | – | "no event" | – | 0 |
    | Events stopped at base of volume | – | 10 (l.1163) | – | – | – | – | (Limitations l.1219: 12)
  Consequence: the published catalogue (relocated-catalog-2023-2025-v1, built on branch relocated-catalog-3d)
    is from an earlier model than the paper's numbers; a reproducer cannot know which run is authoritative.
  Severity: BLOCKING (abstract-level results)
```

```
REPRODUCTION-STOP [S-RP.R4] at steps "Vegetation", "Validation vs 1D", "Platform"
  Missing: Input identity & access
  Manuscript says: "four are read from local or delivered copies" (abstract l.25; l.152; conclusions l.1237),
    and separately "the four inputs that exist only on a project machine" (l.182)
  Evidence: machine-local inputs named in configs [V-file]:
    | Input | Where read from | Public route | Persistent ID |
    |---|---|---|---|
    | CVM v1.7 L01, L2 | ~/GitHub/gwl-space-time-smooth/data/raw | ScienceBase, manual (captcha) | yes |
    | CRESCENT Gen0 | ~/GitHub/cascadia_obs_ensemble/... | figshare | yes |
    | PNSN 1D table vel_pnsn_wa.csv | ~/GitHub/cascadia_obs_ensemble/data | none; identity unknown | no |
    | Canopy lidar CHM, cover (2) | ~/Downloads/... | none (QGIS, private repo) | no |
    | GEDI L2B PAI mean, L4B MU, L4B SE, S2 LAI (delivered) | ~/Downloads/... | only partly via S28 | product DOIs only |
    | Soil-map image masked_soil.tif | ~/Downloads | none; source undocumented | no |
    | DAS channel table | ~/Downloads | none | no |
    | Synoptic/SNOTEL station folder | ~/GitHub/mt-rainier-smart-sensing | gaia-hazlab/catalog is public [V-gh] | no |
    | USGS I-432 KMZ | ~/Downloads | NGMDB product 1268 | via PP 444 |
    | NRCS soil poster KMZ ("modified") | ~/Downloads | none for the modified file | no |
    | Summit 4392 m (l.77) | smart-sensing DEM mosaic (registry key rainier_dem_smart_sensing) | none | no |
  Consequence: the count is at least ten distinct sources, not four. The validation baseline (0.131 / 0.263 s
    in "the PNSN 1D model", abstract) rests on a table nobody outside the group can obtain or name.
  Severity: BLOCKING for the PNSN 1D row (headline comparison); PARTIAL for the display-only rows
```

```
REPRODUCTION-STOP [S-RP.R5] at step "GNSS (S18)"
  Missing: Operation (no script produces the reported numbers)
  Manuscript says: "| WRSZ | 20 [TODO: not reproduced; 23 from outputs/gnss/strain_wrsz.csv, no script
    computes it]" (l.801); same for Edifice 106 vs 133 (l.802); 1500 vs 2335 nanostrain (l.806)
  Consequence: contradicts "All numbers are produced by the scripts named in the text" (l.1250). P3 cannot
    reproduce the swarm-period strain scatter.
  Severity: BLOCKING for that table (a reported result with no generating code)
```

```
REPRODUCTION-STOP [S-RP.R6] at step "Relocation (S26)"
  Missing: Parameters of the environment (NonLinLoc version) and Sequence (no task, not in the bash block)
  Manuscript says: Grid2Time and NLLoc control lines in full (l.1155–1159), no version; bash block l.164–178
    has no s26
  Evidence: src/rainier3d/catalog/nll.py reads binaries from RAINIER3D_NLL_BIN or ~/.local/nonlinloc; no
    `s26` task in pixi.toml [V-file]
  Consequence: the relocated 2023–2025 catalogue (an abstract result) cannot be regenerated without guessing a
    NonLinLoc build. The settings themselves are well specified.
  Severity: BLOCKING (abstract result; becomes PARTIAL once the version and install line are given)
```

```
REPRODUCTION-STOP [S-RP.R7] at step "Rebuild sequence"
  Missing: Sequence
  Manuscript says: the bash block "download[s] every input, rebuild[s] the model and check[s] the result"
  Evidence: S13/S14, S20, S21, S25, S26, S29, S30, S33–S35 absent; no pixi task for S19, S20, S21, S26;
    `pixi run platform` comes before the stores it requires. S13 had to run outside `pixi run`
    (docs/joint_calibration.md l.296). Workflow is called "S0 to S30" (l.91) but the text uses S31–S35 and
    the repo has S36
  Severity: PARTIAL (all of it is deferred to code that exists)
```

```
REPRODUCTION-STOP [S-RP.R8] at step "Rock physics (S4)" and others
  Missing: Parameters' provenance (values exist, sources do not)
  Manuscript says: 16 unit rows m1_placeholder "chosen within published ranges" with the range TODO (l.370);
    Q rule TODO (l.369); magma-body depth reference TODO (l.557); fusion cutoffs placeholder (l.52)
  Consequence: reproducible from configs, not traceable to literature. Limitations l.1205 is candid about it.
  Severity: PARTIAL
```

```
REPRODUCTION-STOP [S-RP.R9] at step "Inputs, all live archives"
  Missing: Input identity (byte-level)
  Manuscript says: "ComCat can revise picks, and the USGS can re-stage NHDPlus. The check lists those files"
    (l.110)
  Consequence: `pixi run manifest -- --check` detects drift but cannot restore the inputs; the raw cache is not
    deposited. ComCat picks feed the calibration and the relocation; 3DEP and Sentinel-2 are reprocessed in place.
  Severity: PARTIAL
```

```
REPRODUCTION-STOP [S-RP.R10] at step "Redistribution and licences"
  Missing: Input access terms
  Evidence: four sources flagged redistribute_derived false (adds soilgrids_bdticm); paper says three
    (l.188). Release licences already stated (CC BY 4.0) in relocated-catalog and storms release notes, so the
    TODO at l.1241 is stale. Viewer bundles in public releases contain renderings of the Ma (NC-ND), DNR lidar
    and soil-map layers.
  Severity: PARTIAL (P6: "can I redistribute this?" has no single answer)
```

```
REPRODUCTION-STOP [S-RP.R11] at step "Data compilation section, stated counts"
  Missing: Expected output (counts out of date)
  | Statement | Paper | Repo at d61305c [V-file] |
  |---|---|---|
  | Registry entries | 99 (l.108) | 133 |
  | Manifest files | 2,768 (l.110) | 2,772 |
  | Manifest size | 5.16 GB | 5.93 GB |
  | Sources flagged no-redistribution | 3 | 4 |
  | mass_movements archive | 1 MB | 1.83 MB (1,828,031 bytes) [V-gh] |
  Severity: COSMETIC each, but P1 checks exactly these
```

```
REPRODUCTION-STOP [S-RP.R12] at step "AI-assisted code record"
  Missing: Input access (session transcripts)
  Manuscript says: "[TODO: ... state here whether and where they are deposited]" (l.221);
    scripts/redact_transcripts.py exists [V-file]
  Severity: PARTIAL (not on the data path; ESSD editors may ask)
```

```
REPRODUCTION VERDICT: NOT RECONSTRUCTABLE: 6 blocking stops (R1, R2, R3, R4, R5, R6)
```

What does work, and should be kept: the registry with a key per number, the checksummed cache manifest, the
deterministic platform rebuild with a data freeze, the committed calibration result and event list, the full
NonLinLoc control lines, and the Redistribution section. The gap is between this machinery and what is
published.

---

## Tier feed to Criterion 3

**Poor.** Not Fatal: the code is public and most of the chain rebuilds from public archives, so the central
product can in principle be regenerated. It is Poor because the cited deposit does not hold the model described,
the headline numbers disagree with the released catalogue, the validation baseline is an unidentified local file,
and there is no DOI. Submitted to ESSD without R1 and R2 fixed, this becomes a desk return regardless of tier.

Excellent would need all of Pass 1 to pass and every stop removed.

---

## Ordered fixes

1. **Cut one consistent release and deposit it (R1, R2, R7).** At one commit: run the whole chain, cut
   `products-v1.1.0` with S20 (REBUILD.md, inputs.csv included), tag `v1.0.0`, run `scripts/27_zenodo_deposit.py`
   for software and data, publish both drafts, then write the version DOIs into l.1241, `CITATION.cff` and
   `src/rainier3d/products.json`. Fill Table tbl:products from that release. Put the relocated catalogue and the
   storm summaries into the same data record (or their own versioned records) so they get DOIs too.
2. **Regenerate every headline number from that commit (R3, R5, R11).** One run of S13, S14, S26, S18; then
   update abstract, introduction, Sect. Validation, Table tbl:relocation, Conclusions and Limitations (10 vs 12
   events at the base) from the output files. Either add the script that gives the WRSZ and edifice strain
   scatter or drop those cells. Refresh the registry and manifest counts.
3. **Close the local-input gap (R4, R9, R10).** Replace "four" with a table of every machine-local input and its
   public route. Identify and cite the PNSN 1D model (PNSN network DOI 10.7914/SN/UW for ComCat as well), or
   deposit the table with permission. Deposit the redistributable part of `data/raw/` that drives the headline
   results (ComCat picks and QuakeML for the 88 calibration and 371 catalogue events, NLLoc observation files),
   since ComCat can revise them. For the canopy layers: make the upstream repository public at the vendored
   commit, or deposit the delivered files with their licence, or state that they are display-only and
   unreproducible.
4. **Pin the toolchain and finish the driver (R6, R7, S-RP.5).** Give the NonLinLoc commit and build line; add
   pixi tasks for S19, S20, S21, S26; extend the bash block to every stage the products need, in a runnable order,
   with total runtime and disk. Resolve the pykonal build (conda-forge or a wheel) so S13 runs under `pixi run`.

Then clear the remaining 22 TODOs; the licence ones (l.1241, 1271, 1275) are partly answered already in the
release notes and the registry.

---

## Persona lines (P1, P6)

- **P1 (ESSD data reviewer):** stops at l.1241. No DOI, and the only products release predates the text. Single
  change: fix 1.
- **P6 (hazard analyst / research software engineer):** the download and client sections are clear and usable
  today. But the rebuild block is incomplete, NonLinLoc is unpinned, and the redistribution status of four layers
  is split across paper, registry and release notes. Single change: fix 4, plus one licence table per product.

---

## Human-verify

- Every DOI in Appendix A, especially `brocher_2005`, `glathida`, `rgi60` (from memory) and the IceBoost paper.
- Whether NLCD 2021 (USGS ScienceBase), NHDPlus HR and the PNSN network (10.7914/SN/UW) have DOIs to cite in
  place of service URLs. I believe NLCD 2021 and the UW network DOI exist; not resolved here.
- Contents of `products-v1.0.0/rainier3d_model.zarr.zip`: which variables it holds (resampled third-party
  fields? critical zone? vegetation from delivered files?). Not downloaded.
- Whether the `viewer-data-*` bundles contain the Ma, lidar and soil-map renderings as files, and whether that
  is acceptable under CC-BY-NC-ND and the DNR terms.
- SoilGrids250m 2017 licence (registry says "to verify") and why it is flagged no-redistribution but not named in
  the paper.
- `docs/joint_calibration.md` stopping criterion for the Gauss–Newton iterations (not checked).
