import { KINDS } from "../data/kinds.js";
import Glyph from "./Glyph.jsx";
import SensorFilter from "./SensorFilter.jsx";
import "./ui.css";

export default function Legend({ bundle, children, sensors }) {
  const present = new Set(bundle.stations.sites.flatMap(s => s.kinds));
  return (
    <div className="panel legend">
      {sensors ? <SensorFilter {...sensors} /> : <div><div className="eyebrow">Station marker</div>
        <div className="row">One ring segment per instrument kind</div>
        <div className="kinds">{KINDS.filter(k => present.has(k.key)).map(k => <div key={k.key} className="row"><Glyph glyph={k.glyph} color={k.color} />{k.label}</div>)}</div></div>}
      {children}
    </div>
  );
}
