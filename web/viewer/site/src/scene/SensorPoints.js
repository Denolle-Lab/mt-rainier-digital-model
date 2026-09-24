import * as THREE from "three";
import { KIND_BY_KEY } from "../data/kinds.js";
import { passes } from "../data/sensors.js";
import { occluded } from "./occlusion.js";

// Every inventory site that is not a station marker, as one GPU point each: colour by instrument kind, filled
// for permanent networks, a ring for temporary ones, faded for past deployments. Plus the DAS fiber as a line on
// the ground. Both follow the 2D flattening and the terrain cut; hover picking is done in screen space.
const PT_VERT = `
  attribute vec3 color; attribute float temp; attribute float past; attribute float on;
  uniform float uSize, uFlat, uClipOn; uniform vec4 uClip;
  varying vec3 vColor; varying float vTemp, vPast;
  void main() {
    vColor = color; vTemp = temp; vPast = past;
    vec3 p = position; p.y *= 1.0 - uFlat;
    bool cut = uClipOn > 0.5 && dot(p.xz, uClip.xz) > uClip.w;
    vec4 mv = modelViewMatrix * vec4(p, 1.0);
    // pull the sprite toward the camera along its own line of sight (same screen position), so a steep slope
    // does not hide its lower half: at most 300 m, and at most 2 % of the distance
    mv.xyz *= 1.0 - min(0.02, 0.3 / max(length(mv.xyz), 0.001));
    gl_Position = (on < 0.5 || cut) ? vec4(2.0, 2.0, 2.0, 1.0) : projectionMatrix * mv;
    gl_PointSize = uSize * (temp > 0.5 ? 1.15 : 1.0);
  }`;
const PT_FRAG = `
  varying vec3 vColor; varying float vTemp, vPast;
  void main() {
    float r = length(gl_PointCoord - 0.5);
    if (r > 0.5) discard;
    vec3 c = vColor, light = vec3(0.96, 0.96, 0.94), dark = vec3(0.07);
    if (vTemp > 0.5) {                        // temporary: coloured ring, dark inside, light outer rim
      if (r < 0.17) discard;
      c = r < 0.23 ? dark : (r > 0.40 ? light : vColor);
    } else {                                  // permanent: filled disc with a light rim
      c = r > 0.38 ? light : vColor;
    }
    gl_FragColor = vec4(c, vPast > 0.5 ? 0.45 : 1.0);
  }`;
const LINE_VERT = `
  uniform float uFlat; varying vec3 vPos;
  void main() { vec3 p = position; p.y *= 1.0 - uFlat; vPos = p; gl_Position = projectionMatrix * modelViewMatrix * vec4(p, 1.0); }`;
const LINE_FRAG = `
  uniform float uClipOn; uniform vec4 uClip; varying vec3 vPos;
  void main() { if (uClipOn > 0.5 && dot(vPos.xz, uClip.xz) > uClip.w) discard; gl_FragColor = vec4(0.96, 0.96, 0.94, 1.0); }`;

export class SensorPoints {
  constructor(rs, sites, das) {
    this.rs = rs; this.sites = sites; this.hover = null;
    const n = sites.length, pos = new Float32Array(n * 3), col = new Float32Array(n * 3);
    const temp = new Float32Array(n), past = new Float32Array(n), on = new Float32Array(n).fill(1);
    const c = new THREE.Color();
    sites.forEach((s, i) => {
      const y = (rs.elevKm(s.x, s.z) ?? (s.elev ?? 0) / 1000) + 0.015;
      pos.set([s.x, y, s.z], i * 3);
      c.set(KIND_BY_KEY[s.kinds[0]]?.color ?? "#8b8980"); col.set([c.r, c.g, c.b], i * 3);
      temp[i] = s.temporary ? 1 : 0; past[i] = s.status === "operating" ? 0 : 1;
    });
    this.yKm = i => pos[i * 3 + 1];
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    g.setAttribute("color", new THREE.BufferAttribute(col, 3));
    g.setAttribute("temp", new THREE.BufferAttribute(temp, 1));
    g.setAttribute("past", new THREE.BufferAttribute(past, 1));
    g.setAttribute("on", (this.onAttr = new THREE.BufferAttribute(on, 1)));
    const U = { uSize: { value: 12 * Math.min(devicePixelRatio, 2) }, uFlat: rs.U.flat, uClipOn: rs.U.clipOn, uClip: rs.U.clip };
    this.points = new THREE.Points(g, new THREE.ShaderMaterial({ uniforms: U, vertexShader: PT_VERT, fragmentShader: PT_FRAG, transparent: true }));
    this.points.frustumCulled = false; this.points.renderOrder = 6;
    rs.scene.add(this.points);

    this.fiber = new THREE.Group();
    const lm = new THREE.ShaderMaterial({ uniforms: { uFlat: rs.U.flat, uClipOn: rs.U.clipOn, uClip: rs.U.clip },
      vertexShader: LINE_VERT, fragmentShader: LINE_FRAG });
    for (const seg of das?.segments ?? []) {
      if (seg.length < 2) continue;
      const pts = seg.map(([x, z]) => new THREE.Vector3(x, (rs.elevKm(x, z) ?? 0) + 0.008, z));
      const tube = new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), Math.max(8, pts.length * 3), 0.012, 5, false);
      const m = new THREE.Mesh(tube, lm); m.frustumCulled = false; m.renderOrder = 5; this.fiber.add(m);
    }
    rs.scene.add(this.fiber);
    this.das = das;
  }

  setFilter(f) {
    const on = this.onAttr.array;
    this.sites.forEach((s, i) => { on[i] = passes(s, f) ? 1 : 0; });
    this.onAttr.needsUpdate = true;
    this.fiber.visible = !!this.das && f.temporary && (!f.kinds || f.kinds.has("das"));
    this.filter = f;
  }

  // nearest visible, unoccluded point within `px` of a screen position
  pick(cx, cy, px = 10) {
    const rs = this.rs, flat = rs.U.flat.value, on = this.onAttr.array, cam = rs.camera.position.toArray();
    const c = rs.U.clip.value, clipOn = rs.U.clipOn.value > 0.5;
    let best = null, bd = px * px;
    for (let i = 0; i < this.sites.length; i++) {
      if (!on[i]) continue;
      const s = this.sites[i];
      if (clipOn && s.x * c.x + s.z * c.z > c.w) continue;
      const [x, y, z] = rs.project(s.x, this.yKm(i) * (1 - flat), s.z);
      if (z > 1) continue;
      const d = (x - cx) ** 2 + (y - cy) ** 2;
      if (d < bd) { bd = d; best = i; }
    }
    if (best == null) return null;
    const s = this.sites[best];
    if (occluded(cam, [s.x, this.yKm(best) * (1 - flat), s.z], (x, z) => (rs.elevKm(x, z) ?? -1) * (1 - flat))) return null;
    return s;
  }

  dispose() {
    this.rs.scene.remove(this.points, this.fiber);
    this.points.geometry.dispose(); this.points.material.dispose();
    for (const m of this.fiber.children) m.geometry.dispose();
  }
}
