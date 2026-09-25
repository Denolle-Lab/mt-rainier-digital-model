import Search from "./Search.jsx";
import "./ui.css";

// A slim title bar: the title, the summit detail level, and search. The counts live in the Help panel.
export default function Header({ bundle, detail, onPick }) {
  return (
    <header className="panel header">
      <div className="title-row">
        <h1>Mount Rainier Seismic Atlas</h1>
        <span className="detail-tag mono" title="Summit terrain detail">{detail}</span>
      </div>
      <Search bundle={bundle} onPick={onPick} />
    </header>
  );
}
