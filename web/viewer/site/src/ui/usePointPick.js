import { useEffect, useRef, useState } from "react";

// Hover (mouse) or tap (touch) picking of a point layer: returns {s, x, y} or null. While a point is hit,
// scene[flag] is true so the model readout stays quiet. A tapped card closes after 5 s; any camera move drops it.
export function usePointPick(scene, points, flag) {
  const [hit, setHit] = useState(null), raf = useRef(0);
  useEffect(() => {
    if (!points) return undefined;
    const canvas = scene.renderer.domElement;
    let down = null, timer = 0;
    const at = (e, keep) => {
      cancelAnimationFrame(raf.current);
      raf.current = requestAnimationFrame(() => {
        const s = points.pick(e.clientX, e.clientY);
        scene[flag] = !!s;
        setHit(s ? { s, x: e.clientX, y: e.clientY } : null);
        if (s && keep) { clearTimeout(timer); timer = setTimeout(() => { scene[flag] = false; setHit(null); }, 5000); }
      });
    };
    const move = e => { if (e.pointerType === "mouse") at(e, false); };
    const pd = e => { if (e.pointerType !== "mouse") down = [e.clientX, e.clientY]; };
    const pu = e => { if (e.pointerType !== "mouse" && down && Math.hypot(e.clientX - down[0], e.clientY - down[1]) < 8) at(e, true); };
    canvas.addEventListener("pointermove", move); canvas.addEventListener("pointerdown", pd); canvas.addEventListener("pointerup", pu);
    // the card belongs to a screen position: drop it as soon as the camera moves (flights, keys, wheel)
    let last = scene.camera.position.clone();
    const watch = setInterval(() => {
      if (!scene.camera.position.equals(last)) { last = scene.camera.position.clone(); scene[flag] = false; setHit(null); }
    }, 200);
    return () => {
      scene[flag] = false;   // an unmounted card must not keep the model readout disabled
      clearInterval(watch);
      cancelAnimationFrame(raf.current); clearTimeout(timer);
      canvas.removeEventListener("pointermove", move); canvas.removeEventListener("pointerdown", pd); canvas.removeEventListener("pointerup", pu);
    };
  }, [scene, points, flag]);
  return hit;
}
