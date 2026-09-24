import { useState } from "react";
import "./ui.css";

function Seg({ label, options, value, onChange }) {
  return (
    <div className="ctl-row">
      <span className="eyebrow">{label}</span>
      <div className="seg" role="group" aria-label={label}>
        {options.map(([v, text]) => (
          <button key={v} aria-pressed={value === v} onClick={() => { if (v !== value) onChange(v); }}>{text}</button>
        ))}
      </div>
    </div>
  );
}

export default function Controls({ scene, children }) {
  const [view, setView] = useState("3d"), [style, setStyle] = useState("photo");
  return (
    <div className="panel controls">
      <Seg label="View" options={[["3d", "3D"], ["2d", "2D"]]} value={view} onChange={v => { setView(v); scene.setView(v); }} />
      <Seg label="Style" options={[["photo", "Photo"], ["mono", "Mono"], ["contours", "Contours"]]} value={style} onChange={v => { setStyle(v); scene.setStyle(v); }} />
      {children}
      <div className="hint">Drag to move · right-drag or <kbd>Ctrl</kbd>/<kbd>⌘</kbd>-drag to rotate · Scroll or pinch to zoom · <kbd>←</kbd><kbd>↑</kbd><kbd>↓</kbd><kbd>→</kbd> to glide · <b>?</b> at the bottom for help</div>
    </div>
  );
}
