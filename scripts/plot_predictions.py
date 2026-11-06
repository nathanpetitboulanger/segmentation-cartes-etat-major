"""Plot the predictions against the labels: one PNG per tile in reports/figures/predictions/
with the scan, the labels, the prediction and where they disagree.

    uv run scripts/plot_predictions.py              # every tile in models/predictions/
    uv run scripts/plot_predictions.py TILE [...]   # these tiles

Needs predictions (scripts/predict.py).
"""

import argparse

from segmentation_cartes_etat_major import plots


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "tiles", nargs="*", help="tile file names (default: every predicted tile)"
    )
    args = parser.parse_args()
    plots.plot_predictions(args.tiles)


if __name__ == "__main__":
    main()
