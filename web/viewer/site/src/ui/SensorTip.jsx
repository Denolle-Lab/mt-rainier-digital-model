import { useEffect, useRef, useState } from "react";
import { KIND_BY_KEY } from "../data/kinds.js";
import Glyph from "./Glyph.jsx";
import "./ui.css";

// Hover (or tap) card for the inventory points: name, instruments, network type, status and dates.
export default function SensorTip({ scene, points }) {
  const [hit, setHit] = useState(null), raf = useRef(0);
  useEffect(() => {
    const canvas = scene.renderer.domElement;
    let down = null, timer = 0;
    const at = (e, keep) => {
      cancelAnimationFrame(raf.current);
      raf.current = requestAnimationFrame(() => {
        const s = points.pick(e.clientX, e.clientY);
        scene.sensorHover = !!s;
        setHit(s ? { s, x: e.clientX, y: e.clientY } : null);
        if (s && keep) { clearTimeout(timer); timer = setTimeout(() => { scene.sensorHover = false; setHit(null); }, 5000); }
      });
    };
    const move = e => { if (e.pointerType === "mouse") at(e, false); };
    const pd = e => { if (e.pointerType !== "mouse") down = [e.clientX, e.clientY]; };
    const pu = e => { if (e.pointerType !== "mouse" && down && Math.hypot(e.clientX - down[0], e.clientY - down[1]) < 8) at(e, true); };
    canvas.addEventListener("pointermove", move); canvas.addEventListener("pointerdown", pd); canvas.addEventListener("pointerup", pu);
    // the card belongs to a screen position: drop it as soon as the camera moves (flights, keys, wheel)
    let last = scene.camera.position.clone();
    const watch = setInterval(() => {
      if (!scene.camera.position.equals(last)) { last = scene.camera.position.clone(); scene.sensorHover = false; setHit(null); }
    }, 200);
    return () => {
      clearInterval(watch);
      cancelAnimationFrame(raf.current); clearTimeout(timer);
      canvas.removeEventListener("pointermove", move); canvas.removeEventListener("pointerdown", pd); canvas.removeEventListener("pointerup", pu);
    };
  }, [scene, points]);
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
