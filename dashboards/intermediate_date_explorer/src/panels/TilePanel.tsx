// The scan tiles by one metric: a histogram that is also the map's colour legend, brushed
// to filter the tiles, and the ranked list of the tiles it keeps (the histogram's table).

import { bin } from "d3-array";
import { brushX, type BrushBehavior } from "d3-brush";
import { format } from "d3-format";
import { scaleLinear, type ScaleQuantize } from "d3-scale";
import { select } from "d3-selection";
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { className, metricLabel, metricValue, type ClassInfo, type Metric, type Tile } from "../data";
import { useHover } from "../map/hover";

const pctFmt = format(".1f");
const BINS = 20;
const M = { top: 10, right: 10, bottom: 24, left: 30 };
const PLOT_H = 112;

interface Props {
  tiles: Tile[]; // in scope
  filtered: Tile[]; // in scope and in range
  metric: Metric;
  onMetric: (m: Metric) => void;
  classes: ClassInfo[];
  domain: [number, number];
  colour: ScaleQuantize<string>;
  range: [number, number] | null;
  onRange: (r: [number, number] | null) => void;
  focus: string | null;
  onFocus: (name: string) => void;
  onHoverTiles: (s: Set<string> | null) => void;
}

export function TilePanel(p: Props) {
  const [desc, setDesc] = useState(true);
  const ranked = useMemo(() => {
    const withValue = p.filtered.map((t) => ({ t, v: metricValue(t, p.metric) }));
    return withValue.sort((a, b) => {
      if (a.v === null) return 1;
      if (b.v === null) return -1;
      return desc ? b.v - a.v : a.v - b.v;
    });
  }, [p.filtered, p.metric, desc]);
  const undefinedCount = p.tiles.filter((t) => metricValue(t, p.metric) === null).length;

  return (
    <section className="panel" aria-label="Scan tiles">
      <div className="panel-head">
        <h2>Scan tiles</h2>
        <label className="field inline">
          <span className="muted small">by</span>
          <select
            value={String(p.metric)}
            onChange={(e) => p.onMetric(e.target.value === "labelled" ? "labelled" : Number(e.target.value))}
          >
            <option value="labelled">Labelled coverage</option>
            {p.classes.map((c) => (
              <option key={c.id} value={c.id}>
                {className(c.name)} share
              </option>
            ))}
          </select>
        </label>
      </div>
      <p className="muted small">
        {p.metric === "labelled"
          ? "Share of each tile's area that has a label."
          : `Share of each tile's labelled area that is ${className(p.classes.find((c) => c.id === p.metric)!.name).toLowerCase()}.`}{" "}
        Drag across the histogram to keep a range; its colours are the map's.
      </p>

      <Histogram {...p} />
      {undefinedCount > 0 && p.metric !== "labelled" && (
        <p className="muted small">{undefinedCount} tiles without labels are left out.</p>
      )}

      <div className="list-head">
        <span className="small">
          <strong>{p.filtered.length}</strong> <span className="muted">tiles{p.range ? " in range" : ""}</span>
        </span>
        <button type="button" className="link small" onClick={() => setDesc(!desc)}>
          {desc ? "highest first" : "lowest first"}
        </button>
      </div>
      <ol className="tile-list" onPointerLeave={() => p.onHoverTiles(null)}>
        {ranked.map(({ t, v }) => (
          <li key={t.name}>
            <button
              type="button"
              className={`tile-row${t.name === p.focus ? " active" : ""}`}
              onClick={() => p.onFocus(t.name)}
              onPointerEnter={() => p.onHoverTiles(new Set([t.name]))}
              onFocus={() => p.onHoverTiles(new Set([t.name]))}
            >
              <span className="num">{t.id}</span>
              <span className="muted small deps">{t.deps.join(" ")}</span>
              <span className="mini-track">
                {v !== null && (
                  <span
                    className="mini-bar"
                    style={{ width: `${(100 * v) / p.domain[1]}%`, background: p.colour(v) }}
                  />
                )}
              </span>
              <span className="num value">{v === null ? "–" : `${pctFmt(v)} %`}</span>
            </button>
          </li>
        ))}
      </ol>
    </section>
  );
}

function Histogram(p: Props) {
  const wrap = useRef<HTMLDivElement>(null);
  const brushG = useRef<SVGGElement>(null);
  const brush = useRef<BrushBehavior<unknown>>(null);
  const [width, setWidth] = useState(320);
  const [hoverBin, setHoverBin] = useState<number | null>(null);
  const hover = useHover();

  useLayoutEffect(() => {
    const el = wrap.current!;
    const ro = new ResizeObserver(([e]) => setWidth(e.contentRect.width));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const [d0, d1] = p.domain;
  const step = (d1 - d0) / BINS;
  const x = scaleLinear().domain(p.domain).range([M.left, Math.max(M.left + 10, width - M.right)]);
  const bins = useMemo(() => {
    const values = p.tiles.flatMap((t) => {
      const v = metricValue(t, p.metric);
      return v === null ? [] : [{ t, v }];
    });
    return bin<{ t: Tile; v: number }, number>()
      .value((d) => d.v)
      .domain(p.domain)
      .thresholds(Array.from({ length: BINS - 1 }, (_, i) => d0 + (i + 1) * step))(values);
  }, [p.tiles, p.metric, p.domain, d0, step]);
  const yMax = Math.max(1, ...bins.map((b) => b.length));
  const y = scaleLinear().domain([0, yMax]).nice(3).range([M.top + PLOT_H, M.top]);

  // the brush: drawn by d3 in its <g>, snapped to bin edges, synced from the range
  useEffect(() => {
    const b = brushX<unknown>()
      .extent([
        [M.left, M.top],
        [x.range()[1], M.top + PLOT_H],
      ])
      .on("end", (e: { selection: [number, number] | null; sourceEvent?: Event }) => {
        if (!e.sourceEvent) return; // moved by the code below
        if (!e.selection) return p.onRange(null);
        const lo = Math.max(d0, Math.floor((x.invert(e.selection[0]) - d0) / step) * step + d0);
        const hi = Math.min(d1, Math.max(lo + step, Math.ceil((x.invert(e.selection[1]) - d0) / step) * step + d0));
        p.onRange([lo, hi]);
      });
    brush.current = b;
    select(brushG.current!).call(b);
  }, [width, d0, d1]);
  useEffect(() => {
    if (!brush.current) return;
    select(brushG.current!).call(brush.current.move, p.range ? [x(p.range[0]), x(p.range[1])] : null);
  }, [p.range, width, d0, d1]);

  const pointer = (e: React.PointerEvent<SVGSVGElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    const v = x.invert(e.clientX - r.left);
    const i = v < d0 || v > d1 ? null : Math.min(BINS - 1, Math.floor((v - d0) / step));
    if (i === hoverBin) return;
    setHoverBin(i);
    p.onHoverTiles(i === null || !bins[i].length ? null : new Set(bins[i].map((d) => d.t.name)));
  };
  const leave = () => {
    setHoverBin(null);
    p.onHoverTiles(null);
  };

  const hoverValue = hover?.tile ? metricValue(hover.tile, p.metric) : null;
  const hb = hoverBin !== null ? bins[hoverBin] : null;

  return (
    <div className="histogram" ref={wrap}>
      <svg
        width={width}
        height={M.top + PLOT_H + M.bottom}
        onPointerMove={pointer}
        onPointerLeave={leave}
        role="img"
        aria-label={`Histogram of ${metricLabel(p.metric, p.classes)} over ${p.tiles.length} tiles`}
      >
        {y.ticks(3).map((v) => (
          <g key={v}>
            <line className="gridline" x1={M.left} x2={x.range()[1]} y1={y(v)} y2={y(v)} />
            <text className="axis-label" x={M.left - 6} y={y(v)} dy="0.32em" textAnchor="end">
              {v}
            </text>
          </g>
        ))}
        {bins.map((b, i) => {
          const x0 = x(b.x0!) + 1;
          const w = Math.max(0, x(b.x1!) - x(b.x0!) - 2);
          const top = y(b.length);
          const inRange = !p.range || (b.x0! >= p.range[0] - 1e-9 && b.x1! <= p.range[1] + 1e-9);
          return b.length ? (
            <path
              key={i}
              d={roundedTop(x0, top, w, y(0) - top, Math.min(3, w / 2))}
              fill={p.colour((b.x0! + b.x1!) / 2)}
              opacity={inRange ? (hoverBin === i ? 0.8 : 1) : 0.25}
            />
          ) : null;
        })}
        <line className="baseline" x1={M.left} x2={x.range()[1]} y1={y(0)} y2={y(0)} />
        {x.ticks(5).map((v) => (
          <text key={v} className="axis-label" x={x(v)} y={M.top + PLOT_H + 16} textAnchor="middle">
            {v} %
          </text>
        ))}
        {hoverValue !== null && hover?.tile && (
          <g className="marker" transform={`translate(${x(hoverValue)},0)`}>
            <line y1={M.top - 4} y2={M.top + PLOT_H} />
            <text y={M.top + 2} dx={x(hoverValue) > width / 2 ? -5 : 5} textAnchor={x(hoverValue) > width / 2 ? "end" : "start"}>
              {hover.tile.id}
            </text>
          </g>
        )}
        <g ref={brushG} className="brush" />
      </svg>
      {hb && hoverBin !== null && (
        <div
          className="tooltip"
          style={{ left: Math.min(width - 120, Math.max(0, x(hb.x0!) - 40)), top: Math.max(0, y(hb.length) - 46) }}
        >
          <strong>{hb.length} tiles</strong>
          <span className="muted">
            {pctFmt(hb.x0!)}–{pctFmt(hb.x1!)} %
          </span>
        </div>
      )}
    </div>
  );
}

/** A bar with rounded top corners and a square base. */
function roundedTop(x: number, y: number, w: number, h: number, r: number): string {
  if (h <= 0 || w <= 0) return "";
  const rr = Math.min(r, h);
  return `M${x},${y + h}V${y + rr}Q${x},${y} ${x + rr},${y}H${x + w - rr}Q${x + w},${y} ${x + w},${y + rr}V${y + h}Z`;
}
