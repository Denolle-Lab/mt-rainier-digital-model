import { SHELLS } from "../scene/quakes/shells.js";
import "./ui.css";

const fmtMag = m => (m < 0 ? `−${Math.abs(m)}` : `${m}`);

export default function QuakeLegend({ meta }) {
  return (
    <div>
      <div className="eyebrow">Earthquakes</div>
      <div className="qramp" />
      <div className="ramp-labels"><span>few</span><span>many</span></div>
      <div className="row">Shells enclose {SHELLS.map(s => `${Math.round(s.fraction * 100)}`).join(" / ")}% of events</div>
      <div className="row qsrc">{meta.count.toLocaleString("en-US")} earthquakes, {meta.from?.slice(0, 4)}–{meta.to?.slice(0, 4)}, M {fmtMag(meta.magMin)} to {meta.magMax}.
        {meta.aboveGround ? ` ${meta.aboveGround} located above the ground are not drawn.` : ""}</div>
    </div>
  );
}
