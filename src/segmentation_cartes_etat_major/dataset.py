"""PyTorch Dataset of (scan, label) patches, read on the fly from the tiles.

A sample is one square patch of `size` px, the same window of a scan tile and of its
label tile (data/interim/labels/, same grid):

    image  float32 (3, size, size): RGB scaled to [0, 1], channels first like PyTorch
    label  int64 (size, size): class 0-7 (config.CLASSES id - 1), IGNORE_INDEX if unlabelled

__init__ only lists where the patches are; the pixels are read in __getitem__, so the
16 GB of scans never sit in memory and the DataLoader workers read in parallel.
"""

import numpy as np
import rasterio
import torch
from rasterio.windows import Window
from torch.utils.data import Dataset

from segmentation_cartes_etat_major import config


class PatchDataset(Dataset):
    def __init__(
        self,
        tiles: list[str],
        size: int = config.PATCH_SIZE,
        min_labelled: float = 0.5,
    ):
        """Patches on a regular grid over each tile of `tiles` (file names), kept when at
        least `min_labelled` of their pixels have a label."""
        self.size = size
        self.patches = []  # (tile, row, col) of each patch's top-left pixel
        for tile in tiles:
            with rasterio.open(config.LABEL_TILES / tile) as src:
                labelled = src.read(1) > 0
            h, w = labelled.shape
            # a regular grid, plus a last row and column of patches flush with the edge
            rows = [*range(0, h - size, size), h - size]
            cols = [*range(0, w - size, size), w - size]
            for row in rows:
                for col in cols:
                    patch = labelled[row : row + size, col : col + size]
                    if patch.mean() >= min_labelled:
                        self.patches.append((tile, row, col))

    def __len__(self) -> int:
        return len(self.patches)

    def __getitem__(self, i: int) -> tuple[torch.Tensor, torch.Tensor]:
        tile, row, col = self.patches[i]
        window = Window.from_slices((row, row + self.size), (col, col + self.size))
        # opened here rather than in __init__, so each DataLoader worker has its own files
        with rasterio.open(config.SCANS / tile) as src:
            image = src.read(window=window)
        with rasterio.open(config.LABEL_TILES / tile) as src:
            label = src.read(1, window=window).astype(np.int64) - 1  # 1-8 -> 0-7
        label[label < 0] = config.IGNORE_INDEX
        return torch.from_numpy(image).float() / 255, torch.from_numpy(label)
