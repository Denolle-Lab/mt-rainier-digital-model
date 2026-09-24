import { KIND_BY_KEY } from "../data/kinds.js";
import { fmtElev } from "../data/format.js";
import "./ui.css";

// Without WebGL there is no map: say so, and list the stations as a table.
export default function NoWebGL({ bundle }) {
  return (
    <div className="nowebgl">
      <p role="alert">This map needs WebGL, which this browser has turned off or doesn't support. The stations are listed below.</p>
      <table>
        <thead><tr><th>Site</th><th>Codes</th><th>Instruments</th><th>Elevation</th></tr></thead>
        <tbody>
          {bundle.stations.sites.map(s => (
            <tr key={s.id}><td>{s.name}</td><td className="mono">{s.codes.join(" ")}</td>
              <td>{s.kinds.map(k => KIND_BY_KEY[k].label).join(", ")}</td><td className="mono">{fmtElev(s.elev)}</td></tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
