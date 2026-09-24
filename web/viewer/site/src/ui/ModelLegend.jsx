import { rampTicks } from "../data/modelLayers.js";
import "./ui.css";

export default function ModelLegend({ layer }) {
  if (!layer) return null;
  const { legend } = layer;
  return (
    <div className="mlegend">
      <div className="eyebrow">{layer.label}{layer.units && layer.kind !== "categorical" ? ` (${layer.units})` : ""}</div>
      {layer.kind === "categorical" ? (
        <div className="mclasses">
          {legend.classes.map(c => <div key={c.value} className="row"><span className="swatch" style={{ background: c.color }} />{c.label}</div>)}
        </div>
      ) : (
        <>
          <div className="qramp" style={{ background: `linear-gradient(90deg, ${legend.ramp.join(", ")})` }} />
          <div className="ramp-labels mono">{rampTicks(legend).map((t, i) => <span key={i}>{t}</span>)}</div>
          {legend.log && <div className="msrc">Log scale</div>}
        </>
      )}
      <div className="msrc">{layer.note}{layer.note ? ". " : ""}Model grid, 100 m cells.{" "}
        {layer.sources.map((s, i) => <span key={s.key}>{i ? ", " : "Source: "}{s.link ? <a href={s.link} target="_blank" rel="noreferrer">{s.key}</a> : s.key}</span>)}
      </div>
    </div>
  );
}
