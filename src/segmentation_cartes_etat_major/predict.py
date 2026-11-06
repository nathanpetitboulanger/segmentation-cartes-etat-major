"""Predict whole scan tiles with the trained U-Net (config.CHECKPOINT).

For each tile, a uint8 class raster (config.CLASSES ids 1-8) with the same name, grid and
colour table as its label tile goes to config.PREDICTIONS, so predictions, labels and
scans line up in QGIS; config.PREDICTIONS_VRT is their mosaic.

PatchDataset with min_labelled=0 serves every window of a tile, with the same context as
in training: the neighbouring tile, or a mirror image at the edge of the scans. Each
window's prediction (its central out_size px) is pasted at its place in the tile.

A prediction newer than the checkpoint is kept, so an interrupted run resumes, and a new
training makes every tile be predicted again.
"""

import numpy as np
import rasterio
import torch
from torch import nn
from torch.utils.data import DataLoader

from segmentation_cartes_etat_major import config
from segmentation_cartes_etat_major.dataset import PatchDataset
from segmentation_cartes_etat_major.model import load_unet
from segmentation_cartes_etat_major.train import split_tiles
from segmentation_cartes_etat_major.writers import write_class_cog, write_vrt


@torch.no_grad()
def predict_tile(model: nn.Module, tile: str, device: torch.device) -> np.ndarray:
    """Class id (1-8) of every pixel of `tile`, an array the shape of the tile."""
    dataset = PatchDataset([tile], min_labelled=0)
    loader = DataLoader(
        dataset, batch_size=config.BATCH_SIZE, num_workers=config.NUM_WORKERS
    )
    with rasterio.open(config.LABEL_TILES / tile) as src:
        classes = np.zeros(src.shape, np.uint8)
    out = dataset.out_size
    windows = iter(dataset.patches)  # in the loader's order, as it does not shuffle
    for images, _ in loader:
        with torch.autocast(device.type, dtype=torch.bfloat16):
            logits = model(images.to(device))
        # class index 0-7 back to class id 1-8, as in the label tiles
        preds = (logits.argmax(dim=1) + 1).byte().cpu().numpy()
        for pred, (_, row, col) in zip(preds, windows):
            classes[row : row + out, col : col + out] = pred
    return classes


def predict(tiles: list[str] | None = None, every_tile: bool = False) -> None:
    """Write the prediction of `tiles` (file names), of every scan tile if `every_tile`,
    or else of the test tiles, then the mosaic of all the predictions."""
    if every_tile:
        tiles = sorted(path.name for path in config.LABEL_TILES.glob("*.tif"))
    elif not tiles:
        _, _, tiles = split_tiles()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = load_unet(device)
    trained = config.CHECKPOINT.stat().st_mtime
    config.PREDICTIONS.mkdir(parents=True, exist_ok=True)

    for i, tile in enumerate(tiles, 1):
        dst = config.PREDICTIONS / tile
        if dst.exists() and dst.stat().st_mtime > trained:
            print(f"predict  {i:>3}/{len(tiles)}  {tile}  done before", flush=True)
            continue
        classes = predict_tile(model, tile, device)
        with rasterio.open(config.LABEL_TILES / tile) as src:
            profile = {
                "width": src.width,
                "height": src.height,
                "crs": src.crs,
                "transform": src.transform,
            }
        write_class_cog(classes, profile, dst)
        print(f"predict  {i:>3}/{len(tiles)}  {tile}", flush=True)

    write_vrt(sorted(config.PREDICTIONS.glob("*.tif")), config.PREDICTIONS_VRT)
