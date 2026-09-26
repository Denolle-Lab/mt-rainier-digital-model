import { useEffect } from "react";
import "./ui.css";

// Phone layout (max-width 700px): the desktop panels become bottom sheets, one open at a time, chosen here.
// The open sheet is written to <html data-sheet>, which the phone CSS in ui.css reads. Help has no tab: the nav pad's
// ? button opens it as a sheet (App sets sheet "help").
export const SHEETS = [["view", "View"], ["quakes", "Quakes"], ["mass", "Mass"], ["sensors", "Sensors"],
  ["model", "Models"], ["events", "Events"], ["goto", "Go to"]];

export default function MobileDock({ sheet, onSheet, has = {} }) {
  useEffect(() => {
    document.documentElement.dataset.sheet = sheet ?? "";
    return () => { delete document.documentElement.dataset.sheet; };
  }, [sheet]);
  return (
    <nav className="dock" aria-label="Panels">
      {SHEETS.filter(([k]) => has[k] !== false).map(([k, label]) => (
        <button key={k} aria-pressed={sheet === k} onClick={() => onSheet(sheet === k ? null : k)}>{label}</button>
      ))}
    </nav>
  );
}
