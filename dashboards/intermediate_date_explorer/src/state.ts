// Per-viewer conveniences kept in localStorage: layer settings and the colour theme.
// Storage may be unavailable (private window): everything still works without it.

import { useEffect, useLayoutEffect, useState } from "react";

export function useStored<T extends object>(key: string, initial: T): [T, (v: T) => void] {
  const [value, setValue] = useState<T>(() => {
    try {
      const raw = localStorage.getItem(`etat-major-explorer:${key}`);
      return raw ? { ...initial, ...JSON.parse(raw) } : initial;
    } catch {
      return initial;
    }
  });
  const set = (v: T) => {
    setValue(v);
    try {
      localStorage.setItem(`etat-major-explorer:${key}`, JSON.stringify(v));
    } catch {
      // not persisted, still applied
    }
  };
  return [value, set];
}

export type ThemeChoice = "auto" | "light" | "dark";

const media = window.matchMedia("(prefers-color-scheme: dark)");

/** The chosen theme, its setter, and the resolved one ("light" | "dark"). */
export function useTheme(): [ThemeChoice, (t: ThemeChoice) => void, "light" | "dark"] {
  const [{ choice }, setStored] = useStored<{ choice: ThemeChoice }>("theme", { choice: "auto" });
  const [systemDark, setSystemDark] = useState(media.matches);
  useEffect(() => {
    const onChange = (e: MediaQueryListEvent) => setSystemDark(e.matches);
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, []);
  // before the map reads its colours from the CSS (passive effects run after layout ones)
  useLayoutEffect(() => {
    if (choice === "auto") delete document.documentElement.dataset.theme;
    else document.documentElement.dataset.theme = choice;
  }, [choice]);
  const resolved = choice === "auto" ? (systemDark ? "dark" : "light") : choice;
  return [choice, (c) => setStored({ choice: c }), resolved];
}
