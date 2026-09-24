import { useMemo, useState } from "react";
import { searchStations } from "../data/search.js";

export default function Search({ bundle, onPick }) {
  const [q, setQ] = useState(""), [active, setActive] = useState(0);
  const results = useMemo(() => searchStations(bundle, q), [bundle, q]);
  const pick = r => { onPick(bundle.siteById[r.id]); setQ(""); };
  return (
    <div className="search">
      <input type="search" placeholder="Search stations" value={q} aria-label="Search stations"
        onChange={e => { setQ(e.target.value); setActive(0); }}
        onKeyDown={e => {
          if (e.key === "ArrowDown") { e.preventDefault(); setActive(a => Math.min(a + 1, results.length - 1)); }
          if (e.key === "ArrowUp") { e.preventDefault(); setActive(a => Math.max(a - 1, 0)); }
          if (e.key === "Enter" && results[active]) pick(results[active]);
          if (e.key === "Escape") setQ("");
        }} />
      {results.length > 0 && (
        <ul role="listbox">
          {results.map((r, i) => (
            <li key={r.id} role="option" aria-selected={i === active} onMouseDown={() => pick(r)}>
              <span>{r.title}</span><span className="sub mono">{r.sub}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
