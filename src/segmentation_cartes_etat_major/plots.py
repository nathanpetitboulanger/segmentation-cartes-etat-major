"""Figures of the trained U-Net's results, for reports.

plot_predictions  one PNG per predicted tile (predict.py) in config.PREDICTION_FIGURES,
                  four panels: the scan, the labels (BD CARTO), the prediction, and where
                  the last two disagree. The rasters are read at PANEL_PX px a side from
                  their COG overviews (those of the class rasters keep the majority
                  class), so a figure stays small; the agreement and mIoU in its title
                  are computed at full resolution.
plot_confusion    the confusion matrix of the test tiles (evaluate.py's config.SCORES),
                  each row in % of its true class, to config.CONFUSION_FIGURE.
"""

import json

import numpy as np
import rasterio
import torch
from matplotlib.colors import LinearSegmentedColormap, PowerNorm
from matplotlib.figure import Figure
from matplotlib.patches import Patch
from rasterio.enums import Resampling

from segmentation_cartes_etat_major import config, metrics

PANEL_PX = 600  # px a side of each panel, about its size in the saved figure
DPI = 120
SURFACE, INK, INK_2 = "#fcfcfb", "#0b0b0b", "#52514e"  # figure, text, secondary text
SAME, DIFFERENT = "#d9d9d4", "#d03b3b"  # disagreement panel: recessive grey, red
NO_LABEL = SURFACE
# sequential blue, light -> dark, for the confusion matrix
BLUES = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]


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


def confusion_figure() -> Figure:
    """The confusion matrix of config.SCORES, each row in % of its true class's pixels,
    with the IoU of each class beside its row."""
    scores = json.loads(config.SCORES.read_text())
    names = list(scores["classes"])
    n = len(names)
    cm = np.array(scores["confusion_matrix"], dtype=float)
    with np.errstate(invalid="ignore", divide="ignore"):
        share = 100 * cm / cm.sum(axis=1, keepdims=True)
    # cells under 0.05 % (or of a class absent from the tiles) are left blank
    shown = np.ma.masked_where(~(share >= 0.05), share)
    blank = np.ma.getmaskarray(shown)
    cmap = LinearSegmentedColormap.from_list("blues", BLUES)
    cmap.set_bad(SURFACE)
    norm = PowerNorm(0.5, vmin=0, vmax=100)  # spreads the small, off-diagonal shares

    fig = Figure(figsize=(8.6, 8), facecolor=SURFACE)
    ax = fig.add_axes((0.2, 0.17, 0.58, 0.62))
    mesh = ax.pcolormesh(shown, cmap=cmap, norm=norm, edgecolors=SURFACE, linewidth=2)
    ax.set_xlim(0, n)
    ax.set_ylim(n, 0)  # first class on top
    ax.set_aspect("equal")
    for i in range(n):
        for j in range(n):
            if blank[i, j]:
                continue
            r, g, b, _ = cmap(norm(share[i, j]))
            on_dark = 0.2126 * r + 0.7152 * g + 0.0722 * b < 0.5
            ax.text(
                j + 0.5,
                i + 0.5,
                f"{share[i, j]:.0f}" if share[i, j] >= 10 else f"{share[i, j]:.1f}",
                ha="center",
                va="center",
                fontsize=9,
                color="white" if on_dark else INK,
            )

    ticks = np.arange(n) + 0.5
    ax.set_xticks(ticks, names, rotation=35, ha="right", fontsize=9.5, color=INK)
    ax.set_yticks(ticks, names, fontsize=9.5, color=INK)
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_xlabel("Predicted class (U-Net)", fontsize=10, color=INK_2, labelpad=8)
    ax.set_ylabel("True class (BD CARTO)", fontsize=10, color=INK_2, labelpad=8)

    ax.text(n + 0.3, -0.15, "IoU", fontsize=9.5, color=INK_2, va="bottom")
    for i, name in enumerate(names):
        iou = scores["classes"][name]["iou"]
        text = "–" if iou is None else f"{iou:.2f}"
        ax.text(n + 0.3, i + 0.5, text, fontsize=9.5, color=INK, va="center")

    cax = fig.add_axes((0.89, 0.17, 0.022, 0.62))
    bar = fig.colorbar(mesh, cax=cax, ticks=[0, 5, 25, 50, 100])
    bar.outline.set_visible(False)
    bar.ax.tick_params(labelsize=8.5, colors=INK_2, length=0)
    bar.set_label("% of the true class's pixels", fontsize=9, color=INK_2)

    fig.text(
        0.03,
        0.945,
        f"Confusion matrix, {len(scores['tiles'])} test tiles",
        fontsize=14,
        color=INK,
    )
    fig.text(
        0.03,
        0.91,
        "Each row splits the pixels of one true class by predicted class, in %; "
        "the diagonal is correct.",
        fontsize=9.5,
        color=INK_2,
    )
    fig.text(
        0.03,
        0.885,
        f"mIoU {scores['miou']:.3f}   ·   mean F1 {scores['mean_f1']:.3f}   ·   "
        f"pixel accuracy {scores['pixel_accuracy']:.3f}   ·   "
        f"weights {scores['checkpoint']}",
        fontsize=9.5,
        color=INK_2,
    )
    return fig


def plot_confusion() -> None:
    """Save the confusion matrix of config.SCORES to config.CONFUSION_FIGURE."""
    assert config.SCORES.exists(), f"no {config.SCORES}: run scripts/evaluate.py"
    config.FIGURES.mkdir(parents=True, exist_ok=True)
    confusion_figure().savefig(config.CONFUSION_FIGURE, dpi=DPI, facecolor=SURFACE)
    print(f"plot  {config.CONFUSION_FIGURE.relative_to(config.ROOT)}")
