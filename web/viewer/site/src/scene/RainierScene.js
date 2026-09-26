import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { approach, ease, isMoveKey, motionDuration, moveStep, orbitPose } from "./cameraMath.js";
import { decimate, gridGeometry } from "./gridGeometry.js";
import { deviceProfile } from "./device.js";
import { cutUniform, isUnder, terrainOrder } from "./groundControls.js";
import { makeGround } from "./ground.js";
import { PLACES, placePose, stationPose } from "./stationPose.js";
import { SummitLod } from "./summitLod.js";
import { terrainMaterial } from "./terrainMaterial.js";

const STYLE = { photo: 0, mono: 1, contours: 2 };
const BLANK = new THREE.DataTexture(new Uint8Array(4), 1, 1); BLANK.needsUpdate = true;

// Draw a loaded texture's image at most maxWidth wide (the phone profile's drape); returns the texture, unchanged
// when the browser has no 2D canvas or cannot draw the image (a larger drape beats no scene).
export function shrink(tex, maxWidth, doc = typeof document === "undefined" ? undefined : document) {
  const im = tex.image;
  if (!im || !(im.width > maxWidth) || !doc) return tex;
  try {
    const c = doc.createElement("canvas");
    c.width = maxWidth; c.height = Math.round((im.height * maxWidth) / im.width);
    const ctx = c.getContext("2d");
    if (!ctx) return tex;
    ctx.drawImage(im, 0, 0, c.width, c.height);
    tex.image = c; tex.needsUpdate = true;
  } catch {
    /* keep the full-size image */
  }
  return tex;
}

export class RainierScene {
  static async create(canvas, bundle) {
    const profile = deviceProfile();
    const photo = shrink(await new THREE.TextureLoader().loadAsync(bundle.terrain.imageUrl), profile.photoMaxWidth);
    return new RainierScene(canvas, bundle, photo, profile);
  }

  constructor(canvas, bundle, photo, profile = deviceProfile()) {
    this.bundle = bundle; this.held = new Set(); this.flight = null; this.materials = []; this.profile = profile;
    const r = (this.renderer = new THREE.WebGLRenderer({ canvas, antialias: profile.antialias, preserveDrawingBuffer: true }));
    r.setPixelRatio(Math.min(devicePixelRatio, profile.maxPixelRatio)); r.setSize(innerWidth, innerHeight);
    this.scene = new THREE.Scene(); this.scene.background = new THREE.Color("#121211");
    this.camera = new THREE.PerspectiveCamera(32, innerWidth / innerHeight, 0.1, 2000);
    this.scene.add(new THREE.HemisphereLight(0xdfe6ee, 0x2a2a28, 1.7));
    const sun = new THREE.DirectionalLight(0xffffff, 1.3); sun.position.set(-30, 40, -20); this.scene.add(sun);

    this.U = {
      clip: { value: new THREE.Vector4(0, 0, 1, 0) }, clipOn: { value: 0 }, alpha: { value: 1 }, under: { value: 0 },
      style: { value: 0 }, flat: { value: 0 }, hole: { value: new THREE.Vector4(1, -1, 1, -1) }, holeOn: { value: 0 },
      over: { value: BLANK }, overA: { value: 0 }, lines: { value: BLANK }, linesOn: { value: 0 }, oRect: { value: new THREE.Vector4(0, 0, 1, 1) },
    };
    this.targets = { style: 0, flat: 0 }; this.cut = { on: false, angle: 90, offset: 0 };
    const { meta, heights } = bundle.terrain;
    this.terrainMeta = meta;
    this.ground = makeGround(meta, heights);
    this.U.oRect.value.copy(this.ground.rect);   // model layers are textures on the same lon/lat box as the photo
    this._tex = new Map(); this._overOpacity = 0.8;

    photo.flipY = false; photo.colorSpace = THREE.NoColorSpace; photo.anisotropy = r.capabilities.getMaxAnisotropy(); photo.needsUpdate = true;
    const km = new Float32Array(heights.length); for (let i = 0; i < km.length; i++) km[i] = heights[i] / 1000;
    // the mesh may use every s-th sample (phones); heights for placing things on the ground stay full (this.ground)
    const d = decimate(km, meta.cols, meta.rows, profile.terrainStride), s = d.s;
    const g = gridGeometry(d.n, d.m, (c, rr) => [meta.x0 + (c * s + 0.5) * meta.dx, meta.z0 + (rr * s + 0.5) * meta.dz, meta.dx * s, meta.dz * s], d.heights,
      (c, rr) => [(c * s + 0.5) / meta.cols, (rr * s + 0.5) / meta.rows]);
    this.baseTerrain = new THREE.Mesh(g, this._material(photo, true));
    this.baseTerrain.frustumCulled = false;   // heights flatten in the shader for 2D
    this.scene.add(this.baseTerrain);

    const p = bundle.summit.patch;
    // the overview keeps 20 m under the summit tiles' edges, so no raster crack opens between the two meshes
    this.U.hole.value.set(p.west_km + 0.02, p.west_km + p.width_km - 0.02, p.north_km + 0.02, p.north_km + p.height_km - 0.02);
    this.summitGroup = new THREE.Group(); this.scene.add(this.summitGroup);
    this.lod = new SummitLod(bundle.summit, bundle.base, tex => this._material(tex, false), this.summitGroup,
      { inflight: profile.summitInflight, cap: profile.summitCap, stride: profile.summitStride,
        refine: profile.summitRefine, maxLevel: profile.summitMaxLevel });

    // Navigation, copied from the Cascadia atlas: drag moves; Ctrl/Cmd/Shift-drag rotates (OrbitControls swaps
    // PAN→ROTATE with a modifier); right-drag rotates. Rainier lets the camera go below the ground.
    const c = (this.controls = new OrbitControls(this.camera, canvas));
    c.enableDamping = true; c.dampingFactor = 0.08; c.screenSpacePanning = false; c.zoomToCursor = true;
    c.minPolarAngle = 0; c.maxPolarAngle = Math.PI; c.minDistance = 0.03; c.maxDistance = 220;
    c.mouseButtons = { LEFT: THREE.MOUSE.PAN, MIDDLE: THREE.MOUSE.DOLLY, RIGHT: THREE.MOUSE.ROTATE };
    c.touches = { ONE: THREE.TOUCH.PAN, TWO: THREE.TOUCH.DOLLY_ROTATE };
    c.addEventListener("start", () => { this.flight = null; });
    this._onContext = e => e.preventDefault();
    canvas.addEventListener("contextmenu", this._onContext);
    this._onKeyDown = e => { if (!isMoveKey(e)) return; e.preventDefault(); this.held.add(e.key); this.flight = null; };
    this._onKeyUp = e => (e.key === "Meta" ? this.held.clear() : this.held.delete(e.key));
    this._onBlur = () => this.held.clear();
    this._onResize = () => { r.setSize(innerWidth, innerHeight); this.camera.aspect = innerWidth / innerHeight; this.camera.updateProjectionMatrix(); this.layers?.resize(); this.onResize?.(); };
    addEventListener("keydown", this._onKeyDown); addEventListener("keyup", this._onKeyUp);
    addEventListener("blur", this._onBlur); addEventListener("resize", this._onResize);
    this._motion = matchMedia?.("(prefers-reduced-motion: reduce)");

    this.jumpTo("home");
    this.clock = new THREE.Clock(); this._v = new THREE.Vector3();
    this.frame = { dist: 0, under: false, finest: -1, flat: 0 };
    window.__rainier = this;   // test hook (e2e)
    this._raf = requestAnimationFrame(this._tick);
  }

  _material(map, hole) {
    const m = terrainMaterial(this.U, map, { hole });
    m.transparent = this.see > 0; m.depthWrite = !(this.see > 0);   // tiles that load later match the see-through setting
    this.materials.push(m); return m;
  }

  get reducedMotion() { return !!this._motion?.matches; }
  elevKm(x, z) { return this.ground.elevKm(x, z); }
  project(x, y, z) { const v = this._v.set(x, y, z).project(this.camera); return [((v.x + 1) / 2) * innerWidth, ((1 - v.y) / 2) * innerHeight, v.z]; }

  _pose(key) { return placePose(PLACES.find(p => p.key === key), (x, z) => this.elevKm(x, z)); }
  jumpTo(key) { const p = this._pose(key); this.camera.position.set(...p.pos); this.controls.target.set(...p.target); }
  flyTo(key) { const p = this._pose(key); this._fly(new THREE.Vector3(...p.pos), new THREE.Vector3(...p.target), 1800); }
  flyToSite(site) {
    const p = stationPose({ x: site.x, z: site.z, y: (this.elevKm(site.x, site.z) ?? site.elev / 1000) * (1 - this.U.flat.value) }, this.camera.position.toArray());
    this._fly(new THREE.Vector3(...p.pos), new THREE.Vector3(...p.target), 1800);
  }
  // Navigation pad: rotate / tilt / zoom about the current target, or turn north up.
  orbit(opts) {
    const t = this.controls.target, maxPol = this.controls.maxPolarAngle;
    const p = orbitPose(this.camera.position.toArray(), t.toArray(), opts, 0.02, Math.min(maxPol, Math.PI - 0.02));
    this._fly(new THREE.Vector3(...p), t.clone(), 350);
  }
  _fly(pos, target, dur) {
    this.flight = { t0: performance.now(), dur: motionDuration(dur, this.reducedMotion), fromPos: this.camera.position.clone(), fromTarget: this.controls.target.clone(), pos, target };
  }

  setStyle(s) { this.targets.style = STYLE[s]; }
  setSeeThrough(pct) {
    this.see = pct; this.U.alpha.value = 1 - pct / 100;
    for (const m of this.materials) { m.transparent = pct > 0; m.depthWrite = pct === 0; }
  }
  // Model surface layers (rainier3d): one draped at a time, plus the stream network. null clears.
  async _texture(url, nearest) {
    if (!this._tex.has(url)) {
      this._tex.set(url, new THREE.TextureLoader().loadAsync(url).then(t => {
        t.flipY = false; t.colorSpace = THREE.NoColorSpace; t.anisotropy = this.renderer.capabilities.getMaxAnisotropy();
        if (nearest) { t.magFilter = THREE.NearestFilter; }
        t.needsUpdate = true; return t;
      }));
    }
    return this._tex.get(url);
  }
  async setOverlay(url, { categorical = false } = {}) {
    this._overUrl = url;
    if (!url) { this.U.overA.value = 0; return; }
    const t = await this._texture(url, categorical);
    if (this._overUrl !== url) return;   // a later pick won
    this.U.over.value = t; this.U.overA.value = this._overOpacity;
  }
  setOverlayOpacity(a) { this._overOpacity = a; if (this._overUrl) this.U.overA.value = a; }
  async setStreams(url) {
    if (!url) { this.U.linesOn.value = 0; return; }
    this.U.lines.value = await this._texture(url, false); this.U.linesOn.value = 1;
  }
  // Ground point under a screen position: march the view ray against the overview heights, then bisect.
  groundAt(clientX, clientY) {
    const ray = new THREE.Raycaster(); ray.setFromCamera(new THREE.Vector2((clientX / innerWidth) * 2 - 1, -(clientY / innerHeight) * 2 + 1), this.camera);
    const { origin: o, direction: d } = ray.ray, flat = 1 - this.U.flat.value;
    const above = t => { const x = o.x + d.x * t, z = o.z + d.z * t, e = this.elevKm(x, z); return e == null ? null : o.y + d.y * t - e * flat; };
    const far = Math.min(400, this.camera.position.distanceTo(this.controls.target) * 8), n = 400;
    let t0 = 0, h0 = above(0);
    for (let i = 1; i <= n; i++) {
      const t = (far * i) / n, h = above(t);
      if (h != null && h0 != null && h0 > 0 && h <= 0) {
        let a = t0, b = t;
        for (let k = 0; k < 24; k++) { const m = (a + b) / 2, hm = above(m); if (hm != null && hm > 0) a = m; else b = m; }
        const x = o.x + d.x * b, z = o.z + d.z * b; return { x, z, elevKm: this.elevKm(x, z) };
      }
      if (h != null) { t0 = t; h0 = h; }
    }
    return null;
  }
  // The terrain cut is shared state: the ground panel and the subsurface section both set it and follow it.
  setCut({ on, angle, offset }) {
    this.cut = { on, angle, offset };
    this.U.clip.value.set(...cutUniform(angle, offset)); this.U.clipOn.value = on ? 1 : 0;
    for (const f of this._cutListeners ?? []) f(this.cut);
  }
  onCut(f) { (this._cutListeners ??= new Set()).add(f); return () => this._cutListeners.delete(f); }
  setView(v) {
    if (v === this._view) return;   // re-clicking the active view must not overwrite the saved tilt
    this._view = v;
    const to2d = v === "2d"; this.targets.flat = to2d ? 1 : 0;
    this.layers?.setVisibleAll(!to2d);   // earthquake layers and the block frame have no place on a flat map
    const sph = new THREE.Spherical().setFromVector3(this.camera.position.clone().sub(this.controls.target));
    if (to2d) this._savedPolar = sph.phi;
    sph.phi = to2d ? 0.001 : (this._savedPolar ?? 0.9);
    this.controls.minPolarAngle = 0; this.controls.maxPolarAngle = to2d ? 0.001 : Math.PI;
    // the target follows the ground: down to the flat map in 2D, back onto the terrain in 3D
    const t = this.controls.target.clone();
    t.y = to2d ? 0 : (this.elevKm(t.x, t.z) ?? 0);
    this._fly(t.clone().add(new THREE.Vector3().setFromSpherical(sph)), t, 900);
    this.onView?.(v);
  }

  _tick = () => {
    const now = performance.now(), dt = Math.min(this.clock.getDelta(), 0.05), f = this.flight;
    if (f) {
      const t = f.dur > 0 ? Math.min(1, (now - f.t0) / f.dur) : 1, k = ease(t);
      this.camera.position.lerpVectors(f.fromPos, f.pos, k); this.controls.target.lerpVectors(f.fromTarget, f.target, k);
      if (!f.target.equals(f.fromTarget)) this.camera.position.y += Math.sin(Math.PI * k) * f.fromPos.distanceTo(f.pos) * 0.15;
      if (t >= 1) this.flight = null;
    }
    if (this.held.size) {
      const d = moveStep(this.held, this.camera.position.toArray(), this.controls.target.toArray(), dt);
      this.camera.position.x += d[0]; this.camera.position.z += d[2];
      this.controls.target.x += d[0]; this.controls.target.z += d[2];
    }
    this.controls.update();
    const reduced = this.reducedMotion;
    for (const [key, speed] of [["flat", 5], ["style", 8]]) this.U[key].value = approach(this.U[key].value, this.targets[key], dt, speed, reduced);
    // the near plane follows the zoom, so both 1 m detail and the 60 km overview keep depth precision
    const dist = this.camera.position.distanceTo(this.controls.target);
    this.camera.near = THREE.MathUtils.clamp(dist * 0.004, 0.0004, 0.1); this.camera.updateProjectionMatrix();
    this.camera.updateMatrixWorld();   // overlays project with exactly this frame's camera
    const flat = this.U.flat.value, under = isUnder(this.camera.position.toArray(), (x, z) => this.elevKm(x, z), flat);
    this.U.under.value = under ? 1 : 0;
    const order = terrainOrder(under);
    this.baseTerrain.renderOrder = order;
    for (const m of this.summitGroup.children) m.renderOrder = order;
    const finest = this.lod.update(this.camera, flat);
    this.U.holeOn.value = this.lod.allRootsReady ? 1 : 0;
    this.frame = { dist, under, finest, flat, summitFailures: this.lod.failures };
    this.beforeRender?.(this);
    this.onFrame?.(this);
    this.renderer.render(this.scene, this.camera);
    this._raf = requestAnimationFrame(this._tick);
  };

  dispose() {
    cancelAnimationFrame(this._raf);
    removeEventListener("keydown", this._onKeyDown); removeEventListener("keyup", this._onKeyUp);
    removeEventListener("blur", this._onBlur); removeEventListener("resize", this._onResize);
    this.renderer.domElement.removeEventListener("contextmenu", this._onContext);
    this.lod.dispose(); this.controls.dispose(); this.renderer.dispose();
    if (window.__rainier === this) delete window.__rainier;
  }
}
