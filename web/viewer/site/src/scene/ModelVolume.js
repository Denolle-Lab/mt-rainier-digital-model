import * as THREE from "three";
import { nearestLevel, segmentPositions } from "./strainBars.js";

// The rainier3d volume below ground: a vertical section on the terrain-cut plane and a horizontal depth slice.
// Both sample one 3D texture per property (atlas/model/volume.json) in the fragment shader: scene (x, z) km map to
// the model's UTM grid by quadratic fits (< 0.001 cell error) and elevation maps to depth linearly. Everything
// above the ground is discarded with the same ground test as the earthquake layers. Strain properties carry
// orientation bars (volume.json "bars"), drawn on the depth slice at the nearest exported level.
const VERT = `
  varying vec3 vPos;
  void main() { vec4 wp = modelMatrix * vec4(position, 1.0); vPos = wp.xyz; gl_Position = projectionMatrix * viewMatrix * wp; }`;
const FRAG = `
  precision highp sampler3D;
  uniform sampler3D uVol; uniform sampler2D uLut;
  uniform vec3 uPuA, uPuB, uPvA, uPvB; uniform float uZTop, uZSpan, uOpacity, uFlat;
  varying vec3 vPos;
  float poly(vec3 a, vec3 b, vec2 p) { return a.x + a.y * p.x + a.z * p.y + b.x * p.x * p.x + b.y * p.x * p.y + b.z * p.y * p.y; }
  void main() {
    if (uFlat > 0.5) discard;
    vec2 p = vPos.xz;
    vec3 t = vec3(poly(uPuA, uPuB, p), poly(uPvA, uPvB, p), (uZTop - vPos.y) / uZSpan);
    if (any(lessThan(t, vec3(0.0))) || any(greaterThan(t, vec3(1.0)))) discard;
    if (vPos.y > groundKm(p)) discard;
    float q = texture(uVol, t).r;
    if (q > 0.998) discard;   // 255: no data (air for the units cube)
    gl_FragColor = vec4(texture2D(uLut, vec2((q * 255.0 + 0.5) / 256.0, 0.5)).rgb, uOpacity);
  }`;

const BAR_FRAG = `
  uniform vec3 uColor; varying vec3 vPos;
  void main() { if (vPos.y > groundKm(vPos.xz)) discard; gl_FragColor = vec4(uColor, 0.9); }`;
const rsGroundUniforms = rs => ({ ...rs.ground.uniforms });

export class ModelVolume {
  constructor(rs, meta, base) {
    this.rs = rs; this.meta = meta; this.base = base; this.cache = new Map(); this.key = null;
    const g = meta.grid, [u, v] = [meta.uv_poly.u, meta.uv_poly.v];
    this.zTop = g.z_top_m / 1000; this.zBot = this.zTop - (g.nz * g.dz_m) / 1000;
    this.U = {
      uVol: { value: null }, uLut: { value: null }, uOpacity: { value: 1 }, uFlat: rs.U.flat,
      uPuA: { value: new THREE.Vector3(u[0], u[1], u[2]) }, uPuB: { value: new THREE.Vector3(u[3], u[4], u[5]) },
      uPvA: { value: new THREE.Vector3(v[0], v[1], v[2]) }, uPvB: { value: new THREE.Vector3(v[3], v[4], v[5]) },
      uZTop: { value: this.zTop }, uZSpan: { value: this.zTop - this.zBot }, ...rs.ground.uniforms,
    };
    const mat = () => new THREE.ShaderMaterial({ uniforms: this.U, vertexShader: VERT, fragmentShader: rs.ground.glsl + FRAG,
      side: THREE.DoubleSide, transparent: false });
    const span = 120;   // km, larger than the model box in any direction
    this.section = new THREE.Mesh(new THREE.PlaneGeometry(span, this.zTop - this.zBot), mat());
    this.slice = new THREE.Mesh(new THREE.PlaneGeometry(span, span), mat());
    this.slice.rotation.x = -Math.PI / 2;
    for (const m of [this.section, this.slice]) { m.visible = false; m.frustumCulled = false; m.renderOrder = 3; rs.scene.add(m); }
    this.want = { section: false, slice: false, sliceKm: -2 };
    this.bars = null;   // { levels_km, meshes: { tectonic: [LineSegments per level], load: [...] } }
    if (meta.bars) fetch(base + meta.bars).then(r => (r.ok ? r.json() : null)).then(j => j && this._buildBars(j)).catch(() => {});
  }

  _buildBars(j) {
    const mat = new THREE.ShaderMaterial({ uniforms: { ...rsGroundUniforms(this.rs), uColor: { value: new THREE.Color("#111111") } },
      vertexShader: VERT, fragmentShader: this.rs.ground.glsl + BAR_FRAG, transparent: true, depthWrite: false });
    const meshes = {};
    for (const kind of ["tectonic", "load"]) {
      meshes[kind] = (j[kind] || []).map(flat => {
        const geo = new THREE.BufferGeometry();
        geo.setAttribute("position", new THREE.BufferAttribute(segmentPositions(flat, 0), 3));
        const m = new THREE.LineSegments(geo, mat);
        m.visible = false; m.frustumCulled = false; m.renderOrder = 4; this.rs.scene.add(m);
        return m;
      });
    }
    this.bars = { levels: j.levels_km, meshes, mat };
    this._apply();
  }

  async _load(key) {
    if (!this.cache.has(key)) {
      const v = this.meta.vars[key], g = this.meta.grid;
      this.cache.set(key, fetch(this.base + v.file).then(r => (r.ok ? r.arrayBuffer() : null)).then(buf => {
        if (!buf) return null;
        const vol = new THREE.Data3DTexture(new Uint8Array(buf), g.nx, g.ny, g.nz);
        vol.format = THREE.RedFormat; vol.type = THREE.UnsignedByteType; vol.unpackAlignment = 1;
        vol.minFilter = vol.magFilter = v.kind === "categorical" ? THREE.NearestFilter : THREE.LinearFilter;
        vol.needsUpdate = true;
        const lut = new Uint8Array(256 * 4);
        v.lut.forEach((c, i) => lut.set([c[0], c[1], c[2], 255], i * 4));
        const lt = new THREE.DataTexture(lut, 256, 1); lt.colorSpace = THREE.NoColorSpace;
        lt.minFilter = lt.magFilter = THREE.NearestFilter; lt.needsUpdate = true;
        return { vol, lut: lt };
      }).catch(() => null));
    }
    const got = await this.cache.get(key);
    if (!got) this.cache.delete(key);
    return got;
  }

  async setVar(key) {
    this.key = key;
    if (!key) { this._apply(); return; }
    const t = await this._load(key);
    if (this.key !== key) return;   // a later pick won
    if (t) { this.U.uVol.value = t.vol; this.U.uLut.value = t.lut; }
    this._apply();
  }
  setSection(on) { this.want.section = on; this._apply(); }
  setSlice(on, km = this.want.sliceKm) { this.want.slice = on; this.want.sliceKm = km; this._apply(); }
  _apply() {
    const ready = !!(this.key && this.U.uVol.value);
    this.section.visible = ready && this.want.section && this.rs.U.clipOn.value > 0.5;
    this.slice.visible = ready && this.want.slice;
    this.slice.position.y = this.want.sliceKm;
    if (this.bars) {
      const kind = this.key && this.meta.vars[this.key]?.bars;
      const lev = nearestLevel(this.bars.levels, this.want.sliceKm);
      for (const [k, list] of Object.entries(this.bars.meshes)) {
        list.forEach((m, i) => {
          m.visible = this.slice.visible && k === kind && i === lev;
          if (m.visible) m.position.y = this.want.sliceKm + 0.02;   // just above the slice plane
        });
      }
    }
  }

  // every frame: the section follows the terrain cut (removed side where dot(xz, n) > offset)
  update() {
    const c = this.rs.U.clip.value;
    this.section.rotation.y = Math.atan2(c.x, c.z);
    this.section.position.set(c.x * c.w, (this.zTop + this.zBot) / 2, c.z * c.w);
    this._apply();
  }

  dispose() {
    for (const m of [this.section, this.slice]) { this.rs.scene.remove(m); m.geometry.dispose(); m.material.dispose(); }
    if (this.bars) {
      for (const list of Object.values(this.bars.meshes)) for (const m of list) { this.rs.scene.remove(m); m.geometry.dispose(); }
      this.bars.mat.dispose();
    }
  }
}

export async function loadVolumeMeta(modelBase) {
  try { const r = await fetch(`${modelBase}volume.json`); return r.ok ? await r.json() : null; } catch { return null; }
}
