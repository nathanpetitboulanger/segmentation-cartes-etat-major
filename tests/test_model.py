import pytest
import torch

from segmentation_cartes_etat_major import config
from segmentation_cartes_etat_major.model import UNet

N_CLASSES = len(config.CLASSES)


@pytest.mark.parametrize(
    "padded, size, out_size",
    [
        (False, config.PATCH_SIZE, config.PATCH_OUT_SIZE),  # 572 -> 388, PatchDataset's
        (False, 188, 4),  # the smallest input the unpadded net takes
        (True, 576, 576),
        (True, 64, 64),
    ],
)
def test_output_shape(padded: bool, size: int, out_size: int):
    model = UNet(padded=padded)
    with torch.no_grad():
        y = model(torch.rand(2, 3, size, size))
    assert y.shape == (2, N_CLASSES, out_size, out_size)

