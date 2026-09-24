import { useEffect } from "react";
import "./ui.css";

const KEY = "rainier-viewer-help-seen";
export const helpSeen = () => { try { return localStorage.getItem(KEY) === "1"; } catch { return true; } };
const markSeen = () => { try { localStorage.setItem(KEY, "1"); } catch { /* storage blocked: show again next time */ } };

const ROWS = {
  Mouse: [["Move", "drag"], ["Rotate and tilt", "right-drag, or hold Ctrl, ⌘ or Shift and drag"], ["Zoom", "scroll wheel (zooms toward the pointer)"]],
  Trackpad: [["Move", "click and drag (or three-finger drag)"], ["Rotate and tilt", "hold ⌘ (or Ctrl) and drag, or drag with a two-finger click"], ["Zoom", "pinch, or scroll with two fingers"]],
  Touch: [["Move", "drag with one finger"], ["Rotate and tilt", "twist or drag with two fingers"], ["Zoom", "pinch"]],
};

export default function HelpCard({ onClose }) {
  const touch = typeof matchMedia === "function" && matchMedia("(pointer: coarse)").matches;
  const sets = touch ? ["Touch"] : ["Mouse", "Trackpad"];
  const close = () => { markSeen(); onClose(); };
  useEffect(() => {
    const k = e => { if (e.key === "Escape") close(); };
    addEventListener("keydown", k); return () => removeEventListener("keydown", k);
  });
  return (
    <div className="helpcard-wrap" onClick={close}>
      <section className="panel helpcard" role="dialog" aria-label="How to move" onClick={e => e.stopPropagation()}>
        <div className="sp-head"><h2>How to move</h2><button className="icon" aria-label="Close" onClick={close}>×</button></div>
        {sets.map(s => (
          <div key={s} className="hc-set">
            <div className="eyebrow">{s}</div>
            {ROWS[s].map(([what, how]) => <div key={what} className="hc-row"><b>{what}</b><span>{how}</span></div>)}
          </div>
        ))}
        <div className="hc-note">
          The buttons at the bottom rotate, tilt and zoom, and <b>N</b> turns north up.{touch ? "" : " Arrow keys glide."}
          {" "}To look under the ground, tilt below the horizon, use <b>From below</b> in Go to, or open
          {touch ? " Model" : " the Surface model panel"} and turn on <b>Section on the cut</b> or <b>Depth slice</b> to show the
          velocity model.
        </div>
        <button className="fly" onClick={close}>Got it</button>
      </section>
    </div>
  );
}
