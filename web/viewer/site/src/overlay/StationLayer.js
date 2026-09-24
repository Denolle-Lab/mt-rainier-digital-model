import { occluded } from "../scene/occlusion.js";
import { place } from "./labels.js";
import { ringSize, ringSvg } from "./ring.js";
import "./overlay.css";

// HTML station markers over the canvas, projected every frame with that frame's camera. A marker behind terrain
// fades to 12% and loses its label and hover; all markers hide below ground and on the cut-away side.
export class StationLayer {
  constructor(container, bundle, scene, handlers = {}) {
    this.c = container; this.scene = scene; this.h = handlers;
    this.items = bundle.stations.sites.filter(s => s.onMap).map(site => {
      const size = ringSize(site.kinds.length), d = document.createElement("div");
      d.className = `station${site.major ? " major" : ""}`;
      d.innerHTML = ringSvg(site.kinds, size) + `<div class="name">${site.id.split(".")[1]}</div>`;
      d.setAttribute("role", "button"); d.tabIndex = 0; d.dataset.id = site.id;
      d.setAttribute("aria-label", `${site.name}, ${site.codes.join(", ")}`);
      d.onmouseenter = ev => handlers.onHover?.(site, ev); d.onmousemove = ev => handlers.onHover?.(site, ev);
      d.onmouseleave = () => handlers.onHover?.(site, null);
      d.onclick = () => handlers.onClick?.(site);
      d.onkeydown = ev => { if (ev.key === "Enter") handlers.onClick?.(site); };
      container.appendChild(d);
      return { site, d, name: d.querySelector(".name"), size };
    });
  }

  setVisible(on) { this.hiddenAll = !on; }

  setSelected(id) { for (const it of this.items) it.d.classList.toggle("selected", it.site.id === id); }

  update() {
    const sc = this.scene, { flat, under } = sc.frame, U = sc.U, cam = sc.camera.position.toArray();
    const ground = (x, z) => (sc.elevKm(x, z) ?? -1) * (1 - flat);
    const labels = [];
    for (const it of this.items) {
      const { x: px, z: pz } = it.site, py = ground(px, pz) + 0.01;
      const [x, y, z] = sc.project(px, py, pz);
      const cutAway = U.clipOn.value > 0.5 && px * U.clip.value.x + pz * U.clip.value.z > U.clip.value.w;
      const onScreen = !this.hiddenAll && !under && !cutAway && z < 1 && x > -40 && x < innerWidth + 40 && y > -40 && y < innerHeight + 40;
      const hidden = onScreen && occluded(cam, [px, py, pz], ground);
      const vis = onScreen && !hidden;
      if (!vis && this._hovered === it.site.id) this.h.onHover?.(it.site, null);
      Object.assign(it.d.style, { left: `${x}px`, top: `${y}px`, opacity: onScreen ? (hidden ? 0.12 : 1) : 0, pointerEvents: vis ? "auto" : "none" });
      if (vis) labels.push({ id: it.site.id, x: x - it.size / 2, y, w: it.size + 12 + it.name.textContent.length * 7.2, h: 18, priority: it.site.major ? 2 : 1 });
    }
    const shown = place(labels);
    for (const it of this.items) it.name.style.opacity = shown.has(it.site.id) ? 1 : 0;
  }

  dispose() { this.c.innerHTML = ""; }
}
