"""Score the trained U-Net (config.CHECKPOINT) on the test tiles: IoU and F1 per class.

Training never sees the test tiles, not even to pick its best epoch (the val tiles do
that), so these are the scores to report.

The scores are printed and written to config.SCORES (JSON): the tiles scored, the means,
each class's pixels, IoU and F1 (null for a class absent from the tiles), and the
confusion matrix in pixels, rows = true class, columns = predicted, in config.CLASSES
order.
"""

import json
import math

import torch
from torch.utils.data import DataLoader

from segmentation_cartes_etat_major import config, metrics
from segmentation_cartes_etat_major.dataset import PatchDataset
from segmentation_cartes_etat_major.model import UNet, load_unet
from segmentation_cartes_etat_major.train import split_tiles


@torch.no_grad()
def confusion_on_tiles(
    model: UNet, tiles: list[str], device: torch.device
) -> torch.Tensor:
    """Confusion matrix of `model` over every patch of `tiles`."""
    loader = DataLoader(
        PatchDataset(tiles),
        batch_size=config.BATCH_SIZE,
        num_workers=config.NUM_WORKERS,
    )
    n = metrics.N_CLASSES
    cm = torch.zeros(n, n, dtype=torch.long, device=device)
    model.eval()
    for images, labels in loader:
        images, labels = images.to(device), labels.to(device)
        with torch.autocast(device.type, dtype=torch.bfloat16):
            logits = model(images)
        cm += metrics.confusion_matrix(logits.argmax(dim=1), labels)
    return cm.cpu()


def evaluate(n_tiles: int | None = None) -> None:
    """Print the IoU and F1 of each class, their means and the pixel accuracy on the test
    tiles, or on the first `n_tiles` of them only, for a quick run, and write them to
    config.SCORES."""
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    _, _, tiles = split_tiles()
    if n_tiles is not None:
        tiles = tiles[:n_tiles]
    cm = confusion_on_tiles(load_unet(device), tiles, device)

    ious, f1s = metrics.iou(cm), metrics.f1(cm)
    names = [name for name, _, _ in config.CLASSES.values()]
    pixels = cm.sum(dim=1)
    accuracy = cm.diag().sum() / cm.sum()
    print(f"{len(tiles)} test tiles, weights from {config.CHECKPOINT.name}\n")
    print(f"{'class':<15}{'pixels':>13}{'IoU':>8}{'F1':>8}")
    for name, n, iou, f1 in zip(names, pixels, ious, f1s):
        print(f"{name:<15}{n:>13,}{iou:>8.3f}{f1:>8.3f}")
    print(
        f"\nmIoU {torch.nanmean(ious):.3f}   mean F1 {torch.nanmean(f1s):.3f}   "
        f"pixel accuracy {accuracy:.3f}"
    )

    scores = {
        "checkpoint": config.CHECKPOINT.name,
        "tiles": tiles,
        "miou": _number(torch.nanmean(ious)),
        "mean_f1": _number(torch.nanmean(f1s)),
        "pixel_accuracy": _number(accuracy),
        "classes": {
            name: {"pixels": int(n), "iou": _number(iou), "f1": _number(f1)}
            for name, n, iou, f1 in zip(names, pixels, ious, f1s)
        },
        "confusion_matrix": cm.tolist(),
    }
    config.SCORES.write_text(json.dumps(scores, indent=2) + "\n")
    print(f"written to {config.SCORES.relative_to(config.ROOT)}")


def _number(x: torch.Tensor) -> float | None:
    """A score for JSON, which has no nan: None for a class absent from the tiles."""
    value = float(x)
    return None if math.isnan(value) else round(value, 4)
