import { KIND_BY_KEY } from "../data/kinds.js";
import Glyph from "./Glyph.jsx";
import { usePointPick } from "./usePointPick.js";
import "./ui.css";

// Hover (or tap) card for the inventory points: name, instruments, network type, status and dates.
export default function SensorTip({ scene, points }) {
  const hit = usePointPick(scene, points, "sensorHover");
  if (!hit) return null;
  const { s } = hit;
  const when = s.status === "operating" ? `operating since ${s.start ?? "?"}` : `${s.start ?? "?"} to ${s.end ?? "?"}`;
  return (
    <div className="tip stip" style={{ left: Math.min(hit.x + 18, innerWidth - 330), top: Math.min(hit.y + 18, innerHeight - 160) }} role="tooltip">
      <div className="t-name">{s.name}</div>
      <div className="t-sub">{s.temporary ? "Temporary" : "Permanent"} · {s.source} · {when}</div>
      <div className="t-list">
        {s.kinds.map(k => <div key={k} className="t-item"><Glyph glyph={KIND_BY_KEY[k]?.glyph ?? "circle"} color={KIND_BY_KEY[k]?.color ?? "#888"} /><span>{KIND_BY_KEY[k]?.label ?? k}</span></div>)}
      </div>
      {s.instruments.length > 0 && <div className="t-more">{s.instruments.join(" · ")}</div>}
      {s.notes && <div className="t-more">{s.notes}</div>}
    </div>
  );
}
