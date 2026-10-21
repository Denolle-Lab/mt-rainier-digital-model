# Running the pipeline on a remote Linux server

A full `pixi run pipeline` takes about six hours on a 10-core laptop (README, Run time and resources). On a Linux
server it runs unattended, with more workers. This page lists what the server needs, how to move the input
cache, and how to run and watch the families.

## 1. The server

| Need | Why |
|---|---|
| Linux x86-64 (`linux-64` is a pixi platform of this repository) | the environment is solved for it in `pixi.lock` |
| 16 cores or more | S6, S13, S14 and S37 run eikonal pools; set `RAINIER3D_WORKERS` to the core count |
| 32 GB RAM or more | S37 reached 19.6 GB summed over 8 workers |
| 20 GB of disk | `data/raw/` 5.8 GB, `data/processed/` 3.5 GB, `outputs/` 3.1 GB, plus the environment |
| outbound internet | GitHub (clone, push, releases), ComCat and GNSS archives, and the TeX packages that tectonic downloads the first time the paper is built |
| git, `gh` (logged in), tmux, a C compiler and CMake | version control, releases, a session that survives logout, and NonLinLoc |

## 2. One-time set-up on the server

```bash
curl -fsSL https://pixi.sh/install.sh | bash          # pixi; then open a new shell
git clone https://github.com/Denolle-Lab/mt-rainier-digital-model.git
cd mt-rainier-digital-model
git checkout <branch>                                  # the branch to rebuild
pixi install                                           # the default environment (and `pixi install -e paper`)
```

**NonLinLoc** (S26 only). The runs of October 2026 used NonLinLoc v7.1.05 (18 April 2025), the version its
own log lines print. Build that version and point `RAINIER3D_NLL_BIN` at the folder that holds `Grid2Time` and
`NLLoc`:

```bash
git clone https://github.com/alomax/NonLinLoc.git ~/src/NonLinLoc
cd ~/src/NonLinLoc/src && mkdir -p bin && cmake . && make     # as in NonLinLoc's README; binaries in bin/
export RAINIER3D_NLL_BIN=~/src/NonLinLoc/src/bin               # add to ~/.bashrc
```

After S26, the first line of each `outputs/catalog/nll/gt_*.log` names the version, e.g.
`Grid2Time (NonLinLoc v7.1.05 18Apr2025)`.

## 3. Copy the input cache

The pipeline reads only `data/raw/`, which holds every downloaded and every machine-local input. That includes
the CVM v1.7 domain cut (`regional/cvm17_domain.nc`) and the staged copies of CRESCENT Gen0 and the PNSN 1D
table (`regional/`). It is not in git. Copy it once from a machine that has it, then check it against the
committed manifest:

```bash
# on the machine with the cache (about 5.8 GB)
rsync -avP data/raw/ <user>@<server>:mt-rainier-digital-model/data/raw/   # over ssh
# on the server
pixi run manifest -- --check          # every file of docs/data_manifest.csv present and identical
```

**Integrity.**
- **The check:** `--check` recomputes the SHA-256 of every cached file and compares it with the committed
  manifest. It lists missing and different files, and exits with an error if there are any.
- **Repair:** if it reports a file, copy again with `rsync -avP --checksum` (which compares contents rather
  than sizes and dates), and check again. Start the run only once the check passes.
- **Why not download again:** copying keeps the exact bytes the published model was built from. A fresh
  download does not:
  - live services (ComCat, NHDPlus, 3DEP, the GNSS archives) can return different bytes after the data freeze;
  - some inputs cannot be downloaded by a script: CVM v1.7 sits behind a captcha, and the DAS table, the KMZ
    overlays and the Synoptic catalogue are local files (`configs/sources.yaml`).
  The stages do download what is missing and scriptable, so a server without a cache would rebuild most of
  it, but `--check` would then list the files that differ from the published inputs.

The model products in `data/processed/` and the outputs are rebuilt by the pipeline, so they do not need copying.
To skip families that have not changed, copy `data/processed/` and `outputs/` as well.

## 4. Run

Run in tmux, so the run survives a dropped connection:

```bash
tmux new -s rebuild
export RAINIER3D_WORKERS=$(nproc)                     # eikonal pools of S6, S13, S14, S37
LOG=outputs/logs/families_$(date +%Y%m%d_%H%M).log; mkdir -p outputs/logs
for t in inputs surface model calibrate validate tomography applications deliver; do
  echo "=== $(date '+%F %T') START $t" >> $LOG
  pixi run $t >> $LOG 2>&1 || { echo "=== $(date '+%F %T') FAILED $t" >> $LOG; break; }
  echo "=== $(date '+%F %T') DONE $t" >> $LOG
done
# detach with Ctrl-b d; reattach with: tmux attach -t rebuild; follow with: grep '^===' $LOG
```

- **Families:** the loop runs the same eight families as `pixi run pipeline`, but logs the start and end of
  each one, so a failure shows which family to rerun.
- **Partial runs:** after a change to the model, `model`, `calibrate`, `validate` and `tomography` are the
  families that matter for the published numbers.
- **Manual stages:** S20 (products release, `pixi run s20 --tag products-vX.Y.Z --upload`), S27 and S28 run by
  hand.

### What a clean machine needs that a laptop hid

The first server run (21 October 2026) started with an empty `data/processed/` and `outputs/`, and found stages
that read products no family had built yet. They are fixed in the families:

- **S22 and S3:** S22 read `geomodel.zarr`, which S3 builds from S22's own output; S22 now reads the S1 surface
  store (`surface.zarr`), which holds the same elevation, ice and map units.
- **S21 and the model table of the paper:** `validate` now builds the uncalibrated model (`pixi run nocal`:
  `model_nocal.zarr`, from S4 and S5 without the calibration, into their own stores) and relocates the PNSN 1D
  and uncalibrated models (`s14-1d`, `s14-nocal`), as well as the published one.
- **S8 in `applications`:** S18 and S10 read the event catalogue of S8 (`web/atlas/data/events.geojson`, frozen at
  `as_of`), which no family ran; S8 now opens `applications`.
- **S29 before S34:** S34 reads the storm that S29 writes (`data/processed/events/`).

Two inputs exist only on the machine where they were made, and the server run goes on without them:

- **Canopy layers of S19** (lidar canopy height and cover, Sentinel-2 LAI, GEDI PAI and biomass): read from
  `~/Downloads` (`configs/canopy_products.yaml`) and not staged into `data/raw/`. S19 keeps the GEDI canopy height
  only, and S10 keeps the committed canopy figure instead of remaking it.
- **The retired calibration snapshots** (`model_vscal_20260924.zarr`, `model_joint_s13.zarr`) and their S14 runs:
  the dated rows of the paper's model table. S10 leaves their curves out of the calibration figure and their rows
  out of `docs/joint_calibration/relocation_qc.csv`.

## 5. Claude Code on the server

Run Claude Code where the files are: either VS Code Remote-SSH with the Claude Code extension in the remote
window, or `claude` inside a tmux session on the server. The session then reads and edits the clone, runs the
families, and commits and pushes from the server. The laptop can sleep.

## 6. Results

- **Through git:** the committed results (figures under `docs/`, `configs/velocity_calibration.yaml`,
  `docs/data_manifest.csv`, the tomography report) come back through git.
- **Paper builds:** the paper HTML and PDF are left to the Linux CI build, so restore the server's local
  builds (`git checkout -- docs/paper/rainier3d_paper.html docs/paper/rainier3d_paper.pdf`) before committing.
- **Stores:** `data/processed/` and `outputs/` stay on the server. The derived products reach users through a
  products release (S20) built there.
