import * as THREE from "three";
import { makeCloud } from "./cloud.js";
import { makeDots } from "./dots.js";
import { makeFrame } from "./frame.js";
import { makeShells } from "./shells.js";

export const DEFAULT_LAYERS = { cloud: true, shells: true, dots: false };

// The earthquake layers and the block frame, attached to a RainierScene (or anything with scene, camera, renderer,
// ground and terrainMeta). Tick labels are HTML in `overlay` when one is given.
export class QuakeLayers {
  constructor(rs, quakes, overlay = null) {
    this.rs = rs; this.visible = true; this.layerState = { ...DEFAULT_LAYERS };
    const n = quakes.records.length / 4, pos = new Float32Array(n * 3), mag = new Float32Array(n), grd = new Float32Array(n);
    for (let i = 0; i < n; i++) {
      const [x, y, z, m] = quakes.records.subarray(i * 4, i * 4 + 4);
      pos.set([x, y, z], i * 3); mag[i] = m; grd[i] = rs.ground.elevKm(x, z) ?? 0;
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    geo.setAttribute("mag", new THREE.BufferAttribute(mag, 1));
    geo.setAttribute("ground", new THREE.BufferAttribute(grd, 1));
    this.pxScale = { value: 0 }; this.resize();
    this.cloud = makeCloud(geo, { pxScale: this.pxScale, ground: rs.ground, camera: rs.camera });
    this.dots = makeDots(geo, { dpr: rs.renderer.getPixelRatio() });
    this.shells = makeShells(quakes.records, rs.ground);
    const t = rs.terrainMeta;
    this.frame = makeFrame({ xmin: t.x0 + t.dx / 2, xmax: t.x0 + (t.cols - 0.5) * t.dx, zmin: t.z0 + t.dz / 2, zmax: t.z0 + (t.rows - 0.5) * t.dz, bottom: -20 });
    rs.scene.add(this.shells, this.cloud, this.dots, this.frame.group);
    this.tickEls = overlay ? this.frame.ticks.map(tk => {
      const el = document.createElement("div"); el.className = "tick"; el.textContent = tk.label; overlay.appendChild(el); return el;
    }) : [];
    this._apply();
  }

  get state() { return { ...this.layerState }; }
  set(layer, on) { this.layerState[layer] = on; this._apply(); }
  setVisibleAll(on) { this.visible = on; this._apply(); }
  resize() { this.pxScale.value = this.rs.renderer.domElement.height / (2 * Math.tan(THREE.MathUtils.degToRad(this.rs.camera.fov) / 2)); }

  _apply() {
    const v = this.visible, s = this.layerState;
    this.cloud.visible = v && s.cloud; this.dots.visible = v && s.dots; this.shells.visible = v && s.shells;
    this.frame.group.visible = v;
    for (const el of this.tickEls) el.style.display = v ? "" : "none";
  }

  update(project) {
    if (!this.visible) return;
    this.frame.ticks.forEach((tk, i) => {
      const el = this.tickEls[i]; if (!el) return;
      const [x, y, z] = project(tk.pos.x, tk.pos.y, tk.pos.z);
      Object.assign(el.style, { left: `${x}px`, top: `${y}px`, opacity: z < 1 ? 1 : 0 });
    });
  }

  dispose() {
    this.rs.scene.remove(this.shells, this.cloud, this.dots, this.frame.group);
    this.cloud.geometry.dispose(); this.cloud.material.dispose(); this.dots.material.dispose();
    for (const el of this.tickEls) el.remove();
  }
}
