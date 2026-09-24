import { useEffect, useRef, useState } from "react";
import { formatValue, loadValues, sampleValue } from "../data/modelLayers.js";
import { fromX, fromZ } from "../scene/geo.js";
import "./ui.css";

// Value of the draped model layer at the ground point under the pointer.
export default function ModelReadout({ scene, model, layer, box }) {
  const [read, setRead] = useState(null), values = useRef(null), raf = useRef(0);
  useEffect(() => {
    values.current = null; setRead(null);
    if (!layer) return;
    let live = true;
    loadValues(model, layer).then(v => { if (live) values.current = v; });
    const canvas = scene.renderer.domElement;
    const move = e => {
      cancelAnimationFrame(raf.current);
      raf.current = requestAnimationFrame(() => {
        const g = values.current && scene.groundAt(e.clientX, e.clientY);
        if (!g) { setRead(null); return; }
        const lon = fromX(g.x), lat = fromZ(g.z);
        setRead({ x: e.clientX, y: e.clientY, text: formatValue(layer, sampleValue(layer, values.current, box, lon, lat)),
          where: `${lat.toFixed(4)}° N ${Math.abs(lon).toFixed(4)}° W · ${Math.round((g.elevKm ?? 0) * 1000)} m` });
      });
    };
    const leave = () => { cancelAnimationFrame(raf.current); setRead(null); };
    canvas.addEventListener("pointermove", move); canvas.addEventListener("pointerleave", leave);
    return () => { live = false; cancelAnimationFrame(raf.current); canvas.removeEventListener("pointermove", move); canvas.removeEventListener("pointerleave", leave); };
  }, [scene, model, layer, box]);
  if (!read) return null;
  return (
    <div className="mread" style={{ left: Math.min(read.x + 16, innerWidth - 250), top: read.y + 16 }} role="status">
      <div className="t-name">{read.text}</div>
      <div className="t-sub mono">{read.where}</div>
    </div>
  );
}
