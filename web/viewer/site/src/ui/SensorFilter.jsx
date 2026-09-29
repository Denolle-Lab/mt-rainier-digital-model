import { KINDS } from "../data/kinds.js";
import { fiberOn, surveyOn } from "../data/sensors.js";
import Glyph from "./Glyph.jsx";
import "./ui.css";

// The sensor legend doubles as the filter: current and past sites, one toggle per survey (named deployments, shown
// whatever Current / Past say), and one toggle per instrument kind with its count under those switches. Clicking a
// kind shows only that kind; clicking it again shows all.
export default function SensorFilter({ filter, onFilter, counts, das, surveys = [], virtual = {} }) {
  const set = patch => onFilter({ ...filter, ...patch });
  const only = key => set({ kinds: filter.kinds?.size === 1 && filter.kinds.has(key) ? null : new Set([key]) });
  const on = key => !filter.kinds || filter.kinds.has(key);
  const tog = (k, label) => (
    <button className="sf-tog" aria-pressed={filter[k]} onClick={() => set({ [k]: !filter[k] })}>{label}</button>
  );
  const togSurvey = key => {
    const off = new Set(filter.surveysOff);
    off.has(key) ? off.delete(key) : off.add(key);
    set({ surveysOff: off });
  };
  return (
    <div className="sfilter">
      <div className="eyebrow">Sensors</div>
      <div className="sf-row">{tog("current", "Current")}{tog("past", "Past")}</div>
      {surveys.length > 0 && (<>
        <div className="eyebrow">Surveys</div>
        <div className="sf-surveys">
          {surveys.map(s => (
            <button key={s.key} className="sf-tog" aria-pressed={surveyOn(filter, s.key)} onClick={() => togSurvey(s.key)}>
              {s.label} ({s.period})
            </button>
          ))}
        </div>
      </>)}
      <div className="sf-key">filled: permanent network · ring: temporary · faded: past deployment</div>
      <div className="sf-kinds">
        {KINDS.filter(k => counts[k.key]).map(k => (
          <button key={k.key} className="sf-kind" aria-pressed={on(k.key)} title={`Show only ${k.label.toLowerCase()} (again: all)`}
            onClick={() => only(k.key)}>
            <Glyph glyph={k.glyph} color={k.color} /><span>{k.label}</span><span className="mono n">{counts[k.key].toLocaleString("en-US")}</span>
          </button>
        ))}
        {fiberOn(das, filter) && (
          <button className="sf-kind" aria-pressed={on("das")} title="Show only the DAS fiber (again: all)" onClick={() => only("das")}>
            <span className="sf-line" /><span>DAS fiber</span><span className="mono n">{das.channels.toLocaleString("en-US")} ch</span>
          </button>
        )}
      </div>
      {Object.keys(virtual).length > 0 && (
        <div className="sf-virtual">
          <span className="vbadge-key" aria-hidden="true">V</span>
          <div><b>Virtual sensors ({Object.keys(virtual).length})</b>: instruments repurposed to estimate what they were not designed to
            measure. {Object.entries(virtual).map(([c, uses]) => `${c.split(".")[1]}: ${uses.map(u => u.estimates.split(" (")[0]).join(", ")}`).join("; ")}.</div>
        </div>
      )}
    </div>
  );
}
