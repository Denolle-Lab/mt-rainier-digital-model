import { useEffect } from "react";
import "./ui.css";

// Phone layout (max-width 700px): the desktop panels become bottom sheets, one open at a time, chosen here.
// The open sheet is written to <html data-sheet>, which the phone CSS in ui.css reads.
export const SHEETS = [["layers", "Layers"], ["model", "Model"], ["legend", "Legend"], ["goto", "Go to"]];

export default function MobileDock({ sheet, onSheet, hasModel }) {
  useEffect(() => {
    document.documentElement.dataset.sheet = sheet ?? "";
    return () => { delete document.documentElement.dataset.sheet; };
  }, [sheet]);
  return (
    <nav className="dock" aria-label="Panels">
      {SHEETS.filter(([k]) => k !== "model" || hasModel).map(([k, label]) => (
        <button key={k} aria-pressed={sheet === k} onClick={() => onSheet(sheet === k ? null : k)}>{label}</button>
      ))}
    </nav>
  );
}
