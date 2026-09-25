import { isSeismic } from "../data/massEvents.js";
import { usePointPick } from "./usePointPick.js";
import "./ui.css";

const fmtVol = v => (v >= 1e6 ? `${(v / 1e6).toPrecision(2)} million m³` : `${Math.round(v).toLocaleString("en-US")} m³`);

// Hover (or tap) card for a mass-movement event: what, when, how it was located, size, source.
export default function MassTip({ scene, points, doc }) {
  const hit = usePointPick(scene, points, "massHover");
  if (!hit) return null;
  const { s: e } = hit;
  const cls = doc.classes.find(c => c.key === e.cls);
  const when = e.date ? (isSeismic(e) ? `${e.date} UTC` : e.date) : e.age || "undated";
  const src = doc.sources[e.source];
  return (
    <div className="tip stip" style={{ left: Math.min(hit.x + 18, innerWidth - 330), top: Math.min(hit.y + 18, innerHeight - 170) }} role="tooltip">
      <div className="t-name">{e.name || cls?.label}</div>
      <div className="t-sub">{e.type} · {when}</div>
      <div className="t-more">
        {isSeismic(e) ? `Seismically located, ${e.confidence}` : `Located at the ${e.located}${e.crown_dem ? `, on ${e.crown_dem.replace(/(\d)m$/, "$1 m")} elevation` : ""}`}
        {e.volume_m3 ? ` · volume ${fmtVol(e.volume_m3)}` : ""}{e.depth_m ? ` · failure depth ${e.depth_m} m` : ""}
        {!isSeismic(e) && e.confidence ? ` · confidence ${e.confidence.toLowerCase()}` : ""}
      </div>
      {src && <div className="t-more">{src.title}</div>}
    </div>
  );
}
