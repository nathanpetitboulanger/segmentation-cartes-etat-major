// What is under the pointer: the label class, the scan tile, and the coordinates in
// WGS84 and in Lambert-93 (the CRS the scan tile names count in).

import { format } from "d3-format";
import { className, type ClassInfo } from "../data";
import { useHover } from "./hover";

const metres = format(",.0f");

export function Readout({ classes }: { classes: ClassInfo[] }) {
  const h = useHover();
  if (!h) return <div className="readout readout-idle">Hover the map to read a pixel</div>;
  const cls = classes.find((c) => c.id === h.classId);
  return (
    <div className="readout">
      <div className="readout-class">
        {cls ? (
          <>
            <span className="swatch" style={{ background: cls.colour }} />
            <strong>{className(cls.name)}</strong>
            <span className="muted">{cls.em_codes.join(" ")}</span>
          </>
        ) : h.classId === 0 ? (
          <span className="muted">No label</span>
        ) : (
          <span className="muted">Label tile not loaded</span>
        )}
      </div>
      <div className="readout-grid">
        <span className="muted">Tile</span>
        <span>{h.tile ? h.tile.id : "none"}</span>
        <span className="muted">WGS84</span>
        <span className="num">
          {h.lat.toFixed(5)}° N {Math.abs(h.lon).toFixed(5)}° {h.lon < 0 ? "W" : "E"}
        </span>
        <span className="muted">L93</span>
        <span className="num">
          {metres(h.x93)} · {metres(h.y93)}
        </span>
      </div>
    </div>
  );
}
