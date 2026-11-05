"""Train the U-Net (model.py) on PatchDataset (dataset.py) patches.

The label tiles are split into train and val by tile, not by patch: neighbouring patches
share 2 * margin px of input, so a patch split would show the network val pixels during
training. The weights of the epoch with the lowest val loss go to config.CHECKPOINT.
"""

import random

import torch
from torch import nn
from torch.utils.data import DataLoader

from segmentation_cartes_etat_major import config
from segmentation_cartes_etat_major.dataset import PatchDataset
from segmentation_cartes_etat_major.model import UNet


def split_tiles(
    val_fraction: float = config.VAL_FRACTION, seed: int = config.SEED
) -> tuple[list[str], list[str]]:
    """(train, val) file names of the label tiles, `val_fraction` of them in val."""
    # sorted first: glob order depends on the filesystem, and the split must not
    tiles = sorted(path.name for path in config.LABEL_TILES.glob("*.tif"))
    random.Random(seed).shuffle(tiles)
    n_val = round(len(tiles) * val_fraction)
    return tiles[n_val:], tiles[:n_val]


def train_one_epoch(
    model: nn.Module,
    loader: DataLoader,
    loss_fn: nn.Module,
    optimizer: torch.optim.Optimizer,
    device: torch.device,
    log_every: int = 100,
) -> float:
    """Mean training loss over one pass of `loader`, printed every `log_every` steps."""
    model.train()
    total = 0.0
    for step, (images, labels) in enumerate(loader, start=1):
        images, labels = images.to(device), labels.to(device)
        optimizer.zero_grad()
        with torch.autocast(device.type, dtype=torch.bfloat16):
            logits = model(images)
            loss = loss_fn(logits, labels)
        loss.backward()
        optimizer.step()
        total += loss.item()
        if step % log_every == 0:
            print(f"  step {step}/{len(loader)}  loss {total / step:.4f}")
    return total / len(loader)


@torch.no_grad()
def evaluate(
    model: nn.Module, loader: DataLoader, loss_fn: nn.Module, device: torch.device
) -> tuple[float, float]:
    """Mean loss and pixel accuracy (over the labelled pixels) of one pass of `loader`."""
    model.eval()
    total, correct, counted = 0.0, 0, 0
    for images, labels in loader:
        images, labels = images.to(device), labels.to(device)
        with torch.autocast(device.type, dtype=torch.bfloat16):
            logits = model(images)
            loss = loss_fn(logits, labels)
        total += loss.item()
        preds = logits.argmax(dim=1)
        labelled = labels != config.IGNORE_INDEX
        correct += (preds[labelled] == labels[labelled]).sum().item()
        counted += labelled.sum().item()
    return total / len(loader), correct / counted


def train(epochs: int = config.EPOCHS, n_tiles: int | None = None) -> None:
    """Train a UNet for `epochs` epochs, keeping the weights of the lowest val loss in
    config.CHECKPOINT. `n_tiles` keeps only the first n tiles of each split, for test runs."""
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    train_tiles, val_tiles = split_tiles()
    if n_tiles is not None:
        train_tiles, val_tiles = train_tiles[:n_tiles], val_tiles[:n_tiles]
    train_set, val_set = PatchDataset(train_tiles), PatchDataset(val_tiles)
    train_loader = DataLoader(
        train_set,
        batch_size=config.BATCH_SIZE,
        shuffle=True,
        num_workers=config.NUM_WORKERS,
    )
    val_loader = DataLoader(
        val_set,
        batch_size=config.BATCH_SIZE,
        num_workers=config.NUM_WORKERS,
    )
    print(
        f"{len(train_tiles)} train tiles ({len(train_set)} patches), "
        f"{len(val_tiles)} val tiles ({len(val_set)} patches), on {device}"
    )

    model = UNet().to(device)
    loss_fn = nn.CrossEntropyLoss(ignore_index=config.IGNORE_INDEX)
    optimizer = torch.optim.Adam(model.parameters(), lr=config.LEARNING_RATE)

    config.CHECKPOINT.parent.mkdir(parents=True, exist_ok=True)
    best = float("inf")
    for epoch in range(1, epochs + 1):
        train_loss = train_one_epoch(model, train_loader, loss_fn, optimizer, device)
        val_loss, val_acc = evaluate(model, val_loader, loss_fn, device)
        line = (
            f"epoch {epoch}/{epochs}  train loss {train_loss:.4f}  "
            f"val loss {val_loss:.4f}  val acc {val_acc:.3f}"
        )
        if val_loss < best:
            best = val_loss
            torch.save(model.state_dict(), config.CHECKPOINT)
            line += "  saved"
        print(line)
