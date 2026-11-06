// The land-cover classes: legend, visibility switches for the label layer, and the share
// of each class in the labelled area of the current tiles, against all tiles.

import { format } from "d3-format";
import { scaleLinear } from "d3-scale";
import { className, type ClassInfo } from "../data";

const pctFmt = format(".1f");
const km2Fmt = format(",.0f");

interface Props {
  classes: ClassInfo[];
  km2: number[]; // current tiles, by class id
  globalKm2: number[]; // all tiles
  isSubset: boolean;
  hidden: Set<number>;
  onHidden: (s: Set<number>) => void;
  onEmphasis: (id: number | null) => void;
}

export function ClassPanel(p: Props) {
  const labelled = p.km2.slice(1).reduce((a, b) => a + b, 0);
  const globalLabelled = p.globalKm2.slice(1).reduce((a, b) => a + b, 0);
  const share = (id: number) => (labelled ? (100 * p.km2[id]) / labelled : 0);
  const globalShare = (id: number) => (100 * p.globalKm2[id]) / globalLabelled;
  const max = Math.max(...p.classes.map((c) => Math.max(share(c.id), p.isSubset ? globalShare(c.id) : 0)));
  const x = scaleLinear().domain([0, max || 1]).range([0, 100]);
  const total = p.km2.reduce((a, b) => a + b, 0);

  const toggle = (id: number, solo: boolean) => {
    const all = p.classes.map((c) => c.id);
    if (solo) {
      const onlyThis = all.every((k) => (k === id) !== p.hidden.has(k));
      p.onHidden(new Set(onlyThis ? [] : all.filter((k) => k !== id)));
      return;
    }
    const next = new Set(p.hidden);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    p.onHidden(next);
  };

  return (
    <section className="panel" aria-label="Land-cover classes">
      <div className="panel-head">
        <h2>Land-cover classes</h2>
        <div className="head-actions">
          <button type="button" className="link" onClick={() => p.onHidden(new Set())}>
            all
          </button>
          <button type="button" className="link" onClick={() => p.onHidden(new Set(p.classes.map((c) => c.id)))}>
            none
          </button>
        </div>
      </div>
      <p className="muted small">
        Share of the labelled area{p.isSubset && ", the tick marks all tiles"}. Click a class to show or hide
        it on the map, Alt-click to show it alone.
      </p>

      {labelled === 0 ? (
        <p className="empty">No labelled pixel in these tiles.</p>
      ) : (
        <ul className="classes" onPointerLeave={() => p.onEmphasis(null)}>
          {p.classes.map((c) => {
            const off = p.hidden.has(c.id);
            return (
              <li key={c.id}>
                <button
                  type="button"
                  className={`class-row${off ? " off" : ""}`}
                  aria-pressed={!off}
                  onClick={(e) => toggle(c.id, e.altKey)}
                  onPointerEnter={() => p.onEmphasis(off ? null : c.id)}
                  onFocus={() => p.onEmphasis(off ? null : c.id)}
                  onBlur={() => p.onEmphasis(null)}
                  title={`${c.em_codes.join(" ")}: ${km2Fmt(p.km2[c.id])} km²`}
                >
                  <span className="swatch" style={{ background: off ? "transparent" : c.colour, borderColor: c.colour }} />
                  <span className="class-name">
                    {className(c.name)}
                    <span className="muted small"> {c.em_codes.length > 2 ? "EM3, 6, 11–15" : c.em_codes.join(" ")}</span>
                  </span>
                  <span className="bar-track">
                    <span className="bar" style={{ width: `${x(share(c.id))}%`, background: c.colour }} />
                    {p.isSubset && <span className="tick" style={{ left: `${x(globalShare(c.id))}%` }} />}
                  </span>
                  <span className="num value">{pctFmt(share(c.id))} %</span>
                  <span className="num muted km2">{km2Fmt(p.km2[c.id])}</span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
      <p className="muted small no-label">
        No label: {total ? pctFmt((100 * p.km2[0]) / total) : "–"} % of the area ({km2Fmt(p.km2[0])} km²), outside
        the 16 départements of BD CARTO® État-major.
      </p>
    </section>
  );
}
