import { useState } from "react";
import { DEFAULT_RELOCATED } from "../data/relocated.js";
import "./ui.css";

// Before / after: the same earthquakes as located by ComCat, by NonLinLoc in the PNSN 1D model, and by NonLinLoc in
// the rainier3d 3D model (same picks and settings, hypocentres kept below the ground).
export default function RelocatedPanel({ points }) {
  const meta = points.reloc.meta;
  const [st, setSt] = useState(points.state ?? DEFAULT_RELOCATED);
  const apply = s => { setSt(s); points.set(s); };
  return (
    <div className="layers relocated">
      <div className="eyebrow">Relocated earthquakes, {meta.from.slice(0, 4)}–{meta.to.slice(0, 4)}</div>
      <button className="tog" role="switch" aria-checked={st.on} aria-label="Relocated earthquakes" onClick={() => apply({ ...st, on: !st.on })}>
        <span className="sw" /><span className="t">Show<small>{meta.count} events M ≥ {meta.magMin.toFixed(0)}</small></span>
      </button>
      {st.on && (
        <div className="sub">
          <div className="seg" role="radiogroup" aria-label="Catalogue">
            {Object.entries(meta.catalogs).map(([k, c]) => (
              <button key={k} role="radio" aria-checked={st.catalog === k} className={st.catalog === k ? "on" : ""}
                style={{ borderColor: c.color }} onClick={() => apply({ ...st, catalog: k })}>{c.label}</button>
            ))}
          </div>
          <button className="tog" role="switch" aria-checked={st.lines} aria-label="Shift lines" onClick={() => apply({ ...st, lines: !st.lines })}>
            <span className="sw" /><span className="t">Shift lines<small>from the 1D to the 3D location</small></span>
          </button>
          <button className="tog" role="switch" aria-checked={st.minQuality < 2} aria-label="Include quality C" onClick={() => apply({ ...st, minQuality: st.minQuality < 2 ? 2 : 1 })}>
            <span className="sw" /><span className="t">Include quality C<small>large gap, few phases or deep uncertainty</small></span>
          </button>
          <p className="note" data-testid="reloc-count">{points.shown} shown · {points.above} above the ground</p>
        </div>
      )}
    </div>
  );
}
