import { KINDS } from "../data/kinds.js";
import Glyph from "./Glyph.jsx";
import SensorFilter from "./SensorFilter.jsx";
import "./ui.css";

export default function Legend({ bundle, children, sensors, mass }) {
  const present = new Set(bundle.stations.sites.flatMap(s => s.kinds));
  return (
    <div className="panel legend">
      {sensors ? <SensorFilter {...sensors} /> : <div><div className="eyebrow">Station marker</div>
        <div className="row">One ring segment per instrument kind</div>
        <div className="kinds">{KINDS.filter(k => present.has(k.key)).map(k => <div key={k.key} className="row"><Glyph glyph={k.glyph} color={k.color} />{k.label}</div>)}</div></div>}
      {children}
      <div className="attribution">Terrain and imagery: USGS 3DEP and The National Map (public domain), 1 m lidar at the summit. Stations: EarthScope FDSN, active as of {bundle.stations.asOf}{sensors ? "; other sensors: rainier3d inventory (UW 2025 nodes, EarthScope GNSS, Synoptic, past FDSN deployments, DAS)" : ""}.{bundle.quakes ? " Earthquakes: USGS ComCat (PNSN), depth below sea level." : ""}{mass ? " Mass movements: Washington Geological Survey landslide inventory and 1:100,000 geology, Allstadt et al. (2017)." : ""}</div>
    </div>
  );
}
