import { useLayoutEffect, useRef } from "react";
import { KIND_BY_KEY } from "../data/kinds.js";
import { fmtElev, fmtSince } from "../data/format.js";
import Glyph from "./Glyph.jsx";
import { operators } from "./instruments.js";
import "./ui.css";

export default function Tooltip({ hover, notes = {}, virtual = {} }) {
  const ref = useRef(null);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el || !hover || hover.y + 18 + el.offsetHeight <= innerHeight - 8) return;
    el.style.top = `${Math.max(8, hover.y - 18 - el.offsetHeight)}px`;
  });
  if (!hover) return null;
  const { site, x, y } = hover;
  return (
    <div ref={ref} className="tip" style={{ left: Math.min(x + 18, innerWidth - 340), top: y + 18 }} role="tooltip">
      <div className="t-name">{site.name}</div>
      <div className="t-sub mono">{site.codes.join(" · ")}</div>
      <div className="t-sub">{operators(site).join(" · ")} · {fmtElev(site.elev)} · {fmtSince(site.since)}</div>
      <div className="t-list">{site.kinds.map(k => <div key={k} className="t-item"><Glyph glyph={KIND_BY_KEY[k].glyph} color={KIND_BY_KEY[k].color} /><span>{KIND_BY_KEY[k].label}</span></div>)}</div>
      {site.major && <div className="t-more">{site.major}</div>}
      {site.codes.filter(c => notes[c]).map(c => <div key={c} className="t-more">{c}: {notes[c].split(":")[0]}</div>)}
      {site.codes.filter(c => virtual[c]).map(c => (
        <div key={`v${c}`} className="t-virtual"><span className="vtag">Virtual sensor</span> {c} estimates {virtual[c].map(u => u.estimates).join("; ")}</div>
      ))}
    </div>
  );
}
