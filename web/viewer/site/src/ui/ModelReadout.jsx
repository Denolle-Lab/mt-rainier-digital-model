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
    const leave = e => { if (e.pointerType !== "mouse") return; cancelAnimationFrame(raf.current); setRead(null); };   // touch 'leaves' on every lift
    // touch has no hover: a tap (press and release without dragging) reads the value, which stays for 4 s
    let down = null, timer = 0;
    const onMove = e => { if (e.pointerType === "mouse") move(e); };
    const onDown = e => { if (e.pointerType !== "mouse") down = [e.clientX, e.clientY]; };
    const onUp = e => {
      if (e.pointerType === "mouse" || !down || Math.hypot(e.clientX - down[0], e.clientY - down[1]) > 8) return;
      move(e); clearTimeout(timer); timer = setTimeout(() => setRead(null), 4000);
    };
    canvas.addEventListener("pointermove", onMove); canvas.addEventListener("pointerleave", leave);
    canvas.addEventListener("pointerdown", onDown); canvas.addEventListener("pointerup", onUp);
    return () => {
      live = false; cancelAnimationFrame(raf.current); clearTimeout(timer);
      canvas.removeEventListener("pointermove", onMove); canvas.removeEventListener("pointerleave", leave);
      canvas.removeEventListener("pointerdown", onDown); canvas.removeEventListener("pointerup", onUp);
    };
  }, [scene, model, layer, box]);
  if (!read) return null;
  return (
    <div className="mread" style={{ left: Math.min(read.x + 16, innerWidth - 250), top: read.y + 16 }} role="status">
      <div className="t-name">{read.text}</div>
      <div className="t-sub mono">{read.where}</div>
    </div>
  );
}
