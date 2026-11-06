// The map: one canvas per layer (basemap, scans, labels, tile grid) under a d3-zoom
// surface. The engine draws on animation frames from refs, so panning never re-renders
// React; React only passes settings and styles down.

import { select } from "d3-selection";
import "d3-transition";
import { zoom, zoomIdentity, type ZoomBehavior, type ZoomTransform } from "d3-zoom";
import { useEffect, useImperativeHandle, useRef, useState, type ReactNode, type Ref } from "react";
import { tileAt, type Manifest, type Tile } from "../data";
import { BASEMAPS, basemapUrl, type Basemap } from "./basemaps";
import { hoverStore } from "./hover";
import {
  centeredTransform,
  fitTransform,
  lambert93,
  metresPerPixel,
  project,
  SCALE_EXTENT,
  unproject,
  zoomOf,
} from "./mercator";
import { Readout } from "./Readout";
import { RasterLayer, type Rgba } from "./tiles";

export type GridMode = "off" | "outline" | "colour";
type Box = [number, number, number, number];

export interface LayerSettings {
  basemap: Basemap;
  scans: boolean;
  scansOpacity: number;
  labels: boolean;
  labelsOpacity: number;
  swipe: boolean;
  grid: GridMode;
}

export interface GridStyle {
  fill: (t: Tile) => string | null; // null: no value (tile without labels)
  inFilter: (t: Tile) => boolean;
  focus: string | null;
  highlight: Set<string> | null;
}

export interface MapHandle {
  flyTo(box: Box): void;
}

interface Props {
  manifest: Manifest;
  tiles: Tile[];
  settings: LayerSettings;
  palette: Rgba[];
  grid: GridStyle;
  theme: string;
  onSelectTile: (name: string | null) => void;
  children?: ReactNode;
  ref?: Ref<MapHandle>;
}

export function MapView(props: Props) {
  const { manifest, settings, palette, theme, ref } = props;
  const wrap = useRef<HTMLDivElement>(null);
  const surface = useRef<HTMLDivElement>(null);
  const canvases = {
    base: useRef<HTMLCanvasElement>(null),
    scans: useRef<HTMLCanvasElement>(null),
    labels: useRef<HTMLCanvasElement>(null),
    grid: useRef<HTMLCanvasElement>(null),
  };
  const scaleBar = useRef<HTMLDivElement>(null);
  const scaleLabel = useRef<HTMLSpanElement>(null);
  const loading = useRef<HTMLDivElement>(null);
  const zoomer = useRef<ZoomBehavior<HTMLDivElement, unknown>>(null);
  // a ref, not useMemo: hot reload re-runs memos, and two engines would share the canvases
  const engineRef = useRef<Engine>(null);
  engineRef.current ??= new Engine();
  const engine = engineRef.current;
  engine.props = props;
  const [swipeX, setSwipeX] = useState(0.5);

  // canvases and overlays, once mounted
  useEffect(() => {
    engine.canvases = {
      base: canvases.base.current!,
      scans: canvases.scans.current!,
      labels: canvases.labels.current!,
      grid: canvases.grid.current!,
    };
    engine.overlays = { scaleBar: scaleBar.current!, scaleLabel: scaleLabel.current!, loading: loading.current! };
  }, []);

  // data layers
  useEffect(() => {
    const make = (name: "scans" | "labels") => {
      const info = manifest.layers[name];
      if (!info) return null;
      return new RasterLayer({
        url: (z, x, y) =>
          `/data/${info.url.replace("{z}", `${z}`).replace("{x}", `${x}`).replace("{y}", `${y}`)}?v=${info.version}`,
        minZoom: info.min_zoom,
        maxZoom: info.max_zoom,
        classes: name === "labels",
        onChange: engine.schedule,
      });
    };
    engine.layers.scans = make("scans");
    engine.layers.labels = make("labels");
    engine.layers.labels?.setPalette(engine.props.palette);
    engine.schedule();
    return () => {
      engine.layers.scans?.dispose();
      engine.layers.labels?.dispose();
    };
  }, [manifest, engine]);

  useEffect(() => {
    if (settings.basemap === "none") return;
    const layer = new RasterLayer({
      url: basemapUrl(settings.basemap),
      minZoom: 0,
      maxZoom: BASEMAPS[settings.basemap].maxZoom,
      onChange: engine.schedule,
    });
    engine.layers.base = layer;
    engine.schedule();
    return () => {
      layer.dispose();
      if (engine.layers.base === layer) engine.layers.base = null;
    };
  }, [settings.basemap, engine]);

  useEffect(() => {
    engine.layers.labels?.setPalette(palette);
    engine.schedule();
  }, [palette, engine]);

  useEffect(() => {
    engine.colours = readColours();
    engine.schedule();
  }, [theme, engine]);

  useEffect(() => engine.schedule()); // grid styles, settings: redraw after every render

  // size and zoom
  useEffect(() => {
    const el = wrap.current!;
    const resize = () => {
      const r = el.getBoundingClientRect();
      engine.resize(r.width, r.height, window.devicePixelRatio || 1);
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(el);

    const z = zoom<HTMLDivElement, unknown>()
      .scaleExtent(SCALE_EXTENT)
      .translateExtent([
        [0, 0],
        [1, 1],
      ])
      .on("zoom", (e: { transform: ZoomTransform }) => {
        engine.t = e.transform;
        engine.schedule();
      });
    zoomer.current = z;
    const sel = select(surface.current!).call(z);
    const [w, s, e, n] = engine.props.manifest.bounds;
    const [u0, v0] = project(w, n);
    const [u1, v1] = project(e, s);
    sel.call(
      z.transform,
      initialView(engine.w, engine.h) ?? fitTransform([u0, v0, u1, v1], engine.w, engine.h, 48, 14, cardSpace(engine.w)),
    );
    return () => {
      ro.disconnect();
      sel.on(".zoom", null);
    };
  }, [engine]);

  useImperativeHandle(ref, () => ({
    flyTo(box) {
      select(surface.current!)
        .transition()
        .duration(900)
        .call(zoomer.current!.transform, fitTransform(box, engine.w, engine.h, 72, 13, cardSpace(engine.w)));
    },
  }));

  const zoomBy = (f: number) => select(surface.current!).transition().duration(250).call(zoomer.current!.scaleBy, f);
  const fitAll = () => {
    const [w, s, e, n] = manifest.bounds;
    const [u0, v0] = project(w, n);
    const [u1, v1] = project(e, s);
    select(surface.current!)
      .transition()
      .duration(900)
      .call(zoomer.current!.transform, fitTransform([u0, v0, u1, v1], engine.w, engine.h, 48, 14, cardSpace(engine.w)));
  };

  const pointer = (ev: React.PointerEvent) => {
    if (ev.buttons) return;
    const r = wrap.current!.getBoundingClientRect();
    const [u, v] = engine.t.invert([ev.clientX - r.left, ev.clientY - r.top]);
    const [lon, lat] = unproject(u, v);
    const [x93, y93] = lambert93(lon, lat);
    const tile = tileAt(engine.props.tiles, u, v);
    const classId = engine.layers.labels?.classAt(u, v) ?? null;
    if (tile !== engine.hoverTile) {
      engine.hoverTile = tile;
      engine.schedule();
    }
    hoverStore.set({ lon, lat, x93, y93, tile, classId });
  };
  const leave = () => {
    engine.hoverTile = null;
    engine.schedule();
    hoverStore.set(null);
  };
  const click = (ev: React.MouseEvent) => {
    const r = wrap.current!.getBoundingClientRect();
    const [u, v] = engine.t.invert([ev.clientX - r.left, ev.clientY - r.top]);
    props.onSelectTile(tileAt(engine.props.tiles, u, v)?.name ?? null);
  };

  const swipe = settings.swipe && settings.labels;
  const dragSwipe = (ev: React.PointerEvent<HTMLDivElement>) => {
    if (ev.type === "pointerdown") ev.currentTarget.setPointerCapture(ev.pointerId);
    else if (!ev.currentTarget.hasPointerCapture(ev.pointerId)) return;
    const r = wrap.current!.getBoundingClientRect();
    setSwipeX(Math.min(0.98, Math.max(0.02, (ev.clientX - r.left) / r.width)));
  };

  return (
    <div className="map" ref={wrap}>
      <canvas ref={canvases.base} className={`layer basemap basemap-${settings.basemap}`} />
      <canvas ref={canvases.scans} className="layer" style={{ opacity: settings.scansOpacity }} />
      <canvas
        ref={canvases.labels}
        className="layer"
        style={{
          opacity: settings.labelsOpacity,
          clipPath: swipe ? `inset(0 0 0 ${swipeX * 100}%)` : undefined,
        }}
      />
      <canvas ref={canvases.grid} className="layer" />
      <div
        ref={surface}
        className="map-surface"
        onPointerMove={pointer}
        onPointerLeave={leave}
        onClick={click}
        aria-label="Map: drag to pan, scroll or pinch to zoom, click a scan tile to select it"
        role="application"
      />

      {swipe && (
        <div className="swipe" style={{ left: `${swipeX * 100}%` }}>
          <div
            className="swipe-knob"
            role="slider"
            aria-label="Swipe: labels to the right"
            aria-valuenow={Math.round(swipeX * 100)}
            aria-valuemin={0}
            aria-valuemax={100}
            tabIndex={0}
            onPointerDown={dragSwipe}
            onPointerMove={dragSwipe}
            onKeyDown={(e) => {
              if (e.key === "ArrowLeft") setSwipeX((x) => Math.max(0.02, x - 0.02));
              if (e.key === "ArrowRight") setSwipeX((x) => Math.min(0.98, x + 0.02));
            }}
          >
            <span>scan</span>
            <span>labels</span>
          </div>
        </div>
      )}

      <div className="map-controls">
        <button type="button" onClick={() => zoomBy(2)} aria-label="Zoom in">
          +
        </button>
        <button type="button" onClick={() => zoomBy(0.5)} aria-label="Zoom out">
          −
        </button>
        <button type="button" onClick={fitAll} aria-label="Show all tiles" title="Show all tiles">
          ⤢
        </button>
        <div ref={loading} className="loading" aria-live="polite" />
      </div>

      {props.children}

      <Readout classes={manifest.classes} />
      <div className="map-footer">
        <div className="scale">
          <div ref={scaleBar} className="scale-bar" />
          <span ref={scaleLabel} />
        </div>
        <div className="attribution">
          Scans & labels © IGN, SCAN État-major 40K · BD CARTO® État-major
          {settings.basemap !== "none" && " · basemap © IGN Géoplateforme"}
        </div>
      </div>
    </div>
  );
}

/** Imperative drawing state, read on every animation frame. */
class Engine {
  props!: Props;
  t: ZoomTransform = zoomIdentity;
  w = 0;
  h = 0;
  dpr = 1;
  hoverTile: Tile | null = null;
  colours = readColours();
  layers: { base: RasterLayer | null; scans: RasterLayer | null; labels: RasterLayer | null } = {
    base: null,
    scans: null,
    labels: null,
  };
  canvases: Record<"base" | "scans" | "labels" | "grid", HTMLCanvasElement> | null = null;
  overlays: { scaleBar: HTMLDivElement; scaleLabel: HTMLSpanElement; loading: HTMLDivElement } | null = null;
  private raf = 0;
  private hashTimer = 0;

  schedule = () => {
    if (this.raf) return;
    this.raf = requestAnimationFrame(() => {
      this.raf = 0;
      this.draw();
    });
  };

  resize(w: number, h: number, dpr: number) {
    this.w = w;
    this.h = h;
    this.dpr = dpr;
    for (const c of Object.values(this.canvases ?? {})) {
      c.width = Math.round(w * dpr);
      c.height = Math.round(h * dpr);
    }
    this.schedule();
  }

  private draw() {
    if (!this.canvases || !this.props) return;
    const { settings } = this.props;
    const run = (layer: RasterLayer | null, canvas: HTMLCanvasElement, on: boolean) => {
      const ctx = canvas.getContext("2d")!;
      if (on && layer) layer.draw(ctx, this.t, this.w, this.h, this.dpr);
      else {
        ctx.setTransform(1, 0, 0, 1, 0, 0);
        ctx.clearRect(0, 0, canvas.width, canvas.height);
      }
    };
    run(this.layers.base, this.canvases.base, settings.basemap !== "none");
    run(this.layers.scans, this.canvases.scans, settings.scans);
    run(this.layers.labels, this.canvases.labels, settings.labels);
    this.drawGrid(this.canvases.grid.getContext("2d")!);
    this.drawOverlays();
  }

  private drawGrid(ctx: CanvasRenderingContext2D) {
    const { t, w, h, colours } = this;
    const { tiles, grid, settings } = this.props;
    ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);
    const z = zoomOf(t);
    // the choropleth gives way to the rasters as you zoom in: full up to z8, gone from z9.5
    const fillAlpha = settings.grid === "colour" ? Math.max(0, Math.min(0.85, (9.5 - z) / 1.5)) : 0;
    const outline = settings.grid !== "off";
    const path = (tile: Tile) => {
      ctx.beginPath();
      for (const [u, v] of tile.ring) ctx.lineTo(t.x + t.k * u, t.y + t.k * v);
      ctx.closePath();
    };
    const visible = tiles.filter((tile) => {
      const [u0, v0, u1, v1] = tile.bbox;
      return t.x + t.k * u1 > 0 && t.x + t.k * u0 < w && t.y + t.k * v1 > 0 && t.y + t.k * v0 < h;
    });

    if (outline) {
      for (const tile of visible) {
        const inside = grid.inFilter(tile);
        path(tile);
        if (fillAlpha > 0) {
          ctx.globalAlpha = inside ? fillAlpha : fillAlpha * 0.2;
          ctx.fillStyle = grid.fill(tile) ?? colours.noData;
          ctx.fill();
        }
        ctx.globalAlpha = inside ? 0.55 : 0.2;
        ctx.lineWidth = 1;
        ctx.strokeStyle = colours.line;
        ctx.stroke();
      }
    }
    ctx.globalAlpha = 1;
    const ring = (tile: Tile, colour: string, width: number) => {
      path(tile);
      ctx.lineWidth = width + 3;
      ctx.strokeStyle = colours.halo;
      ctx.stroke();
      ctx.lineWidth = width;
      ctx.strokeStyle = colour;
      ctx.stroke();
    };
    for (const tile of visible) if (grid.highlight?.has(tile.name)) ring(tile, colours.select, 2);
    if (this.hoverTile && outline) ring(this.hoverTile, colours.line, 1.5);
    const focus = grid.focus && visible.find((tile) => tile.name === grid.focus);
    if (focus) ring(focus, colours.select, 3);
  }

  private drawOverlays() {
    if (!this.overlays) return;
    const { t, w, h } = this;
    const [, lat] = unproject(...t.invert([w / 2, h / 2]));
    const mpp = metresPerPixel(lat, t.k);
    const max = mpp * 110;
    const pow = 10 ** Math.floor(Math.log10(max));
    const len = [5, 2, 1].map((m) => m * pow).find((l) => l <= max) ?? pow;
    this.overlays.scaleBar.style.width = `${len / mpp}px`;
    this.overlays.scaleLabel.textContent = len >= 1000 ? `${len / 1000} km` : `${len} m`;
    const pending = Object.values(this.layers).reduce((a, l) => a + (l?.pending() ?? 0), 0);
    this.overlays.loading.textContent = pending ? `Loading ${pending} tile${pending > 1 ? "s" : ""}` : "";

    clearTimeout(this.hashTimer);
    this.hashTimer = window.setTimeout(() => {
      const [lon, clat] = unproject(...t.invert([w / 2, h / 2]));
      history.replaceState(null, "", `#${zoomOf(t).toFixed(2)}/${clat.toFixed(5)}/${lon.toFixed(5)}`);
    }, 300);
  }
}

/** Width the layers card takes over the map, left out when fitting a view. */
function cardSpace(w: number): number {
  return w > 760 ? 312 : 0;
}

/** The view in the URL hash, #zoom/lat/lon, so a view can be shared or reloaded. */
function initialView(w: number, h: number) {
  const [z, lat, lon] = location.hash.slice(1).split("/").map(Number);
  if ([z, lat, lon].some((x) => !Number.isFinite(x))) return null;
  return centeredTransform(lon, lat, z, w, h);
}

function readColours() {
  const css = getComputedStyle(document.documentElement);
  const v = (name: string) => css.getPropertyValue(name).trim() || "#888";
  return {
    line: v("--map-line"),
    halo: v("--map-halo"),
    select: v("--map-select"),
    noData: v("--no-data"),
  };
}
