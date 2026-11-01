"""SCAN État-major® 40K tiles -> COG, lossless WebP, in data/raw/scan_em40k/.

Every converted tile is read back and compared pixel for pixel with its source. Also
writes the tile index scan_em40k_tiles.parquet and the mosaic scan_em40k.vrt.
"""

from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
import rasterio.shutil

from segmentation_cartes_etat_major import config
from segmentation_cartes_etat_major.writers import write_geoparquet, write_vrt

COG = {
    "COMPRESS": "WEBP",
    "QUALITY": 100,
    "BLOCKSIZE": 512,
    "OVERVIEWS": "AUTO",
}  # QUALITY=100 is lossless


def build(source: Path, workers: int) -> None:
    tiles = gpd.read_file(source / "scan_em40k_tiles.gpkg", layer="tiles")
    srcs = sorted((source / "scan_em40k").glob("SCEM40K_*.tif"))
    assert {p.name for p in srcs} == set(tiles["tile"]), (
        "tile files and tile index disagree"
    )

    config.SCANS.mkdir(parents=True, exist_ok=True)
    todo = [p for p in srcs if not (config.SCANS / p.name).exists()]
    print(
        f"scans   {len(srcs) - len(todo)} of {len(srcs)} tiles already built, converting {len(todo)}",
        flush=True,
    )
    with ProcessPoolExecutor(workers) as pool:
        for i, name in enumerate(pool.map(_convert_tile, todo), 1):
            print(f"scans   {i:>3}/{len(todo)}  {name}", flush=True)

    dsts = sorted(config.SCANS.glob("SCEM40K_*.tif"))
    assert len(dsts) == len(srcs), (
        f"expected {len(srcs)} tiles in {config.SCANS}, found {len(dsts)}"
    )
    tiles = gpd.GeoDataFrame(tiles.sort_values("tile", ignore_index=True))
    write_geoparquet(tiles, config.SCAN_TILES)
    write_vrt(dsts, config.SCANS_VRT)


def _convert_tile(src: Path) -> str:
    dst = config.SCANS / src.name
    part = dst.with_name(dst.name + ".part")
    with rasterio.Env(GDAL_NUM_THREADS=1, GDAL_CACHEMAX=512):
        rasterio.shutil.copy(src, part, driver="COG", **COG)
        with rasterio.open(src) as a, rasterio.open(part) as b:
            same = (a.crs, a.transform, a.colorinterp) == (
                b.crs,
                b.transform,
                b.colorinterp,
            )
            if not (same and np.array_equal(a.read(), b.read())):
                raise ValueError(
                    f"{src.name}: the conversion changed the pixels or the georeferencing"
                )
    part.rename(dst)
    return src.name
