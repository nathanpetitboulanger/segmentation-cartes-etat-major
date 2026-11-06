"""U-Net (Ronneberger et al., 2015) mapping a scan patch to the classes of config.CLASSES.

Two forms of the same network, picked with `padded`:

    padded=False  the paper's: every 3x3 conv trims 1 px per side, so the network
                  returns the centre of its input, 572 px in -> 388 px out
                  (config.PATCH_SIZE -> config.PATCH_OUT_SIZE, what PatchDataset serves).
                  Inputs of 16k + 124 px, k >= 4.
    padded=True   "same" convs keep the size: the output is as large as the input.
                  Inputs of 16k px; train it on PatchDataset(tiles, size=576, out_size=576).

The output is raw logits (batch, n_classes, h, w), for
nn.CrossEntropyLoss(ignore_index=config.IGNORE_INDEX).
"""

# Fix: the two forms were scripts/model_unet_padding.py and scripts/model_UNET_without_padding,
# with swapped names (the "padding" one had padding=0, the "without_padding" one "same"),
# the second without .py so it could not be imported, and both in scripts/, which only holds
# command-line entry points. They are now one class in the package, picked by `padded`.
# Fix: the matplotlib import is gone (unused, and not a dependency of the project, so the
# scripts failed on it), and so is the Colab header. Nothing runs at import any more: the
# model built and run on torch.rand at the bottom of each script is now tests/test_model.py.

from pathlib import Path

import torch
from torch import nn

from segmentation_cartes_etat_major import config


def double_conv(in_channels: int, out_channels: int, padded: bool) -> nn.Sequential:
    """Two 3x3 convs with ReLU: one level of the U."""
    padding = "same" if padded else "valid"
    return nn.Sequential(
        nn.Conv2d(in_channels, out_channels, kernel_size=3, padding=padding),
        nn.ReLU(),
        nn.Conv2d(out_channels, out_channels, kernel_size=3, padding=padding),
        nn.ReLU(),
    )


def centre_crop(x: torch.Tensor, height: int, width: int) -> torch.Tensor:
    """The central height x width px of x."""
    top, left = (x.shape[-2] - height) // 2, (x.shape[-1] - width) // 2
    return x[..., top : top + height, left : left + width]


class UNet(nn.Module):
    def __init__(
        self,
        padded: bool = False,
        in_channels: int = 3,
        # Fix: was 10 output channels ("mettre nombre de classe"); there are 8 classes
        n_classes: int = len(config.CLASSES),
    ):
        super().__init__()
        self.padded = padded
        self.encoder = nn.ModuleList(
            [
                double_conv(in_channels, 64, padded),
                double_conv(64, 128, padded),
                double_conv(128, 256, padded),
                double_conv(256, 512, padded),
            ]
        )
        self.pool = nn.MaxPool2d(kernel_size=2, stride=2)
        self.bottleneck = double_conv(512, 1024, padded)
        self.upsample = nn.ModuleList(
            [
                nn.ConvTranspose2d(1024, 512, kernel_size=2, stride=2),
                nn.ConvTranspose2d(512, 256, kernel_size=2, stride=2),
                nn.ConvTranspose2d(256, 128, kernel_size=2, stride=2),
                nn.ConvTranspose2d(128, 64, kernel_size=2, stride=2),
            ]
        )
        # each takes the upsampled map and the encoder map of its level, concatenated
        self.decoder = nn.ModuleList(
            [
                double_conv(1024, 512, padded),
                double_conv(512, 256, padded),
                double_conv(256, 128, padded),
                double_conv(128, 64, padded),
            ]
        )
        self.head = nn.Conv2d(64, n_classes, kernel_size=1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # Fix: forward no longer prints the shape of every block
        skips = []
        for level, block in enumerate(self.encoder):
            x = block(x if level == 0 else self.pool(x))
            skips.append(x)
        x = self.bottleneck(self.pool(x))
        for upsample, block, skip in zip(self.upsample, self.decoder, reversed(skips)):
            x = upsample(x)
            # Fix: the skips were cut by hard-coded margins (4, 16, 40, 88 px), right for a
            # 572 px input only; crop them to the upsampled map instead (a no-op if padded)
            x = block(torch.cat([x, centre_crop(skip, *x.shape[-2:])], dim=1))
        return self.head(x)


def load_unet(device: torch.device, checkpoint: Path = config.CHECKPOINT) -> UNet:
    """The unpadded UNet with the weights train.py saved, on `device`, in eval mode."""
    model = UNet()
    model.load_state_dict(torch.load(checkpoint, map_location=device))
    return model.to(device).eval()
