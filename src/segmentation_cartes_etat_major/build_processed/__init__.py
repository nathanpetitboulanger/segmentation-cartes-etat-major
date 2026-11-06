"""Build data/processed/ from data/raw/ and data/interim/, for the dashboards.

    tiles.py       web map tiles of the labels and the scans
    tile_stats.py  area of every class on every scan tile

Then writes manifest.json, the index the dashboards read: the classes, the finished tile
layers and the stats file. Finished steps are skipped, so the build is cheap to rerun.
"""

import json
from datetime import UTC, datetime

import geopandas as gpd

from segmentation_cartes_etat_major import config
from segmentation_cartes_etat_major.build_processed import tile_stats, tiles

STEPS = ("labels", "scans", "stats")


def build(steps: tuple[str, ...], workers: int, threads: int, force: bool) -> None:
    config.WEB.mkdir(parents=True, exist_ok=True)
    for layer in tiles.LAYERS:
        if layer in steps:
            tiles.build(layer, threads, force)
    if "stats" in steps:
        tile_stats.build(workers, force)
    write_manifest()


def write_manifest() -> None:
    """manifest.json, listing only what is finished. Written to `.part` then renamed."""
    west, south, east, north = (
        gpd.read_parquet(config.SCAN_TILES).to_crs("EPSG:4326").total_bounds
    )
    manifest = {
        "built": datetime.now(UTC).isoformat(timespec="seconds"),
        "classes": [
            {
                "id": cid,
                "name": name,
                "em_codes": [f"EM{n}" for n in levels],
                "colour": colour,
            }
            for cid, (name, levels, colour) in config.CLASSES.items()
        ],
        "no_label": 0,
        "layers": {
            layer: {
                "url": tiles.url(layer),
                "min_zoom": config.WEB_MIN_ZOOM,
                "max_zoom": config.WEB_MAX_ZOOM,
                "version": tiles.version(layer),
            }
            for layer in tiles.LAYERS
            if tiles.is_done(layer)
        },
        "tile_stats": (
            config.TILE_STATS.relative_to(config.WEB).as_posix()
            if config.TILE_STATS.exists()
            else None
        ),
        "bounds": [round(v, 5) for v in (west, south, east, north)],
        "departements": list(config.DEPARTEMENTS),
    }
    part = config.WEB_MANIFEST.with_name(config.WEB_MANIFEST.name + ".part")
    part.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    part.rename(config.WEB_MANIFEST)
    print(f"manifest  layers {', '.join(manifest['layers']) or 'none'}", flush=True)
