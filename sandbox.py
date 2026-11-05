from segmentation_cartes_etat_major.dataset import PatchDataset
from segmentation_cartes_etat_major import config


config.IGNORE_INDEX

ds = PatchDataset(tiles=["SCEM40K_0280_6780_L93_E100.tif"])

ds.__getitem__(0)[1].shape
