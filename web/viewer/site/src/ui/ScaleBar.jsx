import { useEffect, useState } from "react";
import "./ui.css";

const STEPS = [0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50];   // km

// km per screen pixel at the view centre (the orbit target), for a perspective camera
export function kmPerPixel(fovDeg, distKm, viewportPx) {
  return (2 * distKm * Math.tan((fovDeg * Math.PI) / 360)) / viewportPx;
}

// the round length whose bar is closest to `targetPx` without exceeding `maxPx`
export function niceScale(kmPerPx, targetPx = 110, maxPx = 150) {
  let best = STEPS[0];
  for (const s of STEPS) if (s / kmPerPx <= maxPx && Math.abs(s / kmPerPx - targetPx) < Math.abs(best / kmPerPx - targetPx)) best = s;
  return { km: best, px: best / kmPerPx };
}

// Horizontal scale bar, exact at the view centre; a perspective view is larger in front of it and smaller behind.
export default function ScaleBar({ scene }) {
  const [s, setS] = useState(null);
  useEffect(() => {
    const tick = () => {
      const cam = scene.camera, dist = cam.position.distanceTo(scene.controls.target);
      setS(niceScale(kmPerPixel(cam.fov, dist, innerHeight)));
    };
    tick();
    const id = setInterval(tick, 250);
    return () => clearInterval(id);
  }, [scene]);
  if (!s) return null;
  const label = s.km < 1 ? `${Math.round(s.km * 1000)} m` : `${s.km} km`;
  return (
    <div className="panel scalebar" aria-label={`Scale: ${label} at the view centre`} title="Exact at the view centre; nearer ground looks larger, farther ground smaller">
      <div className="sb-bar" style={{ width: `${s.px}px` }} />
      <div className="sb-label mono">{label}</div>
    </div>
  );
}
