// A raster tile layer drawn on its own canvas: XYZ tiles fetched, cached (LRU) and blitted
// at the zoom level that matches the screen's pixels. While a tile loads, a cached
// ancestor (zooming in) or its children (zooming out) stand in, so the map never blanks.
//
// A class layer reads its tiles as class ids (grayscale PNG, value = id) and paints them
// through a palette, so classes can be hidden or emphasised without refetching. Those PNGs
// are decoded in JS: the browser's decoder dithers, turning about 1 % of the ids into
// their neighbour (1 into 0, 3 into 2).

import type { ZoomTransform } from "d3-zoom";
import { decode } from "fast-png";
import { TILE_SIZE } from "./mercator";

export type TileUrl = (z: number, x: number, y: number) => string;
export type Rgba = [number, number, number, number];

interface Entry {
  state: "loading" | "ready" | "empty" | "error";
  image?: ImageBitmap;
  classes?: Uint8Array; // class layers: one id per pixel, row-major
  painted?: OffscreenCanvas;
  paintedVersion?: number;
  ctrl?: AbortController;
}

export interface LayerOptions {
  url: TileUrl;
  minZoom: number;
  maxZoom: number;
  classes?: boolean;
  onChange: () => void;
}

const MAX_CACHE = 600; // tiles kept, about 160 MB of bitmaps
const MAX_INFLIGHT = 8;
const FALLBACK_LEVELS = 8;
const MAX_VISIBLE = 1500; // tiles in view beyond which the layer is not drawn

export class RasterLayer {
  private cache = new Map<string, Entry>();
  private queue: [string, number, number, number][] = [];
  private inflight = 0;
  private palette = new Uint32Array(256);
  private paletteVersion = 0;
  private disposed = false;
  private lastZ = 0;

  constructor(private o: LayerOptions) {}

  /** Colour of every class id, for class layers. */
  setPalette(rgba: Rgba[]) {
    this.palette.fill(0);
    rgba.forEach(([r, g, b, a], id) => {
      this.palette[id] = ((a << 24) | (b << 16) | (g << 8) | r) >>> 0;
    });
    this.paletteVersion++;
  }

  /** Tiles waiting or loading. */
  pending(): number {
    return this.inflight + this.queue.length;
  }

  dispose() {
    this.disposed = true;
    for (const e of this.cache.values()) {
      e.ctrl?.abort();
      e.image?.close();
    }
    this.cache.clear();
    this.queue = [];
  }

  draw(ctx: CanvasRenderingContext2D, t: ZoomTransform, w: number, h: number, dpr: number) {
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height);
    const ideal = Math.round(Math.log2((t.k * dpr) / TILE_SIZE));
    const z = Math.max(this.o.minZoom, Math.min(this.o.maxZoom, ideal));
    this.lastZ = z;
    const n = 2 ** z;
    const size = t.k / n; // CSS px per tile
    const x0 = Math.max(0, Math.floor(-t.x / size));
    const x1 = Math.min(n - 1, Math.floor((w - t.x) / size));
    const y0 = Math.max(0, Math.floor(-t.y / size));
    const y1 = Math.min(n - 1, Math.floor((h - t.y) / size));
    if ((x1 - x0 + 1) * (y1 - y0 + 1) > MAX_VISIBLE) return;

    ctx.imageSmoothingEnabled = !this.o.classes;
    const cx = (w / 2 - t.x) / size;
    const cy = (h / 2 - t.y) / size;
    const visible = new Set<string>();
    const missing: [string, number, number, number, number][] = [];
    for (let y = y0; y <= y1; y++) {
      for (let x = x0; x <= x1; x++) {
        const key = `${z}/${x}/${y}`;
        visible.add(key);
        const rect = deviceRect(t, size, x, y, dpr);
        const e = this.cache.get(key);
        if (e?.state === "ready") {
          this.cache.delete(key); // LRU: move to the end
          this.cache.set(key, e);
          this.blit(ctx, e, 0, 0, TILE_SIZE, rect);
          continue;
        }
        if (e?.state === "empty" || e?.state === "error") continue;
        if (!e) missing.push([key, z, x, y, (x + 0.5 - cx) ** 2 + (y + 0.5 - cy) ** 2]);
        this.fallback(ctx, z, x, y, rect);
      }
    }
    for (const [key, e] of this.cache) {
      if (e.state === "loading" && !visible.has(key)) e.ctrl?.abort();
    }
    missing.sort((a, b) => a[4] - b[4]);
    this.queue = missing.map(([key, tz, tx, ty]) => [key, tz, tx, ty]);
    this.pump();
  }

  /** Class id at world point (u, v) from the sharpest cached tile; null if none is. */
  classAt(u: number, v: number): number | null {
    for (let z = this.lastZ; z >= this.o.minZoom; z--) {
      const n = 2 ** z;
      const x = Math.floor(u * n);
      const y = Math.floor(v * n);
      const e = this.cache.get(`${z}/${x}/${y}`);
      if (e?.state === "empty") return 0;
      if (e?.state !== "ready" || !e.classes) continue;
      const px = Math.min(TILE_SIZE - 1, Math.floor((u * n - x) * TILE_SIZE));
      const py = Math.min(TILE_SIZE - 1, Math.floor((v * n - y) * TILE_SIZE));
      return e.classes[py * TILE_SIZE + px];
    }
    return null;
  }

  private fallback(ctx: CanvasRenderingContext2D, z: number, x: number, y: number, rect: Rect) {
    for (let dz = 1; dz <= FALLBACK_LEVELS && z - dz >= this.o.minZoom; dz++) {
      const e = this.cache.get(`${z - dz}/${x >> dz}/${y >> dz}`);
      if (e?.state === "empty") return; // no data above, none below
      if (e?.state !== "ready") continue;
      const s = TILE_SIZE / 2 ** dz;
      this.blit(ctx, e, (x - ((x >> dz) << dz)) * s, (y - ((y >> dz) << dz)) * s, s, rect);
      return;
    }
    if (z + 1 > this.o.maxZoom) return;
    const [dx, dy, dw, dh] = rect;
    for (let i = 0; i < 4; i++) {
      const e = this.cache.get(`${z + 1}/${2 * x + (i & 1)}/${2 * y + (i >> 1)}`);
      if (e?.state !== "ready") continue;
      const hx = Math.round(dw / 2);
      const hy = Math.round(dh / 2);
      const sub: Rect = [
        dx + (i & 1 ? hx : 0),
        dy + (i >> 1 ? hy : 0),
        i & 1 ? dw - hx : hx,
        i >> 1 ? dh - hy : hy,
      ];
      this.blit(ctx, e, 0, 0, TILE_SIZE, sub);
    }
  }

  private blit(ctx: CanvasRenderingContext2D, e: Entry, sx: number, sy: number, s: number, rect: Rect) {
    const src = this.o.classes ? this.paint(e) : e.image;
    if (src) ctx.drawImage(src, sx, sy, s, s, rect[0], rect[1], rect[2], rect[3]);
  }

  private paint(e: Entry): OffscreenCanvas | undefined {
    if (!e.classes) return undefined;
    if (e.paintedVersion !== this.paletteVersion) {
      e.painted ??= new OffscreenCanvas(TILE_SIZE, TILE_SIZE);
      const ctx = e.painted.getContext("2d")!;
      const img = ctx.createImageData(TILE_SIZE, TILE_SIZE);
      const out = new Uint32Array(img.data.buffer);
      const { classes } = e;
      for (let i = 0; i < classes.length; i++) out[i] = this.palette[classes[i]];
      ctx.putImageData(img, 0, 0);
      e.paintedVersion = this.paletteVersion;
    }
    return e.painted;
  }

  private pump() {
    while (!this.disposed && this.inflight < MAX_INFLIGHT && this.queue.length) {
      const [key, z, x, y] = this.queue.shift()!;
      if (!this.cache.has(key)) void this.load(key, z, x, y);
    }
  }

  private async load(key: string, z: number, x: number, y: number) {
    const e: Entry = { state: "loading", ctrl: new AbortController() };
    this.cache.set(key, e);
    this.inflight++;
    try {
      const res = await fetch(this.o.url(z, x, y), { signal: e.ctrl!.signal });
      if (res.status === 204 || res.status === 404) {
        e.state = "empty";
      } else if (!res.ok) {
        e.state = "error";
      } else if (this.o.classes) {
        e.classes = readClasses(new Uint8Array(await res.arrayBuffer()));
        e.state = "ready";
      } else {
        e.image = await createImageBitmap(await res.blob());
        e.state = "ready";
      }
    } catch {
      e.state = "error";
      // aborted because it scrolled out of view: forget it, so it is refetched if needed
      if (e.ctrl?.signal.aborted && this.cache.get(key) === e) this.cache.delete(key);
    } finally {
      e.ctrl = undefined;
      this.inflight--;
      this.evict();
      this.pump();
      if (!this.disposed) this.o.onChange();
    }
  }

  private evict() {
    if (this.cache.size <= MAX_CACHE) return;
    for (const [key, e] of this.cache) {
      if (this.cache.size <= MAX_CACHE) break;
      if (e.state === "loading") continue;
      e.image?.close();
      this.cache.delete(key);
    }
  }
}

type Rect = [number, number, number, number]; // device px: x, y, w, h

/** Tile (x, y) in device pixels, snapped so neighbours meet without seams. */
function deviceRect(t: ZoomTransform, size: number, x: number, y: number, dpr: number): Rect {
  const left = Math.round((t.x + x * size) * dpr);
  const top = Math.round((t.y + y * size) * dpr);
  return [
    left,
    top,
    Math.round((t.x + (x + 1) * size) * dpr) - left,
    Math.round((t.y + (y + 1) * size) * dpr) - top,
  ];
}

/** Class ids of an 8-bit gray PNG tile, with or without alpha; transparent = 0. */
function readClasses(png: Uint8Array): Uint8Array {
  const { data, channels, width, height } = decode(png);
  if (width !== TILE_SIZE || height !== TILE_SIZE) throw new Error(`tile is ${width} x ${height} px`);
  const ids = new Uint8Array(TILE_SIZE * TILE_SIZE);
  const alpha = channels === 2 || channels === 4;
  for (let i = 0; i < ids.length; i++) {
    ids[i] = alpha && data[i * channels + channels - 1] === 0 ? 0 : data[i * channels];
  }
  return ids;
}
