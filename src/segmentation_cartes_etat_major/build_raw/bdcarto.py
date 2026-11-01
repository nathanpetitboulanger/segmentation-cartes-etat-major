"""BD CARTO® État-major layers -> one GeoParquet per layer in data/raw/bdcarto_em/.

Rows are put in Hilbert order so that nearby features share row groups.
"""

from pathlib import Path

import numpy as np
import pyogrio

from segmentation_cartes_etat_major import config
from segmentation_cartes_etat_major.writers import write_geoparquet


def build(source: Path) -> None:
    gpkg = source / "bdcarto_em_n3.gpkg"
    config.LABELS.mkdir(parents=True, exist_ok=True)
    for layer in config.LABEL_LAYERS:
        dst = config.LABELS / f"{layer}.parquet"
        if dst.exists():
            continue
        info = pyogrio.read_info(gpkg, layer=layer)
        gdf = pyogrio.read_dataframe(gpkg, layer=layer, use_arrow=True)
        assert len(gdf) == info["features"], (
            f"{layer}: read {len(gdf)} of {info['features']} features"
        )
        assert np.allclose(gdf.total_bounds, info["total_bounds"]), (
            f"{layer}: extent changed"
        )
        gdf = gdf.iloc[np.argsort(gdf.hilbert_distance())].reset_index(drop=True)
        write_geoparquet(gdf, dst)
        print(
            f"labels  {layer:28s} {len(gdf):>9,} features  {dst.stat().st_size / 1e6:7.1f} MB",
            flush=True,
        )
