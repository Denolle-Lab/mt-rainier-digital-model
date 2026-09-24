import { useEffect, useState } from "react";
import ModelLegend from "./ModelLegend.jsx";
import "./ui.css";

// The velocity model below ground: property, a section on the terrain cut, and a horizontal depth slice.
export default function SubsurfacePanel({ volume, scene }) {
  const [key, setKey] = useState(""), [section, setSection] = useState(false), [slice, setSlice] = useState(false);
  const [km, setKm] = useState(-2), [cut, setCut] = useState(scene.cut);
  useEffect(() => scene.onCut(setCut), [scene]);
  const vars = volume.meta.vars;
  const pick = k => { setKey(k); volume.setVar(k || null); };
  const showSection = on => {
    setSection(on); volume.setSection(on);
    if (on && !scene.cut.on) scene.setCut({ ...scene.cut, on: true });   // the section lives on the cut
    if (on && !key) pick("vs");
  };
  const showSlice = on => { setSlice(on); volume.setSlice(on, km); if (on && !key) pick("vs"); };
  const v = key ? vars[key] : null;
  const layer = v && { label: `${v.label} below ground`, units: v.units, kind: v.kind, legend: v.legend,
    note: "Fused rainier3d model, 500 m × 250 m cells", sources: [] };
  return (
    <div className="layers subsurface">
      <div className="eyebrow">Below ground</div>
      <label className="ctl-row">
        <select className="mselect" value={key} aria-label="Subsurface property" onChange={e => pick(e.target.value)}>
          <option value="">None</option>
          {Object.entries(vars).map(([k, x]) => <option key={k} value={k}>{x.label}</option>)}
        </select>
      </label>
      <button className="tog" role="switch" aria-checked={section} aria-label="Section on the cut" onClick={() => showSection(!section)}>
        <span className="sw" /><span className="t">Section on the cut<small>vertical slice where the terrain is cut away</small></span>
      </button>
      {section && (
        <div className="sub">
          <label className="ctl-row slider">Direction <span className="mono">{cut.angle}°</span>
            <input type="range" min="0" max="359" value={cut.angle} aria-label="Section direction"
              onChange={e => scene.setCut({ ...scene.cut, on: true, angle: +e.target.value })} />
          </label>
          <label className="ctl-row slider">Position <span className="mono">{cut.offset.toFixed(1)} km</span>
            <input type="range" min="-30" max="30" step="0.5" value={cut.offset} aria-label="Section position"
              onChange={e => scene.setCut({ ...scene.cut, on: true, offset: +e.target.value })} />
          </label>
        </div>
      )}
      <button className="tog" role="switch" aria-checked={slice} aria-label="Depth slice" onClick={() => showSlice(!slice)}>
        <span className="sw" /><span className="t">Depth slice<small>horizontal plane at a fixed elevation</small></span>
      </button>
      {slice && (
        <label className="ctl-row slider sub">Elevation <span className="mono">{km > 0 ? `+${km}` : km} km</span>
          <input type="range" min="-19.5" max="4" step="0.25" value={km} aria-label="Slice elevation"
            onChange={e => { const x = +e.target.value; setKm(x); volume.setSlice(true, x); }} />
        </label>
      )}
      {layer && <ModelLegend layer={layer} />}
    </div>
  );
}
