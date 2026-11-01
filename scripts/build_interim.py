"""Build data/interim/: the land cover rasterized onto every scan tile, 8 classes.

    uv run scripts/build_interim.py [--workers N]

Needs data/raw/ (scripts/build_raw.py). Safe to rerun: finished tiles are skipped.
"""

import argparse
import os

from segmentation_cartes_etat_major import build_interim


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--workers", type=int, default=os.cpu_count(), help="parallel tiles"
    )
    args = parser.parse_args()
    build_interim.build(args.workers)


if __name__ == "__main__":
    main()
