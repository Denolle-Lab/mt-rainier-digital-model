import { useEffect, useMemo, useState } from "react";
import { frameTime, timeLabels, windowAt } from "../data/events.js";
import "./ui.css";

const W = 232, H = 46;

// one small time series: bars (rain) or a line (discharge), AR windows shaded, a cursor at frame k
function Series({ values, k, kind, windows, doc, label, unit }) {
  const n = values.length, max = Math.max(...values.filter(v => v != null), 1e-6);
  const x = i => (i / (n - 1)) * W, y = v => H - (v / max) * (H - 4);
  const t0 = Date.parse(doc.frames.start), step = doc.frames.stepHours * 3600e3;
  const xt = ms => Math.max(0, Math.min(W, x((ms - t0) / step)));
  const line = values.map((v, i) => (v == null ? null : `${x(i).toFixed(1)},${y(v).toFixed(1)}`)).filter(Boolean).join(" ");
  const now = values[k];
  return (
    <div className="ev-series">
      <div className="ev-series-head"><span>{label}</span><span className="mono">{now == null ? "–" : now.toFixed(unit === "mm/h" ? 1 : 0)} {unit}</span></div>
      <svg className="ev-svg" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" height={H} role="img" aria-label={`${label}, maximum ${max.toFixed(1)} ${unit}`}>
        {windows.map(w => <rect key={w.label} className="ev-win" x={xt(Date.parse(w.start))} y={0} width={xt(Date.parse(w.end)) - xt(Date.parse(w.start))} height={H} />)}
        {kind === "bars"
          ? values.map((v, i) => v ? <rect key={i} className="ev-bar" x={x(i) - 0.4} y={y(v)} width={Math.max(0.8, W / n - 0.2)} height={H - y(v)} /> : null)
          : <polyline className="ev-line" points={line} />}
        <line className="ev-cursor" x1={x(k)} x2={x(k)} y1={0} y2={H} />
      </svg>
    </div>
  );
}

// Events: one storm replayed hour by hour. Observed forcing and river response only; nothing responds to the rain.
export default function EventsPanel({ event }) {
  const { doc } = event;
  const [k, setK] = useState(() => doc.rain.domainMean.indexOf(Math.max(...doc.rain.domainMean.filter(v => v != null))));
  const [play, setPlay] = useState(false), [rain, setRain] = useState(true), [gauges, setGauges] = useState(true);
  const sites = useMemo(() => [...doc.gauges, ...doc.virtual].sort((a, b) => b.peak.q - a.peak.q), [doc]);
  const [sel, setSel] = useState(() => (doc.gauges.find(g => g.onMap) ?? sites[0])?.id);
  useEffect(() => { event.setFrame(k); }, [event, k]);
  useEffect(() => { event.show({ rain, gauges }); return () => event.hide(); }, [event, rain, gauges]);
  useEffect(() => {
    if (!play) return undefined;
    const id = setInterval(() => setK(i => (i + 1) % event.count), 180);
    return () => clearInterval(id);
  }, [play, event]);
  const t = frameTime(doc, k), { utc, pst } = timeLabels(t), win = windowAt(doc, t);
  const site = sites.find(s => s.id === sel);
  return (
    <div className="panel events-panel" aria-label="Events">
      <div className="eyebrow">{doc.title}</div>
      <div className="ev-time">
        <button className="ev-play" aria-label={play ? "Pause" : "Play"} aria-pressed={play} onClick={() => setPlay(p => !p)}>{play ? "❚❚" : "▶"}</button>
        <div><div className="mono">{pst}</div><div className="mono ev-utc">{utc}{win ? ` · ${win.label}` : ""}</div></div>
      </div>
      <input className="ev-slider" type="range" min="0" max={event.count - 1} value={k} aria-label="Event hour" onChange={e => { setPlay(false); setK(+e.target.value); }} />
      <Series values={doc.rain.domainMean} k={k} kind="bars" windows={doc.windows} doc={doc} label="Precipitation, domain mean" unit="mm/h" />
      {site && <Series values={site.q} k={k} kind="line" windows={doc.windows} doc={doc} label={site.name} unit="m³/s" />}
      <button className="tog" role="switch" aria-checked={rain} aria-label="Rain" onClick={() => setRain(v => !v)}>
        <span className="sw" /><span className="t">Rain<small>MRMS hourly precipitation, drops ∝ rate (full at 8 mm/h)</small></span>
      </button>
      <button className="tog" role="switch" aria-checked={gauges} aria-label="River gauges" onClick={() => setGauges(v => !v)}>
        <span className="sw" /><span className="t">River gauges<small>bar height = discharge / event peak</small></span>
      </button>
      <div className="ev-sites" role="list">
        {sites.map(s => (
          <button key={s.id} role="listitem" className={`ev-site${s.id === sel ? " on" : ""}`} onClick={() => setSel(s.id)}
            title={s.kind === "virtual" ? `seismic virtual gauge, NSE log Q ${s.nse}` : `USGS ${s.id}${s.recordEnds ? `, record ends ${s.recordEnds}` : ""}${s.onMap ? "" : ", off the map"}`}>
            <span className={`ev-dot ${s.kind}`} /><span className="ev-name">{s.name}{s.recordEnds ? " †" : ""}</span>
            <span className="mono">{s.q[k] == null ? "–" : Math.round(s.q[k])}</span><span className="mono ev-peak">{Math.round(s.peak.q)}</span>
          </button>
        ))}
      </div>
      <div className="msrc">
        m³/s now and at the event peak; † the record stops during the event. Blue: USGS gauges; amber: seismic virtual gauges (rating inverted from river
        noise, seis-hydro-2-sed). Precipitation is the MRMS liquid equivalent: rain and snow are not separated. Shaded: the pre-AR storm and three atmospheric-river pulses. {doc.note}{" "}
        Sources: {Object.entries(doc.sources).map(([key, s], i) => <span key={key}>{i ? ", " : ""}<a href={s.link} target="_blank" rel="noreferrer">{key}</a></span>)}.
      </div>
    </div>
  );
}
