"""Train the U-Net on the label tiles, keeping the best weights in models/unet.pt.

    uv run scripts/train.py [--epochs N] [--tiles N]

Needs data/interim/ (scripts/build_interim.py). A full epoch takes about 35 min.
"""

import argparse

from segmentation_cartes_etat_major import config, train


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--epochs", type=int, default=config.EPOCHS, help="passes over the training tiles"
    )
    parser.add_argument(
        "--tiles",
        type=int,
        default=None,
        help="only the first N tiles of each split, for a test run",
    )
    args = parser.parse_args()
    train.train(args.epochs, args.tiles)


if __name__ == "__main__":
    main()
