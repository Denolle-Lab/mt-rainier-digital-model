import { KINDS } from "../data/kinds.js";
import Glyph from "./Glyph.jsx";
import "./ui.css";

// The sensor legend doubles as the filter: networks (permanent / temporary), past deployments, and one toggle per
// instrument kind with its count under the current network filter. Clicking a kind shows only that kind; clicking
// it again shows all.
export default function SensorFilter({ filter, onFilter, counts, das }) {
  const set = patch => onFilter({ ...filter, ...patch });
  const only = key => set({ kinds: filter.kinds?.size === 1 && filter.kinds.has(key) ? null : new Set([key]) });
  const on = key => !filter.kinds || filter.kinds.has(key);
  const tog = (k, label) => (
    <button className="sf-tog" aria-pressed={filter[k]} onClick={() => set({ [k]: !filter[k] })}>{label}</button>
  );
  return (
    <div className="sfilter">
      <div className="eyebrow">Sensors</div>
      <div className="sf-row">{tog("permanent", "Permanent")}{tog("temporary", "Temporary")}{tog("past", "Past")}</div>
      <div className="sf-key">filled: permanent network · ring: temporary · faded: past deployment</div>
      <div className="sf-kinds">
        {KINDS.filter(k => counts[k.key]).map(k => (
          <button key={k.key} className="sf-kind" aria-pressed={on(k.key)} title={`Show only ${k.label.toLowerCase()} (again: all)`}
            onClick={() => only(k.key)}>
            <Glyph glyph={k.glyph} color={k.color} /><span>{k.label}</span><span className="mono n">{counts[k.key].toLocaleString("en-US")}</span>
          </button>
        ))}
        {das && filter.temporary && (
          <button className="sf-kind" aria-pressed={on("das")} title="Show only the DAS fiber (again: all)" onClick={() => only("das")}>
            <span className="sf-line" /><span>DAS fiber</span><span className="mono n">{das.channels.toLocaleString("en-US")} ch</span>
          </button>
        )}
      </div>
    </div>
  );
}
