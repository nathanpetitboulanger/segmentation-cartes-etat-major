import { useEffect, useMemo, useRef, useState } from "react";
import { classPalette, metricColour, metricDomain } from "./colour";
import {
  loadData,
  metricValue,
  MissingDataError,
  sumKm2,
  unionBbox,
  type Manifest,
  type Metric,
  type Tile,
} from "./data";
import { MapView, type GridStyle, type LayerSettings, type MapHandle } from "./map/MapView";
import { ClassPanel } from "./panels/ClassPanel";
import { LayersCard } from "./panels/LayersCard";
import { ScopePanel } from "./panels/ScopePanel";
import { TilePanel } from "./panels/TilePanel";
import { useStored, useTheme } from "./state";

const DEFAULT_LAYERS: LayerSettings = {
  basemap: "plan",
  scans: true,
  scansOpacity: 1,
  labels: true,
  labelsOpacity: 0.65,
  swipe: false,
  grid: "colour",
};

export function App() {
  const [data, setData] = useState<{ manifest: Manifest; tiles: Tile[] } | null>(null);
  const [error, setError] = useState<Error | null>(null);
  useEffect(() => {
    loadData().then(setData, setError);
  }, []);

  if (error) {
    return (
      <div className="boot">
        <h1>No processed data</h1>
        {error instanceof MissingDataError ? (
          <p>
            The dashboard reads <code>data/processed/web/</code>. Build it from the repository root with{" "}
            <code>uv run scripts/build_processed.py</code>, or start the dashboard with <code>npm run dev</code>,
            which builds whatever is missing first.
          </p>
        ) : (
          <p>{error.message}</p>
        )}
      </div>
    );
  }
  if (!data) return <div className="boot">Loading tiles…</div>;
  return <Explorer manifest={data.manifest} tiles={data.tiles} />;
}

function Explorer({ manifest, tiles }: { manifest: Manifest; tiles: Tile[] }) {
  const [dep, setDep] = useState<string | null>(null);
  const [metric, setMetric] = useState<Metric>("labelled");
  const [range, setRange] = useState<[number, number] | null>(null);
  const [focus, setFocus] = useState<string | null>(null);
  const [hidden, setHidden] = useState<Set<number>>(() => new Set());
  const [emphasis, setEmphasis] = useState<number | null>(null);
  const [hoverTiles, setHoverTiles] = useState<Set<string> | null>(null);
  const [layers, setLayers] = useStored<LayerSettings>("layers", DEFAULT_LAYERS);
  const [themeChoice, setThemeChoice, theme] = useTheme();
  const map = useRef<MapHandle>(null);

  const n = manifest.classes.length + 1;
  const scoped = useMemo(() => (dep ? tiles.filter((t) => t.deps.includes(dep)) : tiles), [tiles, dep]);
  const filtered = useMemo(() => {
    if (!range) return scoped;
    return scoped.filter((t) => {
      const v = metricValue(t, metric);
      return v !== null && v >= range[0] && v <= range[1];
    });
  }, [scoped, range, metric]);
  const focusTile = focus ? (tiles.find((t) => t.name === focus) ?? null) : null;
  const km2 = useMemo(() => sumKm2(focusTile ? [focusTile] : filtered, n), [focusTile, filtered, n]);
  const globalKm2 = useMemo(() => sumKm2(tiles, n), [tiles, n]);
  const domain = useMemo(() => metricDomain(tiles, metric), [tiles, metric]);
  const colour = useMemo(() => metricColour(domain), [domain]);
  const palette = useMemo(() => classPalette(manifest.classes, hidden, emphasis), [manifest, hidden, emphasis]);
  const grid = useMemo<GridStyle>(() => {
    const inside = new Set(filtered.map((t) => t.name));
    return {
      fill: (t) => {
        const v = metricValue(t, metric);
        return v === null ? null : colour(v);
      },
      inFilter: (t) => inside.has(t.name),
      focus,
      highlight: hoverTiles,
    };
  }, [filtered, metric, colour, focus, hoverTiles]);

  const chooseDep = (d: string | null) => {
    setDep(d);
    setFocus(null);
    const box = unionBbox(d ? tiles.filter((t) => t.deps.includes(d)) : tiles);
    if (box) map.current?.flyTo(box);
  };
  const chooseMetric = (m: Metric) => {
    setMetric(m);
    setRange(null); // a range is in the units of its metric
  };
  const focusOn = (name: string | null, fly: boolean) => {
    setFocus(name);
    const t = name && tiles.find((k) => k.name === name);
    if (t && fly) map.current?.flyTo(t.bbox);
  };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setFocus(null);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <div className="app">
      <aside className="sidebar">
        <header className="masthead">
          <div>
            <h1>État-major explorer</h1>
            <p className="muted">
              Labels of <code>data/interim/</code> over the SCAN État-major 40K, {tiles.length} scan tiles
            </p>
          </div>
          <button
            type="button"
            className="ghost theme-toggle"
            onClick={() => setThemeChoice(themeChoice === "auto" ? "dark" : themeChoice === "dark" ? "light" : "auto")}
            title="Colour theme"
          >
            {themeChoice === "auto" ? "Auto" : themeChoice === "dark" ? "Dark" : "Light"}
          </button>
        </header>

        <ScopePanel
          tiles={tiles}
          departements={manifest.departements}
          dep={dep}
          onDep={chooseDep}
          range={range}
          metric={metric}
          classes={manifest.classes}
          onClearRange={() => setRange(null)}
          focus={focusTile}
          onClearFocus={() => setFocus(null)}
          onZoomFocus={() => focusTile && map.current?.flyTo(focusTile.bbox)}
          count={focusTile ? 1 : filtered.length}
          km2={km2}
        />

        <ClassPanel
          classes={manifest.classes}
          km2={km2}
          globalKm2={globalKm2}
          isSubset={!!focusTile || filtered.length !== tiles.length}
          hidden={hidden}
          onHidden={setHidden}
          onEmphasis={setEmphasis}
        />

        <TilePanel
          tiles={scoped}
          filtered={filtered}
          metric={metric}
          onMetric={chooseMetric}
          classes={manifest.classes}
          domain={domain}
          colour={colour}
          range={range}
          onRange={setRange}
          focus={focus}
          onFocus={(name) => focusOn(name, true)}
          onHoverTiles={setHoverTiles}
        />

        <footer className="muted small">
          data/processed/web/ built {new Date(manifest.built).toLocaleString()} · rebuild with{" "}
          <code>uv run scripts/build_processed.py</code>
        </footer>
      </aside>

      <main className="map-area">
        <MapView
          ref={map}
          manifest={manifest}
          tiles={tiles}
          settings={layers}
          palette={palette}
          grid={grid}
          theme={theme}
          onSelectTile={(name) => focusOn(name, false)}
        >
          <LayersCard manifest={manifest} settings={layers} onChange={setLayers} />
        </MapView>
      </main>
    </div>
  );
}
