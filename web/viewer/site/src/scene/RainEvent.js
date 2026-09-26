import * as THREE from "three";

// One event in the scene: falling rain whose density follows the hourly MRMS rain under each drop, and a bar at
// every river gauge whose height follows its discharge (as a fraction of its event peak). The rain frame is a
// small R8 texture on the overview lon/lat box, the same box as the terrain, so uv = scene (x, z) / box.
const RAIN_VERT = `
  attribute vec2 seed; attribute float ground; attribute float tip;
  uniform sampler2D uRain; uniform vec4 uBox; uniform float uTime, uFull, uScale, uFlat, uTop, uLen;
  varying float vA, vTip;
  void main() {
    vec2 uv = (position.xz - uBox.xy) / uBox.zw;
    float q = texture2D(uRain, uv).r * 255.0;
    float mm = q > 254.5 ? 0.0 : q * uScale;
    float on = step(seed.y, clamp(mm / uFull, 0.0, 1.0)) * step(0.05, mm);
    float fall = fract(seed.x - uTime * 0.35);                    // 0 at the ground, 1 at the top of the column
    float y = ground + uTop * fall + tip * uLen;
    vec3 p = vec3(position.x, y * (1.0 - uFlat), position.z);
    vA = on * smoothstep(0.0, 0.08, fall); vTip = tip;
    gl_Position = on < 0.5 ? vec4(2.0, 2.0, 2.0, 1.0) : projectionMatrix * modelViewMatrix * vec4(p, 1.0);
  }`;
const RAIN_FRAG = `
  varying float vA, vTip;
  void main() { gl_FragColor = vec4(0.78, 0.86, 0.96, vA * mix(0.75, 0.0, vTip)); }`;

export class RainEvent {
  constructor(rs, event, { drops = 24000 } = {}) {
    Object.assign(this, { rs, doc: event.doc, frames: event.frames, k: 0, rainOn: true, gaugesOn: true });
    const { width: w, height: h } = this.doc.rain, m = rs.terrainMeta;
    this.tex = new THREE.DataTexture(new Uint8Array(w * h), w, h, THREE.RedFormat, THREE.UnsignedByteType);
    this.tex.minFilter = this.tex.magFilter = THREE.LinearFilter; this.tex.unpackAlignment = 1; this.tex.flipY = false;
    this.U = {
      uRain: { value: this.tex }, uBox: { value: new THREE.Vector4(m.x0, m.z0, m.cols * m.dx, m.rows * m.dz) },
      uTime: { value: 0 }, uFull: { value: 8.0 }, uScale: { value: this.doc.rain.scale }, uFlat: rs.U.flat,
      uTop: { value: 2.5 }, uLen: { value: 0.12 },
    };
    // drops at random places on the terrain box; each is a short segment (tip 0 at the bottom, 1 at the top)
    const pos = [], seed = [], ground = [], tip = [];
    let rnd = 12345; const rand = () => ((rnd = (rnd * 1103515245 + 12345) % 2147483648) / 2147483648);
    for (let i = 0; i < drops; i++) {
      const x = m.x0 + rand() * m.cols * m.dx, z = m.z0 + rand() * m.rows * m.dz, g = rs.elevKm(x, z);
      if (g == null) continue;
      const s0 = rand(), s1 = rand();
      for (const t of [0, 1]) { pos.push(x, 0, z); seed.push(s0, s1); ground.push(g); tip.push(t); }
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
    geo.setAttribute("seed", new THREE.Float32BufferAttribute(seed, 2));
    geo.setAttribute("ground", new THREE.Float32BufferAttribute(ground, 1));
    geo.setAttribute("tip", new THREE.Float32BufferAttribute(tip, 1));
    this.rain = new THREE.LineSegments(geo, new THREE.ShaderMaterial({
      uniforms: this.U, vertexShader: RAIN_VERT, fragmentShader: RAIN_FRAG, transparent: true, depthWrite: false,
    }));
    this.rain.frustumCulled = false; this.rain.renderOrder = 5; this.rain.visible = false;
    rs.scene.add(this.rain);

    // gauges: a thin bar per station on the map, 3 km at its event peak
    this.bars = new THREE.Group(); this.bars.visible = false; rs.scene.add(this.bars);
    this.sites = [...this.doc.gauges, ...this.doc.virtual].filter(s => s.onMap && rs.elevKm(s.x, s.z) != null);
    const barGeo = new THREE.CylinderGeometry(0.09, 0.09, 1, 10).translate(0, 0.5, 0);
    this.barGeo = barGeo;
    for (const s of this.sites) {
      const mat = new THREE.MeshBasicMaterial({ color: s.kind === "virtual" ? 0xe8a33d : 0x4c9be8, transparent: true, opacity: 0.9 });
      const b = new THREE.Mesh(barGeo, mat);
      b.position.set(s.x, rs.elevKm(s.x, s.z), s.z); b.userData.site = s; b.renderOrder = 6;
      this.bars.add(b);
    }
    this.setFrame(0);
  }

  get count() { return this.doc.frames.count; }

  setFrame(k) {
    this.k = Math.max(0, Math.min(this.count - 1, k));
    const { width: w, height: h } = this.doc.rain;
    this.tex.image.data = this.frames.subarray(this.k * w * h, (this.k + 1) * w * h); this.tex.needsUpdate = true;
    for (const b of this.bars.children) {
      const s = b.userData.site, q = s.q[this.k], f = q == null || !s.peak.q ? 0 : q / s.peak.q;
      b.scale.set(1, Math.max(0.002, 3 * f), 1); b.visible = q != null;
    }
  }

  show({ rain = this.rainOn, gauges = this.gaugesOn } = {}) {
    this.rainOn = rain; this.gaugesOn = gauges;
    this.rain.visible = rain; this.bars.visible = gauges;
  }

  hide() { this.rain.visible = false; this.bars.visible = false; }

  update(dt) {
    this.U.uTime.value += dt;
    const flat = 1 - this.rs.U.flat.value;
    for (const b of this.bars.children) b.position.y = (this.rs.elevKm(b.position.x, b.position.z) ?? 0) * flat;
  }

  dispose() {
    this.rs.scene.remove(this.rain); this.rain.geometry.dispose(); this.rain.material.dispose(); this.tex.dispose();
    this.rs.scene.remove(this.bars); this.barGeo.dispose(); for (const b of this.bars.children) b.material.dispose();
  }
}
