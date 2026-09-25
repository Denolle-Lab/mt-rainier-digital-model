import "./ui.css";

// Mass-movement legend and filter. "Events" shows the points, "Dated only" keeps observed and seismically recorded
// events, "Flow deposits" drapes the lahar and debris-flow layer. Clicking a class shows only that class; again: all.
export default function MassFilter({ doc, filter, onFilter, counts, flows, onFlows }) {
  const set = patch => onFilter({ ...filter, ...patch });
  const only = key => set({ on: true, classes: filter.classes?.size === 1 && filter.classes.has(key) ? null : new Set([key]) });
  const on = key => filter.on && (!filter.classes || filter.classes.has(key));
  return (
    <div className="sfilter mfilter">
      <div className="eyebrow">Mass movements</div>
      <div className="sf-row">
        <button className="sf-tog" aria-pressed={filter.on} onClick={() => set({ on: !filter.on })}>Events</button>
        <button className="sf-tog" aria-pressed={filter.dated} onClick={() => set({ dated: !filter.dated, on: true })}>Dated only</button>
        {onFlows && <button className="sf-tog" aria-pressed={flows} onClick={() => onFlows(!flows)}>Flow deposits</button>}
      </div>
      <div className="sf-key">large, light rim: seismically recorded · small: mapped landslide, at its crown</div>
      <div className="sf-kinds">
        {doc.classes.filter(c => counts[c.key]).map(c => (
          <button key={c.key} className="sf-kind" aria-pressed={on(c.key)} title={`Show only: ${c.label.toLowerCase()} (again: all)`}
            onClick={() => only(c.key)}>
            <span className="m-dot" style={{ background: c.color }} /><span>{c.label}</span>
            <span className="mono n">{counts[c.key].toLocaleString("en-US")}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
