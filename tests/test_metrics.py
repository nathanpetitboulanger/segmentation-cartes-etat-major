import torch

from segmentation_cartes_etat_major import config
from segmentation_cartes_etat_major.metrics import confusion_matrix, f1, iou


def test_confusion_matrix():
    labels = torch.tensor([0, 0, 1, 2, 2, config.IGNORE_INDEX])
    preds = torch.tensor([0, 1, 1, 2, 0, 1])
    cm = confusion_matrix(preds, labels, n_classes=3)
    # row = true class, column = predicted; the ignored last pixel is not counted
    expected = torch.tensor(
        [
            [1, 1, 0],
            [0, 1, 0],
            [1, 0, 1],
        ]
    )
    assert torch.equal(cm, expected)


def test_iou():
    cm = torch.tensor(
        [
            [1, 1, 0],
            [0, 1, 0],
            [1, 0, 1],
        ]
    )
    # class 0: 1 correct, 2 true, 2 predicted -> 1 / (2 + 2 - 1)
    # class 1: 1 correct, 1 true, 2 predicted -> 1 / (1 + 2 - 1)
    # class 2: 1 correct, 2 true, 1 predicted -> 1 / (2 + 1 - 1)
    expected = torch.tensor([1 / 3, 1 / 2, 1 / 2], dtype=torch.float64)
    assert torch.allclose(iou(cm), expected)


def test_f1():
    cm = torch.tensor(
        [
            [1, 1, 0],
            [0, 1, 0],
            [1, 0, 1],
        ]
    )
    # class 0: 2 * 1 / (2 true + 2 predicted); class 1: 2 / (1 + 2); class 2: 2 / (2 + 1)
    expected = torch.tensor([1 / 2, 2 / 3, 2 / 3], dtype=torch.float64)
    assert torch.allclose(f1(cm), expected)
    assert torch.allclose(f1(cm), 2 * iou(cm) / (1 + iou(cm)))


def test_iou_of_an_absent_class_is_nan():
    cm = torch.tensor([[2, 0], [0, 0]])  # class 1 neither present nor predicted
    scores = iou(cm)
    assert scores[0] == 1 and scores[1].isnan()
    assert torch.nanmean(scores) == 1  # the mean skips it
