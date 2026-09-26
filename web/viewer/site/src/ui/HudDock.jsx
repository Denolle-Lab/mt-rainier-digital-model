import "./ui.css";

// 16 px line icons, drawn in currentColor so they follow the button's text colour.
const ICONS = {
  layers: <><path d="M8 2 1.8 5.3 8 8.6l6.2-3.3z" /><path d="m1.8 8.2 6.2 3.3 6.2-3.3" /><path d="m1.8 11 6.2 3.3 6.2-3.3" /></>,
  view: <><path d="M1.3 8S3.8 3.5 8 3.5 14.7 8 14.7 8 12.2 12.5 8 12.5 1.3 8 1.3 8z" /><circle cx="8" cy="8" r="2.1" /></>,
  quakes: <><path d="M1 8h2.4l1.3-3.6 2 7.4 1.8-9.3 1.9 8.1 1.3-2.6H15" /></>,
  mass: <><path d="M1.5 14h13L6.5 3.5z" /><circle cx="11.2" cy="6.2" r="1.1" /><circle cx="12.9" cy="9.1" r=".8" /></>,
  sensors: <><path d="M8 2.2 13.2 12H2.8z" /><path d="M8 12v2.3M5.5 14.3h5" /></>,
  model: <><path d="M1.5 13.5 6 6l2.6 4 1.9-2.6 4 6.1z" /><path d="M1.5 13.5h13" /></>,
  legend: <><rect x="1.8" y="3" width="2.4" height="2.4" /><rect x="1.8" y="10.6" width="2.4" height="2.4" /><path d="M7 4.2h7.2M7 8h7.2M7 11.8h7.2M1.8 8h2.4" /></>,
  rain: <><path d="M4.5 9.5a2.8 2.8 0 0 1 .3-5.6 3.6 3.6 0 0 1 6.8 1 2.3 2.3 0 0 1-.1 4.6z" /><path d="M5.5 11.5l-.8 2M8.3 11.5l-.8 2M11 11.5l-.8 2" /></>,
  help: <><circle cx="8" cy="8" r="6.5" /><path d="M6.1 6.3a1.95 1.95 0 1 1 2.7 1.8c-.5.2-.8.6-.8 1.1v.7" /><circle cx="8" cy="11.6" r=".4" fill="currentColor" /></>,
};

// The top-right dock, as in the Cascadia atlas: one icon button per panel. A button toggles its panel, which stays
// open until that button is clicked again; open panels stack under the dock in the buttons' order. Every panel stays
// mounted while closed, so its switches keep their state (and the phone layout can still show it as a bottom sheet).
export default function HudDock({ items, open, onToggle }) {
  const pop = key => `hud-pop-${key}`;
  return (
    <div className="hud-dock">
      <div className="dock-bar">
        {items.map(({ key, label, icon }) => (
          <button key={key} className="panel dock-btn" aria-label={label} title={label}
            aria-expanded={open.has(key)} aria-controls={pop(key)} onClick={() => onToggle(key)}>
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round" aria-hidden="true">{ICONS[icon]}</svg>
          </button>
        ))}
      </div>
      <div className="dock-pops">
        {items.map(({ key, label, node }) => (
          <div key={key} id={pop(key)} className={`dock-pop${open.has(key) ? " open" : ""}`} role="group" aria-label={label}>{node}</div>
        ))}
      </div>
    </div>
  );
}
