"""Build data/processed/ for the dashboards: web map tiles of the labels and the scans,
and the class areas of every scan tile.

    uv run scripts/build_processed.py [--only labels scans stats] [--force]
                                      [--threads N] [--workers N]

Needs data/raw/ and data/interim/ (scripts/build_raw.py, scripts/build_interim.py) and the
GDAL >= 3.11 command line (`gdal raster tile`). Safe to rerun: finished steps are skipped
in a second, an interrupted tile layer resumes. The first build of the scan tiles takes
about 30 minutes, the labels about 6.
"""

import argparse
import os

from segmentation_cartes_etat_major import build_processed


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--only",
        nargs="+",
        choices=build_processed.STEPS,
        default=build_processed.STEPS,
        help="steps to build (default: all)",
    )
    parser.add_argument(
        "--force", action="store_true", help="rebuild the steps even if finished"
    )
    parser.add_argument(
        "--threads", type=int, default=os.cpu_count(), help="gdal tiling threads"
    )
    parser.add_argument(
        "--workers", type=int, default=os.cpu_count(), help="parallel tile stats"
    )
    args = parser.parse_args()
    build_processed.build(tuple(args.only), args.workers, args.threads, args.force)


if __name__ == "__main__":
    main()
