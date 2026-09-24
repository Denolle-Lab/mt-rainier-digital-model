import Search from "./Search.jsx";
import "./ui.css";

export default function Header({ bundle, detail, onPick }) {
  const { counts, sites } = bundle.stations;
  const kinds = new Set(sites.flatMap(s => s.kinds)).size;
  return (
    <header className="panel header">
      <h1>Mount Rainier Seismic Atlas</h1>
      <p>Active seismic stations on and around the volcano, on USGS terrain with 1 m lidar at the summit.</p>
      <div className="stats">
        <div><b className="mono" data-testid="n-stations">{counts.stations}</b><span>Stations</span></div>
        <div><b className="mono" data-testid="n-sites">{counts.sitesOnMap}</b><span>Sites on map</span></div>
        <div><b className="mono" data-testid="n-kinds">{kinds}</b><span>Instrument kinds</span></div>
      </div>
      <div className="detail"><span>Summit terrain detail</span><span className="mono">{detail}</span></div>
      <Search bundle={bundle} onPick={onPick} />
    </header>
  );
}
