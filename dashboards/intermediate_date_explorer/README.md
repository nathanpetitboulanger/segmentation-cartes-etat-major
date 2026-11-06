# État-major explorer

A React + D3 map to explore `data/interim/`: the label rasters over the SCAN État-major
40K scans, the class areas of every scan tile, and modern IGN basemaps to compare with.

```sh
npm install
npm run dev        # http://localhost:5173
```

`npm run dev` first runs `uv run scripts/build_processed.py`, which builds whatever is
missing in `data/processed/web/` (web tiles of the labels and scans, per-tile class
areas, `manifest.json`) and skips what is already there. The first build of the scan
tiles takes about 30 minutes. Vite serves that folder under `/data/`, its path read
from `config.WEB`.

- **Map**: drag to pan, scroll to zoom, click a scan tile to select it. The URL keeps
  the view. Layers (top right): basemap, scans, labels, a swipe between scan and labels,
  and the tile grid coloured by the metric of the Tiles panel.
- **Département**: scopes every panel and flies the map there.
- **Land-cover classes**: share of the labelled area; click to hide a class on the map,
  Alt-click to show it alone, hover to make it stand out.
- **Scan tiles**: histogram of coverage or of a class share (its colours are the
  map's), drag on it to keep a range, and the ranked list of tiles; click one to fly to
  it.
