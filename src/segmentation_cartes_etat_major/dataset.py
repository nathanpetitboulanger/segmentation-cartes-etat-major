"""PyTorch Dataset of (scan, label) patches for an unpadded U-Net, read on the fly.

The network maps a `size` px input to its central `out_size` px, losing
margin = (size - out_size) / 2 px of context per side. A sample is

    image  float32 (3, size, size): RGB scaled to [0, 1], channels first like PyTorch
    label  int64 (out_size, out_size): class 0-7 (config.CLASSES id - 1), IGNORE_INDEX if
           unlabelled, for the central out_size px of the image

The label windows tile each label tile (data/interim/labels/) with a stride of out_size,
so every labelled pixel is a target once. The image windows around them overlap by
2 * margin and are read from the scan mosaic: at a tile edge they reach into the
neighbouring tile, or, where there is none (the edge of the scanned area), into a mirror
image of the tile.

__init__ only lists where the patches are; the pixels are read in __getitem__, so the
16 GB of scans never sit in memory and the DataLoader workers read in parallel.
"""

import geopandas as gpd
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
        out_size: int = config.PATCH_OUT_SIZE,
        min_labelled: float = 0.5,
    ):
        """Label windows on a regular grid over each tile of `tiles` (file names), kept
        when at least `min_labelled` of their pixels have a label."""
        assert out_size <= size and (size - out_size) % 2 == 0, (
            f"no margin fits a {size} px input around a {out_size} px output"
        )
        self.size, self.out_size = size, out_size
        self.margin = (size - out_size) // 2

        # where each scan tile sits in the mosaic, all of them on a grid of tile-sized cells
        with rasterio.open(config.SCANS_VRT) as src:
            self.mosaic_shape = src.shape
            to_px = ~src.transform
        footprints = gpd.read_parquet(config.SCAN_TILES)
        self.offsets = {}  # tile: (row, col) of its top-left pixel in the mosaic
        for tile, (left, _, _, top) in zip(footprints["tile"], footprints.bounds.values):
            col, row = to_px * (left, top)
            self.offsets[tile] = (round(row), round(col))
        with rasterio.open(config.SCANS / footprints["tile"][0]) as src:
            self.cell = src.height
        corners = np.array([*self.offsets.values(), self.mosaic_shape])
        assert (corners % self.cell == 0).all(), "the scan tiles are not all on one grid"
        # cells with a scan, bordered by one row and column of empty cells
        rows, cols = (n // self.cell for n in self.mosaic_shape)
        self.scanned = np.zeros((rows + 2, cols + 2), bool)
        for row, col in self.offsets.values():
            self.scanned[row // self.cell + 1, col // self.cell + 1] = True

        self.patches = []  # (tile, row, col) of each label window's top-left pixel
        for tile in tiles:
            with rasterio.open(config.LABEL_TILES / tile) as src:
                labelled = src.read(1) > 0
            h, w = labelled.shape
            # a regular grid, plus a last row and column of windows flush with the edge
            rows = [*range(0, h - out_size, out_size), h - out_size]
            cols = [*range(0, w - out_size, out_size), w - out_size]
            for row in rows:
                for col in cols:
                    patch = labelled[row : row + out_size, col : col + out_size]
                    if patch.mean() >= min_labelled:
                        self.patches.append((tile, row, col))

    def __len__(self) -> int:
        return len(self.patches)

    def __getitem__(self, i: int) -> tuple[torch.Tensor, torch.Tensor]:
        tile, row, col = self.patches[i]
        out = self.out_size
        window = Window.from_slices((row, row + out), (col, col + out))
        # opened here rather than in __init__, so each DataLoader worker has its own files
        with rasterio.open(config.LABEL_TILES / tile) as src:
            label = src.read(1, window=window).astype(np.int64) - 1  # 1-8 -> 0-7
        label[label < 0] = config.IGNORE_INDEX
        image = self._image(tile, row, col)
        return torch.from_numpy(image).float() / 255, torch.from_numpy(label)

    def _image(self, tile: str, row: int, col: int) -> np.ndarray:
        """The size px of scan centred on the label window at (row, col) of `tile`."""
        size, (height, width) = self.size, self.mosaic_shape
        tile_top, tile_left = self.offsets[tile]
        top, left = tile_top + row - self.margin, tile_left + col - self.margin
        # only windows of tiles on the outer edge of the mosaic reach past it
        r0, r1 = max(top, 0), min(top + size, height)
        c0, c1 = max(left, 0), min(left + size, width)
        image = np.zeros((3, size, size), np.uint8)
        with rasterio.open(config.SCANS_VRT) as src:
            image[:, r0 - top : r1 - top, c0 - left : c1 - left] = src.read(
                window=Window.from_slices((r0, r1), (c0, c1))
            )

        # the mosaic reads 0 off the scanned cells: mirror the tile there instead
        rows = (top + np.arange(size)) // self.cell + 1
        cols = (left + np.arange(size)) // self.cell + 1
        scanned = self.scanned[np.ix_(rows, cols)]
        if scanned.all():
            return image
        r0, r1 = max(tile_top - top, 0), min(tile_top + self.cell - top, size)
        c0, c1 = max(tile_left - left, 0), min(tile_left + self.cell - left, size)
        mirrored = np.pad(
            image[:, r0:r1, c0:c1],
            ((0, 0), (r0, size - r1), (c0, size - c1)),
            mode="reflect",
        )
        return np.where(scanned, image, mirrored)
