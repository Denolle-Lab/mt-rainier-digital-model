import { useEffect, useState } from "react";
import { isTypingTarget } from "../scene/cameraMath.js";
import { groups } from "../data/modelLayers.js";
import "./ui.css";

// Surface layers of the rainier3d model, draped on the terrain one at a time, plus the stream network (W).
export default function ModelLayers({ model, scene, active, onActive }) {
  const [opacity, setOpacity] = useState(80), [streams, setStreams] = useState(false);
  const pick = key => {
    const l = key ? model.byKey[key] : null;
    onActive(key);
    scene.setOverlay(l ? model.base + l.texture : null, { categorical: l?.kind === "categorical" });
  };
  const showStreams = on => { setStreams(on); scene.setStreams(on ? model.base + model.streams.texture : null); };
  useEffect(() => {
    const onKey = e => {
      if (e.metaKey || e.ctrlKey || e.altKey || isTypingTarget(e.target)) return;
      if (e.key?.toLowerCase() === "w" && model.streams) showStreams(!streams);
    };
    addEventListener("keydown", onKey);
    return () => removeEventListener("keydown", onKey);
  });
  return (
    <div className="layers model-layers">
      <div className="eyebrow">Surface model</div>
      <label className="ctl-row">
        <select className="mselect" value={active ?? ""} aria-label="Surface model layer" onChange={e => pick(e.target.value || null)}>
          <option value="">None (imagery)</option>
          {groups(model.layers).map(g => (
            <optgroup key={g.name} label={g.name}>
              {g.layers.map(l => <option key={l.key} value={l.key}>{l.label}</option>)}
            </optgroup>
          ))}
        </select>
      </label>
      {active && (
        <label className="ctl-row slider">Opacity <span className="mono">{opacity}%</span>
          <input type="range" min="10" max="100" step="5" value={opacity} aria-label="Layer opacity"
            onChange={e => { const v = +e.target.value; setOpacity(v); scene.setOverlayOpacity(v / 100); }} />
        </label>
      )}
      {model.streams && (
        <button className="tog" role="switch" aria-checked={streams} aria-label="Streams" onClick={() => showStreams(!streams)}>
          <span className="sw" /><span className="t">Streams<small>NHDPlus flowlines by stream order</small></span><kbd>W</kbd>
        </button>
      )}
    </div>
  );
}
