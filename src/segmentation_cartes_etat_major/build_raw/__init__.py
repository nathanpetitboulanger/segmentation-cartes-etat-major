"""Build data/raw/ from an extracted copy of the IGN data, in modern formats.

The source directory holds IGN's SCAN État-major® 40K and BD CARTO® État-major (level-3
georeferencing) for the 16 départements, already extracted from IGN's archives:

    <source>/scan_em40k/SCEM40K_*.tif   lossless GeoTIFF tiles, 4 m/px, 5000 x 5000 px
    <source>/scan_em40k_tiles.gpkg      their footprints (layer `tiles`: tile, deps)
    <source>/bdcarto_em_n3.gpkg         one layer per theme, 16 départements merged, `dep` column
    <source>/raw/manifest.tsv           IGN download URLs, sizes and MD5s

Only the formats change. Pixels, geometries and attributes are kept as they are:

    bdcarto.py  labels -> GeoParquet 1.1, one file per layer
    scans.py    scans  -> COG, lossless WebP (about 40 % smaller), checked pixel for pixel
    readme.py   ign_sources.tsv and README.md

Each output is written to a `.part` file then renamed, so an interrupted build resumes.
"""

from pathlib import Path

from segmentation_cartes_etat_major import config
from segmentation_cartes_etat_major.build_raw import bdcarto, readme, scans


def build(source: Path, workers: int) -> None:
    source = source.resolve()
    config.RAW.mkdir(parents=True, exist_ok=True)
    bdcarto.build(source)
    scans.build(source, workers)
    readme.write(source)
