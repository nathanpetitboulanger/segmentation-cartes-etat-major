import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from segmentation_cartes_etat_major.build_processed import tile_stats
from segmentation_cartes_etat_major.writers import CLASS_COLORMAP, write_vrt


def _write_tif(path, data, left, top, colormap=None):
    count, height, width = data.shape
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=width,
        height=height,
        count=count,
        dtype="uint8",
        crs="EPSG:2154",
        transform=from_origin(left, top, 4, 4),
    ) as d:
        d.write(data)
        if colormap:
            d.write_colormap(1, colormap)


def test_vrt_alpha_marks_tiles_and_gaps(tmp_path):
    # two 2x2 RGB tiles with a 2 px gap between them; the VRT sits elsewhere, like
    # data/processed/ reading data/raw/
    (tmp_path / "tiles").mkdir()
    (tmp_path / "out").mkdir()
    tifs = [tmp_path / "tiles" / "a.tif", tmp_path / "tiles" / "b.tif"]
    _write_tif(tifs[0], np.full((3, 2, 2), 10, np.uint8), left=0, top=8)
    _write_tif(tifs[1], np.full((3, 2, 2), 20, np.uint8), left=16, top=8)
    vrt = tmp_path / "out" / "mosaic.vrt"
    write_vrt(tifs, vrt, alpha=True)

    with rasterio.open(vrt) as d:
        assert d.count == 4
        assert d.colorinterp[3].name == "alpha"
        rgba = d.read()
    assert rgba[:3, :, :2].tolist() == np.full((3, 2, 2), 10).tolist()
    assert rgba[3].tolist() == [[255, 255, 0, 0, 255, 255]] * 2


def test_vrt_without_colours_keeps_class_ids(tmp_path):
    tif = tmp_path / "labels.tif"
    _write_tif(tif, np.array([[[0, 1], [4, 8]]], np.uint8), 0, 8, CLASS_COLORMAP)
    vrt = tmp_path / "labels_ids.vrt"
    write_vrt([tif], vrt, colours=False)

    with rasterio.open(vrt) as d:
        assert d.colorinterp[0].name == "gray"
        assert d.read(1).tolist() == [[0, 1], [4, 8]]
        with pytest.raises(ValueError):  # no colour table
            d.colormap(1)


def test_class_pixels(tmp_path):
    tif = tmp_path / "labels.tif"
    _write_tif(tif, np.array([[[0, 0, 1], [3, 3, 8]]], np.uint8), 0, 8)
    # one count per id, no_label (0) first, ids with no pixel included
    assert tile_stats.class_pixels(tif).tolist() == [2, 1, 0, 2, 0, 0, 0, 0, 1]
