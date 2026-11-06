// Layer controls, floating on the map.

import { useState } from "react";
import type { Manifest } from "../data";
import { BASEMAPS, type Basemap } from "../map/basemaps";
import type { GridMode, LayerSettings } from "../map/MapView";

interface Props {
  manifest: Manifest;
  settings: LayerSettings;
  onChange: (s: LayerSettings) => void;
}

export function LayersCard({ manifest, settings: s, onChange }: Props) {
  const [open, setOpen] = useState(true);
  const set = (patch: Partial<LayerSettings>) => onChange({ ...s, ...patch });
  const hasScans = !!manifest.layers.scans;
  const hasLabels = !!manifest.layers.labels;

  return (
    <div className="layers-card" onPointerDown={(e) => e.stopPropagation()}>
      <button type="button" className="layers-head" aria-expanded={open} onClick={() => setOpen(!open)}>
        Layers <span aria-hidden>{open ? "▾" : "▸"}</span>
      </button>
      {open && (
        <div className="layers-body">
          <Segmented<Basemap>
            label="Basemap"
            value={s.basemap}
            options={[
              ["plan", BASEMAPS.plan.label],
              ["ortho", BASEMAPS.ortho.label],
              ["none", "None"],
            ]}
            onChange={(basemap) => set({ basemap })}
          />

          <LayerRow
            label="Scans"
            hint={hasScans ? "SCAN État-major 40K" : "not built yet"}
            disabled={!hasScans}
            on={s.scans}
            opacity={s.scansOpacity}
            onToggle={(scans) => set({ scans })}
            onOpacity={(scansOpacity) => set({ scansOpacity })}
          />
          <LayerRow
            label="Labels"
            hint={hasLabels ? "data/interim/labels" : "not built yet"}
            disabled={!hasLabels}
            on={s.labels}
            opacity={s.labelsOpacity}
            onToggle={(labels) => set({ labels })}
            onOpacity={(labelsOpacity) => set({ labelsOpacity })}
          />
          <label className="check indent">
            <input
              type="checkbox"
              checked={s.swipe}
              disabled={!s.labels || !hasLabels}
              onChange={(e) => set({ swipe: e.target.checked })}
            />
            Swipe: scan left, labels right
          </label>

          <Segmented<GridMode>
            label="Scan tiles"
            value={s.grid}
            options={[
              ["off", "Off"],
              ["outline", "Outline"],
              ["colour", "Colour"],
            ]}
            onChange={(grid) => set({ grid })}
          />
          <p className="muted small">Colour fills tiles by the metric of the Tiles panel, fading out as you zoom in.</p>
        </div>
      )}
    </div>
  );
}

function LayerRow(p: {
  label: string;
  hint: string;
  disabled: boolean;
  on: boolean;
  opacity: number;
  onToggle: (on: boolean) => void;
  onOpacity: (o: number) => void;
}) {
  return (
    <div className={`layer-row${p.disabled ? " disabled" : ""}`}>
      <label className="check">
        <input type="checkbox" checked={p.on && !p.disabled} disabled={p.disabled} onChange={(e) => p.onToggle(e.target.checked)} />
        <span>
          {p.label} <span className="muted small">{p.hint}</span>
        </span>
      </label>
      <input
        type="range"
        min={0}
        max={1}
        step={0.05}
        value={p.opacity}
        disabled={p.disabled || !p.on}
        onChange={(e) => p.onOpacity(Number(e.target.value))}
        aria-label={`${p.label} opacity`}
      />
      <span className="num muted small opacity">{Math.round(p.opacity * 100)} %</span>
    </div>
  );
}

function Segmented<T extends string>(p: {
  label: string;
  value: T;
  options: [T, string][];
  onChange: (v: T) => void;
}) {
  return (
    <div className="segmented-field">
      <span className="muted small">{p.label}</span>
      <div className="segmented" role="radiogroup" aria-label={p.label}>
        {p.options.map(([v, text]) => (
          <button key={v} type="button" role="radio" aria-checked={p.value === v} onClick={() => p.onChange(v)}>
            {text}
          </button>
        ))}
      </div>
    </div>
  );
}
