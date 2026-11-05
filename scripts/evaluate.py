"""Score the trained U-Net (models/unet.pt) on the test tiles: IoU per class and mIoU.

    uv run scripts/evaluate.py [--tiles N]

Needs a checkpoint (scripts/train.py).
"""

import argparse

from segmentation_cartes_etat_major import evaluate


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--tiles",
        type=int,
        default=None,
        help="only the first N test tiles, for a quick run",
    )
    args = parser.parse_args()
    evaluate.evaluate(args.tiles)


if __name__ == "__main__":
    main()
