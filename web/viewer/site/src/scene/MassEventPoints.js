import * as THREE from "three";
import { isSeismic, passesMass } from "../data/massEvents.js";
import { occluded } from "./occlusion.js";

// Mass-movement events as GPU points on the ground, coloured by class. The marker is a downward chevron, a shape no
// other layer uses (earthquakes and sensors are discs): material moving downslope. Seismically recorded events are
// larger with a light rim, mapped landslides (placed at their crown) are smaller with a dark rim. They follow the 2D
// flattening and the terrain cut; picking is done in screen space.
const VERT = `
  attribute vec3 color; attribute float big; attribute float on;
  uniform float uSize, uFlat, uClipOn; uniform vec4 uClip;
  varying vec3 vColor; varying float vBig;
  void main() {
    vColor = color; vBig = big;
    vec3 p = position; p.y *= 1.0 - uFlat;
    bool cut = uClipOn > 0.5 && dot(p.xz, uClip.xz) > uClip.w;
    vec4 mv = modelViewMatrix * vec4(p, 1.0);
    mv.xyz *= 1.0 - min(0.02, 0.3 / max(length(mv.xyz), 0.001));   // as the sensors: keep slopes from hiding it
    gl_Position = (on < 0.5 || cut) ? vec4(2.0, 2.0, 2.0, 1.0) : projectionMatrix * mv;
    gl_PointSize = uSize * (big > 0.5 ? 1.6 : 1.0);
  }`;
const FRAG = `
  varying vec3 vColor; varying float vBig;
  // signed distance to a triangle (negative inside), after Inigo Quilez
  float sdTri(vec2 p, vec2 a, vec2 b, vec2 c) {
    vec2 e0 = b - a, e1 = c - b, e2 = a - c, v0 = p - a, v1 = p - b, v2 = p - c;
    vec2 q0 = v0 - e0 * clamp(dot(v0, e0) / dot(e0, e0), 0.0, 1.0);
    vec2 q1 = v1 - e1 * clamp(dot(v1, e1) / dot(e1, e1), 0.0, 1.0);
    vec2 q2 = v2 - e2 * clamp(dot(v2, e2) / dot(e2, e2), 0.0, 1.0);
    float s = sign(e0.x * e2.y - e0.y * e2.x);
    vec2 d = min(min(vec2(dot(q0, q0), s * (v0.x * e0.y - v0.y * e0.x)),
                     vec2(dot(q1, q1), s * (v1.x * e1.y - v1.y * e1.x))),
                     vec2(dot(q2, q2), s * (v2.x * e2.y - v2.y * e2.x)));
    return -sqrt(d.x) * sign(d.y);
  }
  void main() {
    vec2 p = gl_PointCoord;   // y points down the sprite
    float outer = sdTri(p, vec2(0.03, 0.10), vec2(0.97, 0.10), vec2(0.5, 0.95));
    float notch = sdTri(p, vec2(0.30, -0.02), vec2(0.70, -0.02), vec2(0.5, 0.36));
    float sd = max(outer, -notch);   // the chevron: the triangle minus the notch at its top
    if (sd > 0.0) discard;
    vec3 rim = vBig > 0.5 ? vec3(0.96, 0.96, 0.94) : vec3(0.07);
    gl_FragColor = vec4(sd > -0.05 ? rim : vColor, 1.0);
  }`;

// Height of a point: the highest overview-grid ground within 60 m, plus 15 m. The overview grid (~35-50 m cells)
// sits below the 1 m summit lidar on cliffs, where many of these events start; the local maximum keeps them visible.
const RING = [[0, 0], [0.06, 0], [-0.06, 0], [0, 0.06], [0, -0.06], [0.042, 0.042], [-0.042, 0.042], [0.042, -0.042], [-0.042, -0.042]];
export function groundTopKm(elevKm, x, z) {
  let top = -Infinity;
  for (const [dx, dz] of RING) { const h = elevKm(x + dx, z + dz); if (h != null && h > top) top = h; }
  return top + 0.015;
}

export class MassEventPoints {
  constructor(rs, doc) {
    const color = Object.fromEntries(doc.classes.map(c => [c.key, c.color]));
    const events = doc.events.filter(e => rs.elevKm(e.x, e.z) != null);
    this.rs = rs; this.events = events;
    const n = events.length, pos = new Float32Array(n * 3), col = new Float32Array(n * 3);
    const big = new Float32Array(n), on = new Float32Array(n);
    const c = new THREE.Color();
    events.forEach((e, i) => {
      pos.set([e.x, groundTopKm((x, z) => rs.elevKm(x, z), e.x, e.z), e.z], i * 3);
      c.set(color[e.cls] ?? "#a8a39a"); col.set([c.r, c.g, c.b], i * 3);
      big[i] = isSeismic(e) ? 1 : 0;
    });
    this.yKm = i => pos[i * 3 + 1];
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    g.setAttribute("color", new THREE.BufferAttribute(col, 3));
    g.setAttribute("big", new THREE.BufferAttribute(big, 1));
    g.setAttribute("on", (this.onAttr = new THREE.BufferAttribute(on, 1)));
    const U = { uSize: { value: 12 * Math.min(devicePixelRatio, 2) }, uFlat: rs.U.flat, uClipOn: rs.U.clipOn, uClip: rs.U.clip };
    this.points = new THREE.Points(g, new THREE.ShaderMaterial({ uniforms: U, vertexShader: VERT, fragmentShader: FRAG, transparent: true }));
    this.points.frustumCulled = false; this.points.renderOrder = 6;
    rs.scene.add(this.points);
  }

  setFilter(f) {
    const on = this.onAttr.array;
    let shown = 0;
    this.events.forEach((e, i) => { on[i] = passesMass(e, f) ? 1 : 0; shown += on[i]; });
    this.onAttr.needsUpdate = true;
    this.shown = shown;
  }

  // nearest visible, unoccluded event within `px` of a screen position; seismic events win ties
  pick(cx, cy, px = 9) {
    const rs = this.rs, flat = rs.U.flat.value, on = this.onAttr.array, cam = rs.camera.position.toArray();
    const c = rs.U.clip.value, clipOn = rs.U.clipOn.value > 0.5;
    let best = null, bd = px * px;
    for (let i = 0; i < this.events.length; i++) {
      if (!on[i]) continue;
      const e = this.events[i];
      if (clipOn && e.x * c.x + e.z * c.z > c.w) continue;
      const [x, y, z] = rs.project(e.x, this.yKm(i) * (1 - flat), e.z);
      if (z > 1) continue;
      const d = (x - cx) ** 2 + (y - cy) ** 2 - (isSeismic(e) ? 16 : 0);
      if (d < bd) { bd = d; best = i; }
    }
    if (best == null) return null;
    const e = this.events[best];
    if (occluded(cam, [e.x, this.yKm(best) * (1 - flat), e.z], (x, z) => (rs.elevKm(x, z) ?? -1) * (1 - flat))) return null;
    return e;
  }

  dispose() {
    this.rs.scene.remove(this.points);
    this.points.geometry.dispose(); this.points.material.dispose();
  }
}
