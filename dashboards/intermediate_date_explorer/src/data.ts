// The files of data/processed/web/ (served under /data/) and what the panels derive from them.

import { project } from "./map/mercator";

export interface ClassInfo {
  id: number;
  name: string;
  em_codes: string[];
  colour: string;
}

export interface LayerInfo {
  url: string; // relative to /data/, with {z} {x} {y}
  min_zoom: number;
  max_zoom: number;
  version: number;
}

export interface Manifest {
  built: string;
  classes: ClassInfo[];
  no_label: number;
  layers: Partial<Record<"labels" | "scans", LayerInfo>>;
  tile_stats: string | null;
  bounds: [number, number, number, number]; // west, south, east, north
  departements: string[];
}

/** One scan tile: 20 x 20 km, 5000 x 5000 px at 4 m. */
export interface Tile {
  name: string; // SCEM40K_0660_6660_L93_E100.tif
  id: string; // 0660 6660: km of its top-left corner in Lambert-93
  deps: string[];
  km2: number[]; // by class id, 0 = no label
  total: number;
  labelled: number;
  labelledPct: number;
  ring: [number, number][]; // footprint in world coordinates (see mercator.ts)
  bbox: [number, number, number, number]; // u0, v0, u1, v1
}

/** What the tiles are coloured, ranked and filtered by: coverage, or one class's share. */
export type Metric = "labelled" | number;

export const DEPARTEMENT_NAMES: Record<string, string> = {
  "02": "Aisne",
  "03": "Allier",
  "07": "Ardèche",
  "13": "Bouches-du-Rhône",
  "15": "Cantal",
  "18": "Cher",
  "22": "Côtes-d'Armor",
  "29": "Finistère",
  "42": "Loire",
  "43": "Haute-Loire",
  "48": "Lozère",
  "56": "Morbihan",
  "59": "Nord",
  "62": "Pas-de-Calais",
  "63": "Puy-de-Dôme",
  "74": "Haute-Savoie",
};

export class MissingDataError extends Error {}

export async function loadData(): Promise<{ manifest: Manifest; tiles: Tile[] }> {
  const res = await fetch("/data/manifest.json");
  if (!res.ok) throw new MissingDataError("manifest.json not found");
  const manifest: Manifest = await res.json();
  if (!manifest.tile_stats) return { manifest, tiles: [] };
  const geojson = await (await fetch(`/data/${manifest.tile_stats}`)).json();
  const names = ["no_label", ...manifest.classes.map((c) => c.name)];
  const tiles: Tile[] = geojson.features.map((f: GeoJSONFeature) => {
    const p = f.properties;
    const km2 = names.map((n) => Number(p[`${n}_km2`] ?? 0));
    const total = km2.reduce((a, b) => a + b, 0);
    const ring = f.geometry.coordinates[0].map(([lon, lat]) => project(lon, lat));
    const us = ring.map((c) => c[0]);
    const vs = ring.map((c) => c[1]);
    const [, x, y] = String(p.tile).split("_");
    return {
      name: String(p.tile),
      id: `${x} ${y}`,
      deps: String(p.deps).split(/\s+/).filter(Boolean),
      km2,
      total,
      labelled: total - km2[0],
      labelledPct: Number(p.labelled_pct),
      ring,
      bbox: [Math.min(...us), Math.min(...vs), Math.max(...us), Math.max(...vs)],
    } satisfies Tile;
  });
  return { manifest, tiles };
}

interface GeoJSONFeature {
  properties: Record<string, unknown>;
  geometry: { coordinates: [number, number][][] };
}

/** Value of `metric` on a tile, in %; null when the share is undefined (no label). */
export function metricValue(tile: Tile, metric: Metric): number | null {
  if (metric === "labelled") return tile.labelledPct;
  return tile.labelled > 0 ? (100 * tile.km2[metric]) / tile.labelled : null;
}

/** km² of no_label and of each class over `tiles`. */
export function sumKm2(tiles: Tile[], n: number): number[] {
  const out = new Array(n).fill(0);
  for (const t of tiles) for (let i = 0; i < n; i++) out[i] += t.km2[i];
  return out;
}

export function unionBbox(tiles: Tile[]): [number, number, number, number] | null {
  if (!tiles.length) return null;
  return [
    Math.min(...tiles.map((t) => t.bbox[0])),
    Math.min(...tiles.map((t) => t.bbox[1])),
    Math.max(...tiles.map((t) => t.bbox[2])),
    Math.max(...tiles.map((t) => t.bbox[3])),
  ];
}

/** The tile containing world point (u, v), if any. */
export function tileAt(tiles: Tile[], u: number, v: number): Tile | null {
  for (const t of tiles) {
    const [u0, v0, u1, v1] = t.bbox;
    if (u < u0 || u > u1 || v < v0 || v > v1) continue;
    if (insideRing(t.ring, u, v)) return t;
  }
  return null;
}

function insideRing(ring: [number, number][], u: number, v: number): boolean {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [ui, vi] = ring[i];
    const [uj, vj] = ring[j];
    if (vi > v !== vj > v && u < ((uj - ui) * (v - vi)) / (vj - vi) + ui) inside = !inside;
  }
  return inside;
}

export function className(name: string): string {
  return name.replace(/_/g, " / ").replace(/^./, (c) => c.toUpperCase());
}

export function metricLabel(metric: Metric, classes: ClassInfo[]): string {
  if (metric === "labelled") return "Labelled coverage";
  const c = classes.find((k) => k.id === metric);
  return `${c ? className(c.name) : "Class"} share`;
}
