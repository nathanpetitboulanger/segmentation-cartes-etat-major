# segmentation-cartes-etat-major: rules for every agent

Deep-learning land-cover segmentation of the 19th-century État-major maps: IGN SCAN
État-major 40K scans in, BD CARTO EM land-cover classes out.

## Repo layout

Classical data-science layout. Put new files where they belong; don't invent new
top-level folders without asking.

| Path                                  | What goes there                                                                                                                     |
| ------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| `src/segmentation_cartes_etat_major/` | The importable package: data loading, label building, models, training, inference, metrics. All paths and constants in `config.py`. |
| `scripts/`                            | Thin command-line entry points that call the package. No logic of their own.                                                        |
| `tests/`                              | pytest, mirroring the package.                                                                                                      |
| `data/`                               | `raw/` (read-only inputs), `interim/`, `processed/`. Not committed.                                                                 |
| `models/`                             | Checkpoints and run outputs. Not committed.                                                                                         |
| `reports/`                            | Committed write-ups and their `figures/`.                                                                                           |
| `references/`                         | Documentation and papers.                                                                                                           |

- Read every path through `config.py`; never hard-code absolute paths.
- Never modify raw data. Everything derived must be rebuildable by a script.
- **Never commit** data, checkpoints, caches or run outputs. Only code, configs, small
  reports and figures.

## Tooling

-uv
