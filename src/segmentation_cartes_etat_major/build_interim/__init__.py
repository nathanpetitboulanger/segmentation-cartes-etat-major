"""Build data/interim/ from data/raw/.

labels.py   the land cover rasterized onto every scan tile, 8 classes
"""

from segmentation_cartes_etat_major.build_interim import labels


def build(workers: int) -> None:
    labels.build(workers)
