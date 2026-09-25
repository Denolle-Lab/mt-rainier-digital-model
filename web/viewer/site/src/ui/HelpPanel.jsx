import { useState } from "react";
import "./ui.css";

const KEY = "rainier-viewer-help-seen";
export const helpSeen = () => { try { return localStorage.getItem(KEY) === "1"; } catch { return true; } };
export const markHelpSeen = () => { try { localStorage.setItem(KEY, "1"); } catch { /* storage blocked: the hint shows again next time */ } };

const ROWS = {
  Mouse: [["Move", "drag"], ["Rotate and tilt", "right-drag, or hold Ctrl, ⌘ or Shift and drag"], ["Zoom", "scroll wheel (zooms toward the pointer)"]],
  Trackpad: [["Move", "click and drag (or three-finger drag)"], ["Rotate and tilt", "hold ⌘ (or Ctrl) and drag, or drag with a two-finger click"], ["Zoom", "pinch, or scroll with two fingers"]],
  Touch: [["Move", "drag with one finger"], ["Rotate and tilt", "twist or drag with two fingers"], ["Zoom", "pinch"]],
};

// Help, in the dock: how to move the map, the keyboard shortcuts, and the network counts that used to sit in the title.
export default function HelpPanel({ bundle }) {
  const touch = typeof matchMedia === "function" && matchMedia("(pointer: coarse)").matches;
  const { counts, sites } = bundle.stations;
  const kinds = new Set(sites.flatMap(s => s.kinds)).size;
  return (
    <section className="panel helppanel" aria-label="Help">
      <div className="eyebrow">How to move</div>
      {(touch ? ["Touch"] : ["Mouse", "Trackpad"]).map(s => (
        <div key={s} className="hc-set">
          <div className="hc-dev">{s}</div>
          {ROWS[s].map(([what, how]) => <div key={what} className="hc-row"><b>{what}</b><span>{how}</span></div>)}
        </div>
      ))}
      <div className="hc-note">
        The buttons at the bottom rotate, tilt and zoom, and <b>N</b> turns north up.{touch ? "" : <> Arrow keys glide; <kbd>G</kbd> <kbd>S</kbd> <kbd>D</kbd> toggle the earthquake layers, <kbd>X</kbd> the cut, <kbd>T</kbd> stations, <kbd>W</kbd> streams.</>}
        {" "}To look under the ground, tilt below the horizon, use <b>From below</b> in Go to, or open the <b>Surface model</b> panel
        and turn on <b>Section on the cut</b> or <b>Depth slice</b>.
      </div>
      <div className="stats">
        <div><b className="mono" data-testid="n-stations">{counts.stations}</b><span>Stations</span></div>
        <div><b className="mono" data-testid="n-sites">{counts.sitesOnMap}</b><span>Sites on map</span></div>
        <div><b className="mono" data-testid="n-kinds">{kinds}</b><span>Instrument kinds</span></div>
      </div>
    </section>
  );
}

// First visit only: one line above the navigation buttons instead of a card over the map. `hidden` retires it once
// help has been opened another way (the nav pad's ? button).
export function HelpHint({ onHelp, hidden = false }) {
  const [show, setShow] = useState(() => !helpSeen());
  if (!show || hidden) return null;
  const done = () => { markHelpSeen(); setShow(false); };
  const touch = typeof matchMedia === "function" && matchMedia("(pointer: coarse)").matches;
  return (
    <div className="panel helphint" role="status">
      <span>{touch ? "Drag to move · two fingers to rotate · pinch to zoom" : "Drag to move · right-drag to rotate · scroll to zoom"}</span>
      <button className="more" aria-label="More help" onClick={() => { done(); onHelp(); }}>?</button>
      <button className="icon" aria-label="Dismiss" onClick={done}>×</button>
    </div>
  );
}
