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

# Training samples (dataset.py). An unpadded U-Net (4 poolings, two 3x3 convs per level)
# returns the central 388 px of a 572 px input, 92 px of context lost per side. Other
# sizes it accepts: 16k + 124 px in, 16k - 60 px out.
PATCH_SIZE = 572  # px of scan in, 2.3 km at 4 m/px
PATCH_OUT_SIZE = 388  # px of prediction out, the stride of the patch grid
IGNORE_INDEX = 255  # target of unlabelled pixels, skipped by the loss

# Training (train.py)
BATCH_SIZE = 8  # patches per step, 4.3 GB of an 8 GB GPU with bf16 autocast
LEARNING_RATE = 1e-4  # Adam
EPOCHS = 10
VAL_FRACTION = 0.1  # share of the label tiles that picks the best epoch
TEST_FRACTION = 0.1  # share held out for the final score, never seen in training
SEED = 42  # of the train/val/test split, so every run gets the same tiles
CHECKPOINT = MODELS / "unet.pt"  # weights of the epoch with the lowest val loss
NUM_WORKERS = 8  # DataLoader processes reading patches; the GPU needs >= 3
PATIENCE = 3

# Outputs of the trained U-Net, next to CHECKPOINT
SCORES = MODELS / "unet_scores.json"  # evaluate.py: scores of CHECKPOINT, test tiles
PREDICTIONS = MODELS / "predictions"  # predict.py: one class raster per scan tile
PREDICTIONS_VRT = MODELS / "predictions.vrt"  # mosaic of PREDICTIONS

# reports/figures/, made by the plot scripts
FIGURES = REPORTS / "figures"
PREDICTION_FIGURES = FIGURES / "predictions"  # plots.py: one PNG per predicted tile
CONFUSION_FIGURE = FIGURES / "confusion_matrix.png"  # plots.py: from SCORES

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
