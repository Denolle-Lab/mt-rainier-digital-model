import { useEffect, useState } from "react";
import { isTypingTarget } from "../scene/cameraMath.js";
import "./ui.css";

const LAYERS = [
  ["cloud", "Glow cloud", "every event as faint light", "G"],
  ["shells", "Density shells", "70 / 45 / 20% of events", "S"],
  ["dots", "Dots", "one per event, sized by magnitude", "D"],
];

function Toggle({ label, sub, k, on, onChange }) {
  return (
    <button className="tog" role="switch" aria-checked={on} aria-label={label} onClick={() => onChange(!on)}>
      <span className="sw" /><span className="t">{label}{sub && <small>{sub}</small>}</span><kbd>{k}</kbd>
    </button>
  );
}

export default function LayerPanel({ layers, scene, onStations }) {
  const [st, setSt] = useState(layers.state), [see, setSee] = useState(0);
  const [cut, setCut] = useState(scene.cut ?? { on: false, angle: 90, offset: 0 }), [stations, setStations] = useState(true);
  useEffect(() => scene.onCut?.(setCut), [scene]);   // the subsurface section can switch the cut on too
  const toggle = (k, v) => { layers.set(k, v); setSt(layers.state); };
  const applyCut = c => { setCut(c); scene.setCut(c); };
  const showStations = v => { setStations(v); onStations(v); };
  useEffect(() => {
    const onKey = e => {
      if (e.metaKey || e.ctrlKey || e.altKey || isTypingTarget(e.target)) return;
      const k = e.key?.toLowerCase();
      if (k === "g" || k === "s" || k === "d") { const key = { g: "cloud", s: "shells", d: "dots" }[k]; toggle(key, !layers.state[key]); }
      if (k === "x") applyCut({ ...cut, on: !cut.on });
      if (k === "t") showStations(!stations);
    };
    addEventListener("keydown", onKey);
    return () => removeEventListener("keydown", onKey);
  });
  return (
    <div className="layers">
      <div className="eyebrow">Earthquakes</div>
      {LAYERS.map(([k, label, sub, key]) => <Toggle key={k} k={key} label={label} sub={sub} on={st[k]} onChange={v => toggle(k, v)} />)}
      <div className="eyebrow">Ground</div>
      <label className="ctl-row slider">See-through <span className="mono">{see}%</span>
        <input type="range" min="0" max="90" step="1" value={see} aria-label="See-through" onChange={e => { const v = +e.target.value; setSee(v); scene.setSeeThrough(v); }} />
      </label>
      <Toggle label="Cut away terrain" sub="remove one side to look in" k="X" on={cut.on} onChange={v => applyCut({ ...cut, on: v })} />
      {cut.on && (
        <div className="sub">
          <label className="ctl-row slider">Direction <span className="mono">{cut.angle}°</span>
            <input type="range" min="0" max="359" value={cut.angle} aria-label="Direction" onChange={e => applyCut({ ...cut, angle: +e.target.value })} />
          </label>
          <label className="ctl-row slider">Position <span className="mono">{cut.offset.toFixed(1)} km</span>
            <input type="range" min="-20" max="20" step="0.5" value={cut.offset} aria-label="Position" onChange={e => applyCut({ ...cut, offset: +e.target.value })} />
          </label>
        </div>
      )}
      <Toggle label="Stations" k="T" on={stations} onChange={showStations} />
    </div>
  );
}
