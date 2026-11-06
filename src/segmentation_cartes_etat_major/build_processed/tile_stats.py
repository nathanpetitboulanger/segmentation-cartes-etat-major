"""Area of every class on every scan tile (data/processed/web/tile_stats.geojson).

One feature per scan tile: its footprint in WGS84 (RFC 7946), the départements it was
downloaded for (`deps`), the km² of no_label and of each class (`<name>_km2`) and the
labelled share (`labelled_pct`). The dashboards colour, rank and select the tiles from it
without reading a raster.
"""

from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio

from segmentation_cartes_etat_major import config

NAMES = ["no_label"] + [name for name, _, _ in config.CLASSES.values()]


def build(workers: int, force: bool) -> None:
    if config.TILE_STATS.exists() and not force:
        print("tile stats  done, skipped", flush=True)
        return
    tiles = gpd.read_parquet(config.SCAN_TILES)
    paths = [config.LABEL_TILES / name for name in tiles.tile]
    with ProcessPoolExecutor(workers) as pool:
        pixels = np.stack(list(pool.map(class_pixels, paths)))
    with rasterio.open(paths[0]) as d:
        pixel_km2 = abs(d.res[0] * d.res[1]) / 1e6

    for cid, name in enumerate(NAMES):
        tiles[f"{name}_km2"] = (pixels[:, cid] * pixel_km2).round(3)
    tiles["labelled_pct"] = (100 * pixels[:, 1:].sum(1) / pixels.sum(1)).round(2)
    # 1 km vertices, so the squares of Lambert-93 bend as they should in Web Mercator
    tiles = tiles.set_geometry(tiles.geometry.segmentize(1000)).to_crs("EPSG:4326")

    config.TILE_STATS.parent.mkdir(parents=True, exist_ok=True)
    part = config.TILE_STATS.with_name(config.TILE_STATS.name + ".part")
    tiles.to_file(
        part, driver="GeoJSON", engine="pyogrio", RFC7946="YES", COORDINATE_PRECISION=6
    )
    part.rename(config.TILE_STATS)
    print(f"tile stats  {len(tiles)} tiles -> {config.TILE_STATS}", flush=True)


def class_pixels(label_tile: Path) -> np.ndarray:
    """Pixels of no_label (0) and of every class id in a label tile."""
    with rasterio.open(label_tile) as d:
        return np.bincount(d.read(1).ravel(), minlength=len(NAMES))
