// What is under the pointer on the map. Kept outside React state: it changes on every
// pointer move, and only the readout and the histogram marker need to re-render.

import { useSyncExternalStore } from "react";
import type { Tile } from "../data";

export interface Hover {
  lon: number;
  lat: number;
  x93: number;
  y93: number;
  tile: Tile | null;
  classId: number | null; // null: label tile not loaded
}

let current: Hover | null = null;
const listeners = new Set<() => void>();

export const hoverStore = {
  get: () => current,
  set(h: Hover | null) {
    current = h;
    listeners.forEach((f) => f());
  },
  subscribe(f: () => void) {
    listeners.add(f);
    return () => void listeners.delete(f);
  },
};

export function useHover(): Hover | null {
  return useSyncExternalStore(hoverStore.subscribe, hoverStore.get);
}
