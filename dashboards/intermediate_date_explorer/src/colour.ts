// Colours that carry data: the class palette of the label tiles, and the sequential ramp
// of the tile choropleth (one hue, light = low, five steps so each reads as a bin).

import { scaleLinear, scaleQuantize } from "d3-scale";
import { metricValue, type ClassInfo, type Metric, type Tile } from "./data";
import type { Rgba } from "./map/tiles";

export const RAMP = ["#b7d3f6", "#86b6ef", "#5598e7", "#256abf", "#104281"];

/** Metric axis: 0-100 % for coverage, 0 to a round max for a class share. Computed over
 * every tile so a tile keeps its colour whatever the scope. */
export function metricDomain(tiles: Tile[], metric: Metric): [number, number] {
  if (metric === "labelled") return [0, 100];
  const max = Math.max(1, ...tiles.map((t) => metricValue(t, metric) ?? 0));
  const [, hi] = scaleLinear().domain([0, Math.min(100, max)]).nice(10).domain();
  return [0, Math.min(100, hi)];
}

export function metricColour(domain: [number, number]) {
  return scaleQuantize<string>().domain(domain).range(RAMP);
}

export function rgb(hex: string): [number, number, number] {
  const n = parseInt(hex.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

/** Colour of every class id in the label tiles: hidden classes are transparent, and while
 * one class is emphasised the others fade. */
export function classPalette(classes: ClassInfo[], hidden: Set<number>, emphasis: number | null): Rgba[] {
  const out: Rgba[] = [[0, 0, 0, 0]];
  for (const c of classes) {
    const alpha = hidden.has(c.id) ? 0 : emphasis !== null && emphasis !== c.id ? 40 : 255;
    out[c.id] = [...rgb(c.colour), alpha];
  }
  return out;
}
