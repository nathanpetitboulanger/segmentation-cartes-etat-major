// Modern basemaps from the IGN Géoplateforme (WMTS, Web Mercator, no key needed), to
// compare the 19th-century maps with today's land.

export type Basemap = "plan" | "ortho" | "none";

const WMTS = "https://data.geopf.fr/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&STYLE=normal&TILEMATRIXSET=PM";

export const BASEMAPS: Record<Exclude<Basemap, "none">, { label: string; layer: string; format: string; maxZoom: number }> = {
  plan: { label: "Plan IGN", layer: "GEOGRAPHICALGRIDSYSTEMS.PLANIGNV2", format: "image/png", maxZoom: 19 },
  ortho: { label: "Aerial", layer: "ORTHOIMAGERY.ORTHOPHOTOS", format: "image/jpeg", maxZoom: 19 },
};

export function basemapUrl(b: Exclude<Basemap, "none">) {
  const { layer, format } = BASEMAPS[b];
  return (z: number, x: number, y: number) =>
    `${WMTS}&LAYER=${layer}&FORMAT=${format}&TILEMATRIX=${z}&TILEROW=${y}&TILECOL=${x}`;
}
