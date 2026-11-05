"""Segmentation scores, all computed from one confusion matrix.

The matrix is summed over batches (cm += confusion_matrix(preds, labels)), and the scores
are read from the total, so every pixel weighs the same whatever its batch.
"""

import torch

from segmentation_cartes_etat_major import config

N_CLASSES = len(config.CLASSES)


def confusion_matrix(
    preds: torch.Tensor, labels: torch.Tensor, n_classes: int = N_CLASSES
) -> torch.Tensor:
    """(n_classes, n_classes) pixel counts, row = true class, column = predicted class.

    preds and labels hold class indices 0 to n_classes - 1, of any but the same shape;
    pixels labelled config.IGNORE_INDEX are left out.
    """
    labelled = labels != config.IGNORE_INDEX
    # each (true, predicted) pair as one number, true * n + predicted, in 0 to n² - 1
    pairs = labels[labelled] * n_classes + preds[labelled]
    counts = torch.bincount(pairs, minlength=n_classes**2)
    return counts.reshape(n_classes, n_classes)


def iou(cm: torch.Tensor) -> torch.Tensor:
    """IoU of each class: correct / (true + predicted - correct) pixels.

    nan for a class neither present nor predicted (0 / 0); average with torch.nanmean.
    """
    cm = cm.double()  # full-precision ratios, whatever the type of the counts
    correct = cm.diag()
    true = cm.sum(dim=1)  # row sums: pixels that are the class
    predicted = cm.sum(dim=0)  # column sums: pixels predicted as the class
    return correct / (true + predicted - correct)


def f1(cm: torch.Tensor) -> torch.Tensor:
    """F1 (or Dice) of each class: 2 correct / (true + predicted) pixels, the harmonic
    mean of precision and recall. It ranks classes like the IoU: F1 = 2 IoU / (1 + IoU).

    nan for a class neither present nor predicted (0 / 0); average with torch.nanmean.
    """
    cm = cm.double()
    return 2 * cm.diag() / (cm.sum(dim=1) + cm.sum(dim=0))
