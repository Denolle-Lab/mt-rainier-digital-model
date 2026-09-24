import { KINDS } from "../data/kinds.js";
import Glyph from "./Glyph.jsx";
import "./ui.css";

export default function Legend({ bundle, children }) {
  const present = new Set(bundle.stations.sites.flatMap(s => s.kinds));
  return (
    <div className="panel legend">
      <div><div className="eyebrow">Station marker</div>
        <div className="row">One ring segment per instrument kind</div>
        <div className="kinds">{KINDS.filter(k => present.has(k.key)).map(k => <div key={k.key} className="row"><Glyph glyph={k.glyph} color={k.color} />{k.label}</div>)}</div></div>
      {children}
      <div className="attribution">Terrain and imagery: USGS 3DEP and The National Map (public domain), 1 m lidar at the summit. Stations: EarthScope FDSN, active as of {bundle.stations.asOf}.{bundle.quakes ? " Earthquakes: USGS ComCat (PNSN), depth below sea level." : ""}</div>
    </div>
  );
}
