# segmentation-cartes-etat-major

Deep-learning land-cover segmentation of the 19th-century État-major maps: IGN SCAN
État-major 40K scans in, BD CARTO® État-major land-cover classes out (8 classes, U-Net).

## The pipeline in 5 minutes

https://github.com/user-attachments/assets/5bcfd1b2-7201-4185-b3d6-6533bbc62d60

From the label rasters to the final predictions, on real data and real model outputs.
On the 38 held-out test tiles: pixel accuracy 91.7 %, mIoU 0.672, mean F1 0.769.

| Time | Chapter |
| ---- | ------- |
| 0:00 | Scan and U-Net prediction of a test tile |
| 0:27 | The data: 378 scan tiles, BD CARTO® polygons, level-3 georeferencing |
| 0:50 | From polygons to label rasters, class balance |
| 1:26 | Patches: 572 px in, 388 px out, context from neighbours or a mirror, `min_labelled` |
| 2:03 | Train / val / test split by tile |
| 2:18 | The unpadded U-Net, with its real activations |
| 2:47 | Training: loss, ignored pixels, recipe |
| 3:13 | Predicting a whole tile with sliding windows |
| 3:38 | Results: IoU, confusion matrix, test tiles, the full map |
| 4:53 | The whole pipeline, script by script |
