"""Score the trained U-Net (config.CHECKPOINT) on the test tiles: IoU per class and mIoU.

Training never sees the test tiles, not even to pick its best epoch (the val tiles do
that), so these are the scores to report.
"""

import torch
from torch.utils.data import DataLoader

from segmentation_cartes_etat_major import config, metrics
from segmentation_cartes_etat_major.dataset import PatchDataset
from segmentation_cartes_etat_major.model import UNet
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
    tiles, or on the first `n_tiles` of them only, for a quick run."""
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    _, _, tiles = split_tiles()
    if n_tiles is not None:
        tiles = tiles[:n_tiles]
    model = UNet().to(device)
    model.load_state_dict(torch.load(config.CHECKPOINT, map_location=device))
    cm = confusion_on_tiles(model, tiles, device)

    ious, f1s = metrics.iou(cm), metrics.f1(cm)
    print(f"{len(tiles)} test tiles, weights from {config.CHECKPOINT.name}\n")
    print(f"{'class':<15}{'pixels':>13}{'IoU':>8}{'F1':>8}")
    names = [name for name, _, _ in config.CLASSES.values()]
    for name, pixels, iou, f1 in zip(names, cm.sum(dim=1), ious, f1s):
        print(f"{name:<15}{pixels:>13,}{iou:>8.3f}{f1:>8.3f}")
    accuracy = cm.diag().sum() / cm.sum()
    print(
        f"\nmIoU {torch.nanmean(ious):.3f}   mean F1 {torch.nanmean(f1s):.3f}   "
        f"pixel accuracy {accuracy:.3f}"
    )
