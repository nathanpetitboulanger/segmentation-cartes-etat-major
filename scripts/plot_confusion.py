"""Plot the confusion matrix of the test tiles to reports/figures/confusion_matrix.png,
each row in % of its true class, with the IoU of each class.

    uv run scripts/plot_confusion.py

Needs the scores of scripts/evaluate.py (models/unet_scores.json).
"""

import argparse

from segmentation_cartes_etat_major import plots


def main() -> None:
    argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    ).parse_args()
    plots.plot_confusion()


if __name__ == "__main__":
    main()
