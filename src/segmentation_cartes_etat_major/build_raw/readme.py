"""data/raw/ign_sources.tsv (where the IGN data came from) and data/raw/README.md."""

from pathlib import Path

import pyogrio

from segmentation_cartes_etat_major import config


def write(source: Path) -> None:
    _write_sources(source)
    _write_readme()


def _write_sources(source: Path) -> None:
    with open(config.IGN_SOURCES, "w") as f:
        f.write("product\turl\tbytes\tmd5\n")
        f.write((source / "raw" / "manifest.tsv").read_text())


def _write_readme() -> None:
    sizes = {
        p: sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) / 1e9
        for p in (config.SCANS, config.LABELS)
    }
    n_tiles = len(list(config.SCANS.glob("SCEM40K_*.tif")))
    layers = "\n".join(
        f"| `{layer}` | {info['geometry_type']} | {info['features']:,} |"
        for layer in config.LABEL_LAYERS
        for info in [pyogrio.read_info(config.LABELS / f"{layer}.parquet")]
    )
    (config.RAW / "README.md").write_text(
        README.format(
            n_tiles=n_tiles,
            scans_gb=sizes[config.SCANS],
            labels_gb=sizes[config.LABELS],
            layers=layers,
            deps=" ".join(config.DEPARTEMENTS),
        )
    )


README = """\
# Raw data: IGN État-major scans and labels

Read-only inputs, built by `uv run scripts/build_raw.py <source>` (see
`src/segmentation_cartes_etat_major/build_raw/`). Never edit these files; derive into `data/interim/`
or `data/processed/`. All paths are in `config.py`.

Sources: IGN SCAN État-major® 40K and BD CARTO® État-major, Licence Ouverte 2.0
(`ign_sources.tsv` lists the IGN URLs, sizes and MD5s). Départements: {deps}.
CRS everywhere: Lambert-93 (EPSG:2154).

## Contents

| Path | Content |
|---|---|
| `scan_em40k/SCEM40K_XXXX_YYYY_L93_E100.tif` | **{n_tiles}** scan tiles ({scans_gb:.1f} GB): 20 km x 20 km, 5000 x 5000 px, **4 m/px**, RGB uint8. Cloud-Optimized GeoTIFF, **lossless** WebP, 512 px blocks, overviews. `XXXX_YYYY` is the top-left corner in km. |
| `scan_em40k.vrt` | Mosaic of all the tiles. |
| `scan_em40k_tiles.parquet` | Tile footprints; `deps` lists the départements each tile touches. |
| `bdcarto_em/<layer>.parquet` | BD CARTO® État-major, **level-3 georeferencing**, 16 départements merged ({labels_gb:.1f} GB). GeoParquet 1.1, ZSTD, rows in Hilbert order with a `bbox` column. `dep` gives the département. |
| `ign_sources.tsv` | Where everything was downloaded from. |

| Layer | Geometry | Features |
|---|---|---|
{layers}

- `ocs_ancien` is the main land-cover layer; `theme` holds the État-major class code (e.g.
  `EM4.1`). A combined code such as `EM7.1EM6.2` is a mixed class. Official definitions:
  IGN `DC_DL_BDCARTO-EM_1-0.pdf`.
- `chantier` is the outline of each département: the area where labels exist.
- `feuille` holds the map sheets (`nomfcourt`, survey year in `millesime`), handy for
  train/test splits by sheet.

## Why level 3

BD CARTO EM ships two georeferencings. Level 3 ("Lambert 93 Géoportail") is the one IGN
digitized in and it fits the scans: median offset 4 m (1 px), 90 % of windows within about
3 px. Level 4 ("Lambert 93 amélioré") is warped toward modern maps and sits 20-100 m off the
scans, so it is not included. Expect 1-3 px of boundary noise in the labels.

## Caveats

- Scan tiles at the edge of the map are filled with the colour (217, 198, 169) over sea and
  foreign land, and they also cover parts of départements outside the 16, which have no
  labels. Only use pixels inside `chantier`.
- The level-4-only partner data (Pyrenees and other parks) is not included.

## Reading

```python
import geopandas as gpd, rasterio
from segmentation_cartes_etat_major import config

ocs = gpd.read_parquet(config.LABELS / "ocs_ancien.parquet", bbox=(650000, 6650000, 670000, 6670000))
with rasterio.open(config.SCANS_VRT) as src:
    ...
```

```sql
-- DuckDB
INSTALL spatial; LOAD spatial;
SELECT theme, sum(ST_Area(geometry)) / 1e6 AS km2
FROM 'data/raw/bdcarto_em/ocs_ancien.parquet' GROUP BY theme ORDER BY km2 DESC;
```
"""
