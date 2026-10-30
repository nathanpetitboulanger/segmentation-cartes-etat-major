# segmentation-cartes-etat-major: rules for every agent

Deep-learning land-cover segmentation of the 19th-century État-major maps: IGN SCAN
État-major 40K scans in, BD CARTO EM land-cover classes out.

## Working with the user

- **"Could we…?" means answer first.** Say whether it's possible and give a short plan,
  then wait. Read-only checks are fine; don't launch GPU jobs, long runs or big
  refactors until the user says go.
- The machine is shared with the user's own jobs: 16 cores, 62 GB RAM, one 8 GB GPU.

## Repo layout

Classical data-science layout. Put new files where they belong; don't invent new
top-level folders without asking.

| Path | What goes there |
|---|---|
| `src/segmentation_cartes_etat_major/` | The importable package: data loading, label building, models, training, inference, metrics. All paths and constants in `config.py`. |
| `notebooks/` | Exploration only, named `NN-topic.ipynb`. Code that gets reused moves into the package. |
| `scripts/` | Thin command-line entry points that call the package. No logic of their own. |
| `tests/` | pytest, mirroring the package. |
| `data/` | `raw/` (read-only inputs), `interim/`, `processed/`. Not committed. |
| `models/` | Checkpoints and run outputs. Not committed. |
| `reports/` | Committed write-ups and their `figures/`. |
| `references/` | Documentation and papers. |

- Read every path through `config.py`; never hard-code absolute paths.
- Never modify raw data. Everything derived must be rebuildable by a script.
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

- Work tile by tile (e.g. 4096 px tiles with a halo). Never load a whole département as
  float arrays: one is tens of thousands of pixels on each side.
- At most one heavy CPU process per agent, and at most 6 worker processes.
- One GPU job at a time. Smoke-test every new script with a short run before a long one.

## Data

- **Scans:** SCAN État-major 40K, RGB GeoTIFF tiles, 4 m/px, Lambert-93 (EPSG:2154).
- **Labels:** BD CARTO État-major, **level-3 georeferencing only** (level 4 is warped
  toward modern maps and doesn't fit the scans). Main layer `ocs_ancien`, class code in
  `theme` (`EMx.y`). Only use pixels inside `chantier`: the tiles also cover unlabelled
  areas, sea and foreign land.
- **Coverage:** the 16 départements IGN digitized with every class:
  02 03 07 13 15 18 22 29 42 43 48 56 59 62 63 74.
- Level-3 labels fit the scans to within a few pixels: expect 1–3 px of boundary noise.
- Labels are inconsistent in places (e.g. some thin rivers are labelled as the meadow or
  field around them). Check the labels before blaming the model.

**Classes and split:** 8 classes taken from the first EM code: forest, cultures,
meadows, pâquis/landes, vineyards, built-up, water, other. Train on 15 départements;
val = one interior tile per training département; **test = the Cher (18)**. A 2 km guard
strip around val and test is excluded from training.

## Evaluation rules

- **Select on val, never on the test.** Report the test only for the run chosen on val.
- **Compare paired by seed** (`-s0` against the control's `-s0`). Seed noise is about
  ±0.02 F1; a win must hold at every seed.
- When the model correctly draws things the labels omit, score with a metric that
  ignores those zones, otherwise correct predictions count as errors.
- Score large regions tile by tile to stay under the RAM cap.
