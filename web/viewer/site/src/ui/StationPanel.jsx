import { KIND_BY_KEY } from "../data/kinds.js";
import { fmtElev } from "../data/format.js";
import Glyph from "./Glyph.jsx";
import { instrumentLine, operators } from "./instruments.js";
import "./ui.css";

const FDSN = "https://service.earthscope.org/fdsnws";

export function links(st, now = new Date()) {
  const [net, sta] = st.code.split(".");
  const out = [
    { label: "EarthScope station page", url: `https://ds.iris.edu/mda/${net}/${sta}` },
    { label: "StationXML (instrument response)", url: `${FDSN}/station/1/query?network=${net}&station=${sta}&level=response` },
  ];
  if (net === "UW") out.push({ label: "PNSN station page", url: `https://pnsn.org/seismograms/${net}/${sta}` });
  if (net === "CC") out.push({ label: "USGS Cascades Volcano Observatory", url: "https://www.usgs.gov/volcanoes/mount-rainier/science" });
  const chans = st.instruments.flatMap(i => i.channels);
  const cha = chans.find(c => c.endsWith("Z")) ?? chans[0];
  const iso = d => d.toISOString().slice(0, 19);
  out.push({ label: `Last hour of ${cha} (miniSEED)`, url: `${FDSN}/dataselect/1/query?net=${net}&sta=${sta}&loc=*&cha=${cha}&starttime=${iso(new Date(now - 3600e3))}&endtime=${iso(now)}` });
  return out;
}

export default function StationPanel({ site, bundle, onClose, onFly, notes = {} }) {
  return (
    <aside className="panel station-panel" id="panel" aria-label={`${site.name} station details`}>
      <div className="sp-head">
        <div>
          <h2>{site.name}</h2>
          <div className="sp-sub">{operators(site).join(" · ")} · {fmtElev(site.elev)}</div>
        </div>
        <button className="icon" aria-label="Close" onClick={onClose}>×</button>
      </div>
      <div className="sp-kinds">{site.kinds.map(k => <span key={k}><Glyph glyph={KIND_BY_KEY[k].glyph} color={KIND_BY_KEY[k].color} />{KIND_BY_KEY[k].label}</span>)}</div>
      {site.onMap ? <button className="fly" onClick={() => onFly(site)}>Fly to {site.id.split(".")[1]}</button>
        : <p className="sp-note">This station is outside the map area, {Math.round(Math.hypot(site.x, site.z))} km from the summit.</p>}
      {site.stations.map(st => (
        <section key={st.code} className="sp-station">
          <div className="sp-code"><b className="mono">{st.code}</b><span>{st.siteName}</span></div>
          <div className="sp-meta">Running since {st.since.slice(0, 4)} · {fmtElev(st.elev)}{st.depth > 1 ? ` · sensor ${Math.round(st.depth)} m below the surface` : ""}</div>
          <ul className="sp-inst">{st.instruments.map(i => <li key={i.channels.join()}>{instrumentLine(i)}</li>)}</ul>
          {notes[st.code] && <p className="sp-note sp-stnote">{notes[st.code]}</p>}
          <ul className="sp-links">{links(st).map(l => <li key={l.label}><a href={l.url} target="_blank" rel="noreferrer">{l.label}</a></li>)}</ul>
        </section>
      ))}
      <p className="sp-foot">Active per EarthScope station metadata as of {bundle.stations.asOf}: the channels have no end date. This is not a live health check.</p>
    </aside>
  );
}
