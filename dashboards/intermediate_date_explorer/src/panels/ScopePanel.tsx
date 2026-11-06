// The filter row and the headline numbers: which tiles every panel below describes.

import { format } from "d3-format";
import { DEPARTEMENT_NAMES, metricLabel, type ClassInfo, type Metric, type Tile } from "../data";

const km2Fmt = format(",.0f");
const pctFmt = format(".1f");

interface Props {
  tiles: Tile[];
  departements: string[];
  dep: string | null;
  onDep: (d: string | null) => void;
  range: [number, number] | null;
  metric: Metric;
  classes: ClassInfo[];
  onClearRange: () => void;
  focus: Tile | null;
  onClearFocus: () => void;
  onZoomFocus: () => void;
  count: number;
  km2: number[];
}

export function ScopePanel(p: Props) {
  const total = p.km2.reduce((a, b) => a + b, 0);
  const labelled = total - p.km2[0];
  const perDep = (d: string) => p.tiles.filter((t) => t.deps.includes(d)).length;

  return (
    <section className="panel scope" aria-label="Scope">
      <div className="filters">
        <label className="field">
          <span className="muted small">Département</span>
          <select value={p.dep ?? ""} onChange={(e) => p.onDep(e.target.value || null)}>
            <option value="">All {p.departements.length} départements</option>
            {p.departements.map((d) => (
              <option key={d} value={d}>
                {d} · {DEPARTEMENT_NAMES[d] ?? d} ({perDep(d)} tiles)
              </option>
            ))}
          </select>
        </label>
      </div>

      {(p.range || p.focus) && (
        <div className="chips">
          {p.range && (
            <span className="chip">
              {metricLabel(p.metric, p.classes)} {pctFmt(p.range[0])}–{pctFmt(p.range[1])} %
              <button type="button" onClick={p.onClearRange} aria-label="Clear the range filter">
                ×
              </button>
            </span>
          )}
          {p.focus && (
            <span className="chip chip-focus">
              Tile {p.focus.id}
              <button type="button" className="link" onClick={p.onZoomFocus}>
                zoom
              </button>
              <button type="button" onClick={p.onClearFocus} aria-label="Clear the selected tile">
                ×
              </button>
            </span>
          )}
        </div>
      )}

      <div className="stats">
        <div className="stat">
          <span className="stat-label">Scan tiles</span>
          <span className="stat-value">{p.count}</span>
          <span className="stat-sub muted">
            {p.focus ? `deps ${p.focus.deps.join(", ")}` : p.dep ? `of ${p.tiles.length}` : "20 × 20 km"}
          </span>
        </div>
        <div className="stat">
          <span className="stat-label">Area</span>
          <span className="stat-value">{km2Fmt(total)}</span>
          <span className="stat-sub muted">km² at 4 m/px</span>
        </div>
        <div className="stat">
          <span className="stat-label">Labelled</span>
          <span className="stat-value">{total ? `${pctFmt((100 * labelled) / total)} %` : "–"}</span>
          <span className="stat-sub muted">{km2Fmt(labelled)} km²</span>
        </div>
      </div>
    </section>
  );
}
