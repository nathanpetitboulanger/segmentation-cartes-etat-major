"""Predict scan tiles with the trained U-Net (models/unet.pt): one class raster per tile in
models/predictions/, and their mosaic models/predictions.vrt, to open in QGIS.

    uv run scripts/predict.py              # the test tiles
    uv run scripts/predict.py --all        # every scan tile
    uv run scripts/predict.py TILE [...]   # these tiles, e.g. SCEM40K_0680_6900_L93_E100.tif

Needs a checkpoint (scripts/train.py). Safe to rerun: tiles predicted since the last
training are skipped.
"""

import argparse

from segmentation_cartes_etat_major import predict


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "tiles", nargs="*", help="tile file names (default: the test tiles)"
    )
    parser.add_argument("--all", action="store_true", help="every scan tile")
    args = parser.parse_args()
    predict.predict(args.tiles, every_tile=args.all)


if __name__ == "__main__":
    main()
