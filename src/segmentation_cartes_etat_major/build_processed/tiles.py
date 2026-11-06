"""Web map tiles of the labels and the scans (data/processed/web/tiles/).

Each layer is an XYZ pyramid in Web Mercator, zooms config.WEB_MIN_ZOOM to WEB_MAX_ZOOM,
cut by `gdal raster tile` (GDAL >= 3.11 command line) from a mosaic VRT:

    labels  8-bit grayscale PNG, pixel value = class id (config.CLASSES), transparent
            where there is no label. Nearest at the max zoom and mode below, so every
            pixel stays a class; the dashboards colour them.
    scans   lossy WebP, quality 85, transparent off the scan tiles. Cubic at the max
            zoom, average below.

Tiles holding no data are not written: `--skip-blank` reads that from the alpha band,
so both layers keep one (the label VRT's nodata 0 becomes it). A layer is finished once
its `.done` marker exists; an interrupted layer resumes, only the missing tiles are cut.
"""

import shutil
import subprocess
from pathlib import Path

from segmentation_cartes_etat_major import config
from segmentation_cartes_etat_major.writers import write_vrt

LAYERS = {  # name: (tile format, extension, gdal raster tile options)
    "labels": (
        "PNG",
        "png",
        ["-r", "nearest", "--overview-resampling", "mode"],
    ),
    "scans": (
        "WEBP",
        "webp",
        ["-r", "cubic", "--overview-resampling", "average", "--co", "QUALITY=85"],
    ),
}


def build(layer: str, threads: int, force: bool) -> None:
    out = config.WEB_TILES / layer
    if is_done(layer) and not force:
        print(f"{layer} tiles  done, skipped", flush=True)
        return
    if force:
        shutil.rmtree(out, ignore_errors=True)
    gdal = shutil.which("gdal")
    assert gdal, "`gdal raster tile` not found: install the GDAL >= 3.11 command line"

    tile_format, _, options = LAYERS[layer]
    resume = out.exists()
    out.parent.mkdir(parents=True, exist_ok=True)
    print(
        f"{layer} tiles  z{config.WEB_MIN_ZOOM}-{config.WEB_MAX_ZOOM}"
        f"{' (resuming)' if resume else ''} -> {out}",
        flush=True,
    )
    cmd = [
        gdal, "raster", "tile", str(_source(layer)), str(out),
        "-f", tile_format,
        "--min-zoom", str(config.WEB_MIN_ZOOM),
        "--max-zoom", str(config.WEB_MAX_ZOOM),
        "--skip-blank",
        "--webviewer", "none",
        "-j", str(threads),
        *options,
    ]  # fmt: skip
    if resume:
        cmd.append("--resume")
    subprocess.run(cmd, check=True)
    (out / ".done").touch()


def is_done(layer: str) -> bool:
    return (config.WEB_TILES / layer / ".done").exists()


def version(layer: str) -> int:
    """When the layer was finished, in Unix seconds: changes on every rebuild, so the
    dashboards can cache its tiles for good."""
    return int((config.WEB_TILES / layer / ".done").stat().st_mtime)


def url(layer: str) -> str:
    """URL template of the layer's tiles, relative to config.WEB."""
    ext = LAYERS[layer][1]
    path = (config.WEB_TILES / layer).relative_to(config.WEB).as_posix()
    return f"{path}/{{z}}/{{x}}/{{y}}.{ext}"


def _source(layer: str) -> Path:
    """The mosaic VRT the layer is cut from, (re)written: it takes a few seconds."""
    if layer == "labels":
        tifs = sorted(config.LABEL_TILES.glob("SCEM40K_*.tif"))
        assert tifs, (
            f"no label tiles in {config.LABEL_TILES}: build data/interim/ first"
        )
        write_vrt(tifs, config.LABEL_IDS_VRT, colours=False)
        return config.LABEL_IDS_VRT
    tifs = sorted(config.SCANS.glob("SCEM40K_*.tif"))
    assert tifs, f"no scan tiles in {config.SCANS}: build data/raw/ first"
    write_vrt(tifs, config.SCANS_ALPHA_VRT, alpha=True)
    return config.SCANS_ALPHA_VRT
