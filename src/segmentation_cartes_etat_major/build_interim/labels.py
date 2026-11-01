"""Rasterize the BD CARTO® État-major land cover onto the scan tiles (data/interim/).

For every scan tile in data/raw/scan_em40k/, write a uint8 class raster with the same
name, grid and extent to data/interim/labels/: pixel (i, j) of a label tile is pixel
(i, j) of its scan. A pixel holds the class (config.CLASSES) of the `ocs_ancien` polygon
covering its centre, 0 = no label (outside the 16 départements). `ocs_ancien` is a
partition (buildings are holes in the polygons around them), so every labelled pixel
gets exactly one class.

Also writes the mosaic labels.vrt and classes.csv, which compares the rasterized area of
each class with the area of its polygons.

Each tile is written to a `.part` file then renamed, so an interrupted build resumes.
"""

from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import rasterio.features
import rasterio.shutil
from rasterio.io import MemoryFile

from segmentation_cartes_etat_major import config
from segmentation_cartes_etat_major.writers import write_vrt

COG = {
    "COMPRESS": "DEFLATE",
    "BLOCKSIZE": 512,
    "OVERVIEWS": "AUTO",
    "RESAMPLING": "MODE",
}
N_CLASSES = len(config.CLASSES)
CLASS_OF_LEVEL1 = {
    level1: cid for cid, (_, levels, _) in config.CLASSES.items() for level1 in levels
}
COLORMAP = {0: (0, 0, 0, 0)} | {
    cid: (*bytes.fromhex(colour[1:]), 255)
    for cid, (_, _, colour) in config.CLASSES.items()
}


def theme_class(theme: str) -> int:
    """Class id of a `theme` code, from its first EM code: EM7.1EM6.2 -> EM7."""
    return CLASS_OF_LEVEL1[int(theme.removeprefix("EM").split(".")[0])]


def build(workers: int) -> None:
    scans = sorted(config.SCANS.glob("SCEM40K_*.tif"))
    assert scans, f"no scan tiles in {config.SCANS}: build data/raw/ first"
    config.LABEL_TILES.mkdir(parents=True, exist_ok=True)

    pixels = np.zeros(N_CLASSES + 1, dtype=np.int64)
    with ProcessPoolExecutor(workers) as pool:
        for i, (name, counts) in enumerate(pool.map(_label_tile, scans), 1):
            pixels += counts
            print(f"labels  {i:>3}/{len(scans)}  {name}", flush=True)

    write_vrt(sorted(config.LABEL_TILES.glob("SCEM40K_*.tif")), config.LABEL_TILES_VRT)
    with rasterio.open(scans[0]) as d:
        pixel_km2 = abs(d.res[0] * d.res[1]) / 1e6
    _write_class_table(pixels, pixel_km2)


def _label_tile(scan: Path) -> tuple[str, np.ndarray]:
    dst = config.LABEL_TILES / scan.name
    if not dst.exists():
        with rasterio.open(scan) as src:
            profile = {
                "width": src.width,
                "height": src.height,
                "crs": src.crs,
                "transform": src.transform,
            }
            bounds = tuple(src.bounds)
        ocs = gpd.read_parquet(
            config.LABELS / "ocs_ancien.parquet",
            columns=["theme", "geometry"],
            bbox=bounds,
        )
        labels = np.zeros((profile["height"], profile["width"]), dtype=np.uint8)
        if len(ocs):
            rasterio.features.rasterize(
                zip(ocs.geometry, ocs.theme.map(theme_class)),
                out=labels,
                transform=profile["transform"],
            )
        _write_cog(labels, profile, dst)
    with rasterio.open(dst) as d:
        counts = np.bincount(d.read(1).ravel(), minlength=N_CLASSES + 1)
    return scan.name, counts


def _write_cog(labels: np.ndarray, profile: dict, dst: Path) -> None:
    part = dst.with_name(dst.name + ".part")
    with MemoryFile() as mem:
        with mem.open(
            driver="GTiff", count=1, dtype="uint8", nodata=0, **profile
        ) as tmp:
            tmp.write(labels, 1)
            tmp.write_colormap(1, COLORMAP)
            tmp.set_band_description(1, "class")
        with mem.open() as tmp:
            rasterio.shutil.copy(tmp, part, driver="COG", **COG)
    part.rename(dst)


def _write_class_table(pixels: np.ndarray, pixel_km2: float) -> None:
    ocs = gpd.read_parquet(
        config.LABELS / "ocs_ancien.parquet", columns=["theme", "geometry"]
    )
    vector_km2 = (ocs.area / 1e6).groupby(ocs.theme.map(theme_class)).sum()

    table = pd.DataFrame(
        [{"id": 0, "name": "no_label", "em_codes": ""}]
        + [
            {"id": cid, "name": name, "em_codes": " ".join(f"EM{n}" for n in levels)}
            for cid, (name, levels, _) in config.CLASSES.items()
        ]
    )
    table["pixels"] = pixels
    table["km2"] = (pixels * pixel_km2).round(1)
    table["pct_of_labelled"] = (100 * pixels / pixels[1:].sum()).round(2)
    table.loc[0, "pct_of_labelled"] = None
    table["vector_km2"] = table.id.map(vector_km2).round(1)
    table.to_csv(config.CLASS_TABLE, index=False)
    print(table.to_string(index=False))
