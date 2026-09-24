import { PLACES } from "../scene/stationPose.js";
import "./ui.css";

export default function GoTo({ majors, onPlace, onSite, active }) {
  return (
    <nav className="panel goto" aria-label="Go to">
      <div className="eyebrow">Go to</div>
      <div className="row">{PLACES.map(p => <button key={p.key} aria-pressed={active === p.key} onClick={() => onPlace(p.key)}>{p.label}</button>)}</div>
      <div className="eyebrow">Major stations</div>
      <div className="row">{majors.map(s => (
        <button key={s.id} className="st mono" title={s.major} aria-pressed={active === s.id} onClick={() => onSite(s)}>{s.id.split(".")[1]}</button>
      ))}</div>
    </nav>
  );
}
