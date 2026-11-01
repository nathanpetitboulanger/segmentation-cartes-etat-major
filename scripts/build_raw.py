"""Build data/raw/: the IGN État-major scans and labels, in modern formats.

    uv run scripts/build_raw.py SOURCE [--workers N]

SOURCE is the directory holding the extracted IGN data; see segmentation_cartes_etat_major.build_raw.
Safe to rerun: finished files are skipped.
"""

import argparse
import os
from pathlib import Path

from segmentation_cartes_etat_major import build_raw


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "source", type=Path, help="directory holding the extracted IGN data"
    )
    parser.add_argument(
        "--workers", type=int, default=os.cpu_count(), help="parallel tile conversions"
    )
    args = parser.parse_args()
    build_raw.build(args.source, args.workers)


if __name__ == "__main__":
    main()
