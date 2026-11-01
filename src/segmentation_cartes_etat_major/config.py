"""Every path and constant of the project. Read paths from here; never hard-code them."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DATA = ROOT / "data"
RAW = DATA / "raw"
INTERIM = DATA / "interim"
PROCESSED = DATA / "processed"
MODELS = ROOT / "models"
REPORTS = ROOT / "reports"

# data/raw/, built once by scripts/build_raw.py, read-only afterwards
SCANS = RAW / "scan_em40k"  # SCEM40K_XXXX_YYYY_L93_E100.tif: COG, lossless WebP
SCANS_VRT = RAW / "scan_em40k.vrt"  # mosaic of SCANS
SCAN_TILES = RAW / "scan_em40k_tiles.parquet"  # tile footprints, départements touched
LABELS = RAW / "bdcarto_em"  # <layer>.parquet, level-3 georeferencing
IGN_SOURCES = RAW / "ign_sources.tsv"  # IGN download URLs, sizes and MD5s

# data/interim/, built by scripts/build_interim.py
LABEL_TILES = INTERIM / "labels"  # one class raster per scan tile: same name, same grid
LABEL_TILES_VRT = INTERIM / "labels.vrt"  # mosaic of LABEL_TILES
CLASS_TABLE = INTERIM / "classes.csv"  # pixels and area per class

# Land-cover classes rasterized from `ocs_ancien`, keyed by the first EM code of `theme`
# (a mixed code such as EM7.1EM6.2 takes its first part, EM7). 0 = no label.
# Meanings are inferred, except EM1 (it matches the zone_urbaine and batiment layers).
CLASSES = {  # id: (name, first-level EM codes, display colour)
    1: ("cropland", (4,), "#efe3bd"),
    2: ("pasture_heath", (8,), "#eda100"),
    3: ("meadow", (7,), "#1baf7a"),
    4: ("forest", (9,), "#008300"),
    5: ("vineyard", (5,), "#4a3aa7"),
    6: ("water", (10,), "#2a78d6"),
    7: ("built", (1,), "#e34948"),
    8: ("other", (3, 6, 11, 12, 13, 14, 15), "#52514e"),
}

# Training samples (dataset.py)
PATCH_SIZE = 512  # px = 2 km at 4 m/px, the block size of the tiles
IGNORE_INDEX = 255  # target of unlabelled pixels, skipped by the loss

CRS = "EPSG:2154"  # Lambert-93
DEPARTEMENTS = tuple("02 03 07 13 15 18 22 29 42 43 48 56 59 62 63 74".split())

# BD CARTO® État-major layers, one GeoParquet each in LABELS
LABEL_LAYERS = (
    "ocs_ancien",
    "ocs_ancien_sans_bati",
    "batiment",
    "batiment_hors_zone_urbaine",
    "zone_urbaine",
    "route",
    "voie_ferree",
    "cours_d_eau",
    "limite_administrative",
    "surface_administrative",
    "chantier",
    "feuille",
)
