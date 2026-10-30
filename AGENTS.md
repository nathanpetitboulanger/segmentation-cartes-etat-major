# segmentation-cartes-etat-major: rules for every agent

Deep-learning land-cover segmentation of the 19th-century État-major maps: IGN SCAN
État-major 40K scans in, BD CARTO EM land-cover classes out. This repo is the clean,
reusable pipeline. The exploratory work it builds on (campaigns, ablations, label
studies) is in `../baselines/`; read `../baselines/AGENTS.md` before changing the data,
the labels or the training recipe.

## Working with the user

- **"Could we…?" means answer first.** Say whether it's possible and give a short plan,
  then wait. Read-only checks are fine; don't launch GPU jobs, long runs or big
  refactors until the user says go.
- The machine is shared with the user's own jobs: 16 cores, 62 GB RAM, one RTX 3070
  Laptop (8 GB).

## Repo layout

Classical data-science layout. Put new files where they belong; don't invent new
top-level folders without asking.

| Path | What goes there |
|---|---|
| `src/segmentation_cartes_etat_major/` | The importable package: data loading, label building, models, training, inference, metrics. All paths and constants in `config.py`. |
| `notebooks/` | Exploration only, named `NN-topic.ipynb`. Code that gets reused moves into the package. |
| `scripts/` | Thin command-line entry points that call the package. No logic of their own. |
| `tests/` | pytest, mirroring the package. |
| `data/` | Derived data (`interim/`, `processed/`). Not committed. |
| `models/` | Checkpoints and run outputs. Not committed. |
| `reports/` | Committed write-ups and their `figures/`. |
| `references/` | Documentation and papers. |

- **Raw inputs stay in `../data/`** (see Data below, 26 GB of scans). Read them in place
  through `config.py`; never copy or modify them, never hard-code absolute paths.
- **Never commit** data, checkpoints, caches or run outputs. Only code, configs, small
  reports and figures.

## Tooling

- Python 3.12 with **uv**: `uv add <pkg>` for dependencies, `uv run python ...` to run,
  `uv run pytest` for tests, `uvx ruff check` / `uvx ruff format` before committing.
- The shell is **zsh**: an unquoted `$VAR` holding a command is not split into words, and
  a bare `===` is an error. `ls` is an eza alias that can fail: use `/usr/bin/ls`.

## Compute rules

- **CPU / RAM (user rule):** every CPU script runs under a hard 4 GB cap, including quick
  previews:

      systemd-run --user --scope -q -p MemoryMax=4G -p MemorySwapMax=0 uv run python ...

  Work tile by tile (e.g. 4096 px tiles with a halo); never load a whole region as float
  arrays (the Cher alone is 33792 × 25088 px). At most one heavy CPU process per agent
  and 6 worker processes.
- **GPU:** never run CUDA outside the shared dispatcher in `../baselines/hypotheses/`. It
  runs one job at a time and starts every job in `baselines/`, so point uv back here:

      ../baselines/hypotheses/gpu_submit.sh <tag> uv run --directory ../segmentation-cartes-etat-major python -m ...
      python3 ../baselines/hypotheses/gpu_dispatcher.py status

  Wait for `END     <tag> ` in `../baselines/hypotheses/gpu_queue.log`; logs are in
  `../baselines/outputs/segformer/hyp/logs/<tag>.log`. Tags are lowercase and unique.
  Smoke-test every new script first (`<tag>-smoke`). Rules on priorities, time limits and
  restarts are in `../baselines/AGENTS.md`.

## Data

**Decision (2026-10-24):** train only on IGN **level-3** BD CARTO EM labels + SCAN
État-major 40K scans, in the 16 départements IGN digitized with every class:
02 03 07 13 15 18 22 29 42 43 48 56 59 62 63 74. No level-4, partner (`PN*`) or old
Dynafor workshop data unless asked. Details: `../data/README.md`.

- Scans: `../data/scan_em40k/` (378 COG tiles, 4 m/px, Lambert-93, EPSG:2154), mosaic
  `../data/scan_em40k.vrt`.
- Labels: `../data/bdcarto_em_n3.gpkg`, layer `ocs_ancien`, class in `theme` (IGN codes
  `EMx.y`). Only use pixels inside `chantier`: the tiles also cover unlabelled
  départements, sea and foreign land.
- Level-3 labels fit the scans to 0–14 m (median 4 m): expect 1–3 px of boundary noise.
- Known label quirks (thin rivers drawn as meadow/field, `cours_d_eau` flags coded 0/1 or
  f/t, built-up conventions varying by département) are listed in `../baselines/AGENTS.md`.

**Classes and split (from `../baselines/em40k/`):** 8 classes taken from the first EM
code: forest, cultures, meadows, pâquis/landes, vineyards, built-up
(`zone_urbaine` ∪ `batiment`), water, other. Train on 15 départements; val = one interior
tile per training département; **test = the Cher (18)**. A 2 km guard strip around val
and test is excluded from training.

## Evaluation rules

- **Select on val, never on the test.** Report the Cher only for the run chosen on val.
- **Compare paired by seed** (`-s0` against the control's `-s0`). Seed noise is about
  ±0.02 F1; a win must hold at every seed.
- When the model correctly draws things the labels omit (e.g. double-line rivers), score
  with a metric that ignores those zones (`macro_f1_x`, `thin_river_f1`, see
  `../baselines/rivers/scores.py`).
- Score large regions tile by tile to stay under the RAM cap.

## Starting point

Best model so far (2026-10-30, `../baselines/outputs/em40k/FINAL16K_SUMMARY.md`):
DINOv3 ViT-B fine-tuned 16k iterations, plus a small full-resolution detail branch and
`double = t` river lines burned as water (radius 2 px) in the training targets. Cher
macro F1 ≈ 0.84, thin_river_f1 0.906. Label fixes gave bigger gains than architecture
changes; image-only post-processing never helped.
