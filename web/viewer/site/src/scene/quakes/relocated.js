import * as THREE from "three";
import { countAboveGround, selectCatalog, shiftSegments } from "../../data/relocated.js";

// The relocated catalogue as coloured points (one catalogue at a time) and optional 1D -> 3D shift lines. Points are
// drawn wherever the catalogue puts them, above the ground too: that is the point of comparing catalogues. They follow
// the 2D flattening and the terrain cut like the other layers.
const VERT = `
  attribute float mag; uniform float uDpr, uFlat, uClipOn; uniform vec4 uClip;
  void main() {
    vec3 p = position; p.y *= 1.0 - uFlat;
    bool cut = uClipOn > 0.5 && dot(p.xz, uClip.xz) > uClip.w;
    gl_PointSize = (2.5 + 1.6 * clamp(mag, 0.0, 4.0)) * uDpr;
    gl_Position = cut ? vec4(2.0, 2.0, 2.0, 1.0) : projectionMatrix * modelViewMatrix * vec4(p, 1.0);
  }`;
const FRAG = `
  uniform vec3 uColor;
  void main() {
    float r = length(gl_PointCoord - 0.5);
    if (r > 0.5) discard;
    gl_FragColor = vec4(r > 0.4 ? vec3(0.06) : uColor, 0.95);
  }`;
const LINE_VERT = `
  uniform float uFlat, uClipOn; uniform vec4 uClip; varying float vCut;
  void main() {
    vec3 p = position; p.y *= 1.0 - uFlat;
    vCut = uClipOn > 0.5 && dot(p.xz, uClip.xz) > uClip.w ? 1.0 : 0.0;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(p, 1.0);
  }`;
const LINE_FRAG = `
  varying float vCut;
  void main() { if (vCut > 0.5) discard; gl_FragColor = vec4(0.95, 0.95, 0.9, 0.55); }`;

export class RelocatedQuakes {
  constructor(rs, reloc) {
    this.rs = rs; this.reloc = reloc; this.state = null; this.shown = 0; this.above = 0;
    const U = { uFlat: rs.U.flat, uClipOn: rs.U.clipOn, uClip: rs.U.clip };
    this.pointU = { ...U, uDpr: { value: Math.min(devicePixelRatio, 2) }, uColor: { value: new THREE.Color() } };
    this.points = new THREE.Points(new THREE.BufferGeometry(),
      new THREE.ShaderMaterial({ uniforms: this.pointU, vertexShader: VERT, fragmentShader: FRAG, transparent: true, depthWrite: false }));
    this.lines = new THREE.LineSegments(new THREE.BufferGeometry(),
      new THREE.ShaderMaterial({ uniforms: U, vertexShader: LINE_VERT, fragmentShader: LINE_FRAG, transparent: true, depthWrite: false }));
    for (const o of [this.points, this.lines]) { o.frustumCulled = false; o.renderOrder = 7; o.visible = false; rs.scene.add(o); }
  }

  // state: { on, catalog, lines, minQuality } (DEFAULT_RELOCATED)
  set(state) {
    const s = this.state = { ...state }, cat = this.reloc.meta.catalogs[s.catalog];
    const sel = selectCatalog(this.reloc, s.catalog, s.minQuality);
    const g = this.points.geometry;
    g.setAttribute("position", new THREE.BufferAttribute(sel.pos, 3));
    g.setAttribute("mag", new THREE.BufferAttribute(sel.mag, 1));
    g.computeBoundingSphere();
    this.pointU.uColor.value.set(cat?.color ?? "#ffffff");
    this.lines.geometry.setAttribute("position", new THREE.BufferAttribute(shiftSegments(this.reloc, "1d", "3d", s.minQuality), 3));
    this.points.visible = !!s.on; this.lines.visible = !!(s.on && s.lines);
    this.shown = sel.n; this.above = countAboveGround(sel.pos, (x, z) => this.rs.elevKm(x, z));
  }

  dispose() {
    for (const o of [this.points, this.lines]) { this.rs.scene.remove(o); o.geometry.dispose(); o.material.dispose(); }
  }
}
