// Web Mercator "world" coordinates: u, v in [0, 1] from the top-left corner (180° W,
// 85.05° N). A d3-zoom transform maps them to screen pixels, its k being the width of the
// world in CSS pixels: zoom level z = log2(k / 256).

import proj4 from "proj4";
import { zoomIdentity, type ZoomTransform } from "d3-zoom";

export const TILE_SIZE = 256;
export const MIN_ZOOM = 4;
export const MAX_ZOOM = 19;
export const SCALE_EXTENT: [number, number] = [TILE_SIZE * 2 ** MIN_ZOOM, TILE_SIZE * 2 ** MAX_ZOOM];
const EARTH_CIRCUMFERENCE = 40075016.686;

export function project(lon: number, lat: number): [number, number] {
  const phi = (lat * Math.PI) / 180;
  return [(lon + 180) / 360, (1 - Math.log(Math.tan(phi) + 1 / Math.cos(phi)) / Math.PI) / 2];
}

export function unproject(u: number, v: number): [number, number] {
  const lat = (Math.atan(Math.sinh(Math.PI * (1 - 2 * v))) * 180) / Math.PI;
  return [u * 360 - 180, lat];
}

export function zoomOf(t: ZoomTransform): number {
  return Math.log2(t.k / TILE_SIZE);
}

/** The transform showing world box [u0, v0, u1, v1] in a w x h view, with padding and
 * `right` px kept clear on the right (where the layers card floats). */
export function fitTransform(
  box: [number, number, number, number],
  w: number,
  h: number,
  pad = 48,
  maxZoom = 14,
  right = 0,
): ZoomTransform {
  const [u0, v0, u1, v1] = box;
  const k = Math.min(
    (w - 2 * pad - right) / Math.max(u1 - u0, 1e-9),
    (h - 2 * pad) / Math.max(v1 - v0, 1e-9),
    TILE_SIZE * 2 ** maxZoom,
  );
  const kk = Math.max(SCALE_EXTENT[0], Math.min(SCALE_EXTENT[1], k));
  const cx = (w - right) / 2;
  return zoomIdentity.translate(cx - (kk * (u0 + u1)) / 2, h / 2 - (kk * (v0 + v1)) / 2).scale(kk);
}

export function centeredTransform(lon: number, lat: number, z: number, w: number, h: number) {
  const [u, v] = project(lon, lat);
  const k = TILE_SIZE * 2 ** z;
  return zoomIdentity.translate(w / 2 - k * u, h / 2 - k * v).scale(k);
}

/** Ground metres per CSS pixel at latitude `lat`. */
export function metresPerPixel(lat: number, k: number): number {
  return (EARTH_CIRCUMFERENCE * Math.cos((lat * Math.PI) / 180)) / k;
}

proj4.defs(
  "EPSG:2154",
  "+proj=lcc +lat_0=46.5 +lon_0=3 +lat_1=49 +lat_2=44 +x_0=700000 +y_0=6600000 +ellps=GRS80 +towgs84=0,0,0,0,0,0,0 +units=m +no_defs",
);
const toLambert93 = proj4("EPSG:4326", "EPSG:2154");

/** Lambert-93 (EPSG:2154) metres of a lon/lat, the CRS of the scans and labels. */
export function lambert93(lon: number, lat: number): [number, number] {
  return toLambert93.forward([lon, lat]) as [number, number];
}
