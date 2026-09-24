import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { approach, ease, isMoveKey, motionDuration, moveStep } from "./cameraMath.js";
import { gridGeometry } from "./gridGeometry.js";
import { makeGround } from "./ground.js";
import { PLACES, placePose, stationPose } from "./stationPose.js";
import { SummitLod } from "./summitLod.js";
import { terrainMaterial } from "./terrainMaterial.js";

const STYLE = { photo: 0, mono: 1, contours: 2 };

export class RainierScene {
  static async create(canvas, bundle) {
    const photo = await new THREE.TextureLoader().loadAsync(bundle.terrain.imageUrl);
    return new RainierScene(canvas, bundle, photo);
  }

  constructor(canvas, bundle, photo) {
    this.bundle = bundle; this.held = new Set(); this.flight = null; this.materials = [];
    const r = (this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true, preserveDrawingBuffer: true }));
    r.setPixelRatio(Math.min(devicePixelRatio, 2)); r.setSize(innerWidth, innerHeight);
    this.scene = new THREE.Scene(); this.scene.background = new THREE.Color("#121211");
    this.camera = new THREE.PerspectiveCamera(32, innerWidth / innerHeight, 0.1, 2000);
    this.scene.add(new THREE.HemisphereLight(0xdfe6ee, 0x2a2a28, 1.7));
    const sun = new THREE.DirectionalLight(0xffffff, 1.3); sun.position.set(-30, 40, -20); this.scene.add(sun);

    this.U = {
      clip: { value: new THREE.Vector4(0, 0, 1, 0) }, clipOn: { value: 0 }, alpha: { value: 1 }, under: { value: 0 },
      style: { value: 0 }, flat: { value: 0 }, hole: { value: new THREE.Vector4(1, -1, 1, -1) }, holeOn: { value: 0 },
    };
    this.targets = { style: 0, flat: 0 };
    const { meta, heights } = bundle.terrain;
    this.ground = makeGround(meta, heights);

    photo.flipY = false; photo.colorSpace = THREE.NoColorSpace; photo.anisotropy = r.capabilities.getMaxAnisotropy(); photo.needsUpdate = true;
    const km = new Float32Array(heights.length); for (let i = 0; i < km.length; i++) km[i] = heights[i] / 1000;
    const g = gridGeometry(meta.cols, meta.rows, (c, rr) => [meta.x0 + (c + 0.5) * meta.dx, meta.z0 + (rr + 0.5) * meta.dz, meta.dx, meta.dz], km,
      (c, rr) => [(c + 0.5) / meta.cols, (rr + 0.5) / meta.rows]);
    this.baseTerrain = new THREE.Mesh(g, this._material(photo, true));
    this.baseTerrain.frustumCulled = false;   // heights flatten in the shader for 2D
    this.scene.add(this.baseTerrain);

    const p = bundle.summit.patch;
    this.U.hole.value.set(p.west_km + 0.004, p.west_km + p.width_km - 0.004, p.north_km + 0.004, p.north_km + p.height_km - 0.004);
    this.summitGroup = new THREE.Group(); this.scene.add(this.summitGroup);
    this.lod = new SummitLod(bundle.summit, bundle.base, tex => this._material(tex, false), this.summitGroup);

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
    this._onResize = () => { r.setSize(innerWidth, innerHeight); this.camera.aspect = innerWidth / innerHeight; this.camera.updateProjectionMatrix(); this.onResize?.(); };
    addEventListener("keydown", this._onKeyDown); addEventListener("keyup", this._onKeyUp);
    addEventListener("blur", this._onBlur); addEventListener("resize", this._onResize);
    this._motion = matchMedia?.("(prefers-reduced-motion: reduce)");

    this.jumpTo("home");
    this.clock = new THREE.Clock(); this._v = new THREE.Vector3();
    this.frame = { dist: 0, under: false, finest: -1, flat: 0 };
    window.__rainier = this;   // test hook (e2e)
    this._raf = requestAnimationFrame(this._tick);
  }

  _material(map, hole) { const m = terrainMaterial(this.U, map, { hole }); this.materials.push(m); return m; }

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
  _fly(pos, target, dur) {
    this.flight = { t0: performance.now(), dur: motionDuration(dur, this.reducedMotion), fromPos: this.camera.position.clone(), fromTarget: this.controls.target.clone(), pos, target };
  }

  setStyle(s) { this.targets.style = STYLE[s]; }
  setView(v) {
    if (v === this._view) return;   // re-clicking the active view must not overwrite the saved tilt
    this._view = v;
    const to2d = v === "2d"; this.targets.flat = to2d ? 1 : 0;
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
    const cp = this.camera.position, flat = this.U.flat.value;
    const under = cp.y < (this.elevKm(cp.x, cp.z) ?? 0) * (1 - flat);
    this.U.under.value = under ? 1 : 0;
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
