"""Figures of the predictions (predict.py) against the labels: one PNG per tile in
config.PREDICTION_FIGURES, for reports.

Four panels: the scan, the labels (BD CARTO), the prediction, and where the last two
disagree. The rasters are read at PANEL_PX px a side from their COG overviews (those of
the class rasters keep the majority class), so a figure stays small; the agreement and
mIoU in the title are computed at full resolution.
"""

import numpy as np
import rasterio
import torch
from matplotlib.figure import Figure
from matplotlib.patches import Patch
from rasterio.enums import Resampling

from segmentation_cartes_etat_major import config, metrics

PANEL_PX = 600  # px a side of each panel, about its size in the saved figure
DPI = 120
SURFACE, INK, INK_2 = "#fcfcfb", "#0b0b0b", "#52514e"  # figure, text, secondary text
SAME, DIFFERENT = "#d9d9d4", "#d03b3b"  # disagreement panel: recessive grey, red
NO_LABEL = SURFACE


def _lut(colours: list[str]) -> np.ndarray:
    """RGB lookup table: row i is the colour of value i."""
    return np.array([list(bytes.fromhex(c[1:])) for c in colours], np.uint8)


CLASS_LUT = _lut([NO_LABEL] + [colour for _, _, colour in config.CLASSES.values()])
ERROR_LUT = _lut([NO_LABEL, SAME, DIFFERENT])


def _read(path, resampling: Resampling) -> np.ndarray:
    with rasterio.open(path) as src:
        return src.read(
            out_shape=(src.count, PANEL_PX, PANEL_PX), resampling=resampling
        )


def tile_scores(tile: str) -> tuple[float, float]:
    """Pixel agreement and mIoU of the prediction of `tile` with its labels, over its
    labelled pixels at full resolution; nan for a tile without labels."""
    with rasterio.open(config.LABEL_TILES / tile) as src:
        labels = torch.from_numpy(src.read(1).astype(np.int64) - 1)  # 1-8 -> 0-7
    with rasterio.open(config.PREDICTIONS / tile) as src:
        preds = torch.from_numpy(src.read(1).astype(np.int64) - 1)
    labels[labels < 0] = config.IGNORE_INDEX
    cm = metrics.confusion_matrix(preds, labels)
    if cm.sum() == 0:
        return float("nan"), float("nan")
    agreement = cm.diag().sum() / cm.sum()
    return agreement.item(), torch.nanmean(metrics.iou(cm)).item()


def plot_tile(tile: str) -> Figure:
    """The four-panel figure of `tile`."""
    scan = _read(config.SCANS / tile, Resampling.bilinear).transpose(1, 2, 0)
    labels = _read(config.LABEL_TILES / tile, Resampling.nearest)[0]
    preds = _read(config.PREDICTIONS / tile, Resampling.nearest)[0]
    errors = np.where(labels == 0, 0, np.where(preds == labels, 1, 2))
    panels = [
        ("Scan", scan),
        ("Labels (BD CARTO)", CLASS_LUT[labels]),
        ("Prediction (U-Net)", CLASS_LUT[preds]),
        ("Disagreement", ERROR_LUT[errors]),
    ]

    fig = Figure(figsize=(9.3, 11.4), facecolor=SURFACE)  # square panel cells
    axes = fig.subplots(
        2,
        2,
        gridspec_kw={
            "left": 0.03,
            "right": 0.97,
            "top": 0.885,
            "bottom": 0.125,
            "wspace": 0.04,
            "hspace": 0.09,
        },
    )
    for ax, (title, image) in zip(axes.flat, panels):
        ax.imshow(image, interpolation="nearest")
        ax.set_title(title, loc="left", fontsize=11, color=INK, pad=5)
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_color(INK_2)
            spine.set_linewidth(0.6)

    agreement, miou = tile_scores(tile)
    fig.text(0.03, 0.965, tile.removesuffix(".tif"), fontsize=14, color=INK)
    scores = (
        f"Agreement {agreement:.1%}   ·   mIoU {miou:.2f}   (labelled pixels of this tile)"
        if agreement == agreement  # not nan
        else "No labelled pixels on this tile"
    )
    fig.text(0.03, 0.935, scores, fontsize=10, color=INK_2)

    swatch = {"edgecolor": INK_2, "linewidth": 0.5}
    classes = [
        Patch(facecolor=colour, label=name, **swatch)
        for name, _, colour in config.CLASSES.values()
    ]
    disagreement = [
        Patch(facecolor=colour, label=name, **swatch)
        for name, colour in (
            ("same class", SAME),
            ("different class", DIFFERENT),
            ("no label", NO_LABEL),
        )
    ]
    legend = {"frameon": False, "fontsize": 9, "labelcolor": INK, "handlelength": 1.4}
    fig.legend(
        handles=classes,
        loc="lower left",
        bbox_to_anchor=(0.03, 0.035),
        ncol=4,
        **legend,
    )
    fig.legend(
        handles=disagreement, loc="lower right", bbox_to_anchor=(0.97, 0.035), **legend
    )
    return fig


def plot_predictions(tiles: list[str] | None = None) -> None:
    """A figure of each of `tiles` (file names), by default of every predicted tile."""
    if not tiles:
        tiles = sorted(path.name for path in config.PREDICTIONS.glob("*.tif"))
    assert tiles, f"no predictions in {config.PREDICTIONS}: run scripts/predict.py"
    config.PREDICTION_FIGURES.mkdir(parents=True, exist_ok=True)
    for i, tile in enumerate(tiles, 1):
        dst = config.PREDICTION_FIGURES / tile.replace(".tif", ".png")
        plot_tile(tile).savefig(dst, dpi=DPI, facecolor=SURFACE)
        print(f"plot  {i:>3}/{len(tiles)}  {dst.relative_to(config.ROOT)}", flush=True)
