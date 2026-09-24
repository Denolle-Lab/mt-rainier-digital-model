// Underground 3D view (three.js): see-through terrain, the terrain cut along the active section,
// vertical section curtains, a horizontal depth slice, seismicity at depth, sensors and the DAS fiber.
// Units: km, origin at the domain centre, z up. Property, sections and slice depth follow the atlas panel.
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

const $ = (s) => document.querySelector(s);
const DEPTH_STOPS = [[0, [253, 231, 37]], [10, [53, 183, 121]], [20, [49, 104, 142]], [30, [68, 1, 84]]];
let R = null;

function depthColor(d) {
  for (let i = 1; i < DEPTH_STOPS.length; i++) {
    const [d1, c1] = DEPTH_STOPS[i], [d0, c0] = DEPTH_STOPS[i - 1];
    if (d <= d1 || i === DEPTH_STOPS.length - 1) {
      const t = Math.min(1, Math.max(0, (d - d0) / (d1 - d0)));
      return new THREE.Color(...c0.map((c, k) => (c + t * (c1[k] - c)) / 255));
    }
  }
}

async function build() {
  const meta = await Sub.init(), s = Sub.surf(), b = meta.surface.bounds;
  const xc = (b[0] + b[2]) / 2, yc = (b[1] + b[3]) / 2;
  const K = (x, y) => [(x - xc) / 1000, (y - yc) / 1000];
  const host = $("#ug-canvas");
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
  renderer.setPixelRatio(Math.min(2, window.devicePixelRatio));
  renderer.setSize(host.clientWidth, host.clientHeight);
  renderer.localClippingEnabled = true;
  renderer.setClearColor(0x07090c);
  host.appendChild(renderer.domElement);
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(40, host.clientWidth / host.clientHeight, 0.05, 2000);
  camera.up.set(0, 0, 1);
  const [sx, sy] = Sub.utm(...window.atlasData.S.summit);
  const [tx, ty] = K(sx, sy);
  camera.position.set(tx - 45, ty - 55, 38);
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.target.set(tx, ty, -2);
  controls.update();
  scene.add(new THREE.AmbientLight(0xffffff, 0.75));
  const sun = new THREE.DirectionalLight(0xffffff, 0.9);
  sun.position.set(-30, 40, 60);
  scene.add(sun);

  // terrain (200 m vertices from the 100 m surface grid)
  const st = 2, nx = Math.floor((s.nx - 1) / st) + 1, ny = Math.floor((s.ny - 1) / st) + 1;
  const pos = new Float32Array(nx * ny * 3), uv = new Float32Array(nx * ny * 2), base = new Float32Array(nx * ny);
  for (let j = 0; j < ny; j++) for (let i = 0; i < nx; i++) {
    const n = j * nx + i, gi = i * st, gj = j * st;
    const [x, y] = K(s.x0 + gi * s.dx, s.y0 + gj * s.dx);
    base[n] = s.elev[gj * s.nx + gi] / 1000;
    pos.set([x, y, base[n]], 3 * n);
    uv.set([gi / (s.nx - 1), gj / (s.ny - 1)], 2 * n);
  }
  const idx = [];
  for (let j = 0; j < ny - 1; j++) for (let i = 0; i < nx - 1; i++) {
    const a = j * nx + i, b2 = a + 1, c = a + nx, d = c + 1;
    idx.push(a, b2, d, a, d, c);
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
  geo.setAttribute("uv", new THREE.BufferAttribute(uv, 2));
  geo.setIndex(idx);
  geo.computeVertexNormals();
  const loader = new THREE.TextureLoader();
  const tex = {
    units: loader.load("data/model/tex_units.png"),
    ice: loader.load("data/model/tex_ice.png"),
  };
  if (meta.surface.textures.includes("i432")) tex.i432 = await compositeI432();
  Object.values(tex).forEach((t) => { t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 4; });
  const terrainMat = new THREE.MeshLambertMaterial({ map: tex.units, transparent: true, opacity: 0.55,
    side: THREE.DoubleSide, depthWrite: false });
  const terrain = new THREE.Mesh(geo, terrainMat);
  terrain.renderOrder = 2;
  scene.add(terrain);

  // box outline of the model volume
  const zb = -20;
  const box = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry((b[2] - b[0]) / 1000, (b[3] - b[1]) / 1000, 1)),
    new THREE.LineBasicMaterial({ color: 0x3a4250 }));
  scene.add(box);

  // seismicity
  const evs = window.atlasData.events.features;
  const sphere = new THREE.SphereGeometry(1, 10, 8);
  const evMesh = new THREE.InstancedMesh(sphere, new THREE.MeshLambertMaterial(), evs.length);
  const evPos = evs.map((f) => {
    const [x, y] = K(...Sub.utm(...f.geometry.coordinates));
    return [x, y, -f.properties.depth, 0.06 + 0.05 * Math.max(0, f.properties.mag)];
  });
  evs.forEach((f, i) => evMesh.setColorAt(i, depthColor(f.properties.depth)));
  scene.add(evMesh);

  // operating sensors (points at the surface) and the fiber
  const sites = window.atlasData.sites.features.filter((f) => f.properties.status === "operating");
  const sp = new Float32Array(sites.length * 3), sc = new Float32Array(sites.length * 3), sBase = [];
  sites.forEach((f, i) => {
    const [ux, uy] = Sub.utm(...f.geometry.coordinates), [x, y] = K(ux, uy);
    const z = Sub.surfaceAt(ux, uy) / 1000 + 0.06;
    sBase.push(z); sp.set([x, y, z], 3 * i);
    sc.set(new THREE.Color(f.properties.color).toArray(), 3 * i);
  });
  const sGeo = new THREE.BufferGeometry();
  sGeo.setAttribute("position", new THREE.BufferAttribute(sp, 3));
  sGeo.setAttribute("color", new THREE.BufferAttribute(sc, 3));
  const sensors = new THREE.Points(sGeo, new THREE.PointsMaterial({ size: 6, sizeAttenuation: false, vertexColors: true }));
  scene.add(sensors);
  const ch = window.atlasData.dasCh.features;
  const fp = new Float32Array(ch.length * 3), fBase = [];
  ch.forEach((f, i) => {
    const [x, y] = K(...Sub.utm(...f.geometry.coordinates));
    fBase.push((f.properties.elev || 0) / 1000 + 0.02); fp.set([x, y, fBase[i]], 3 * i);
  });
  const fGeo = new THREE.BufferGeometry();
  fGeo.setAttribute("position", new THREE.BufferAttribute(fp, 3));
  const fiber = new THREE.Line(fGeo, new THREE.LineBasicMaterial({ color: 0xffffff }));
  scene.add(fiber);

  const R_ = { renderer, scene, camera, controls, terrain, terrainMat, tex, geo, base, box, zb, evMesh, evPos,
    sensors, sBase, fiber, fBase, K, sections: [], slice: null, vex: 1.5, open: false };
  window.addEventListener("resize", () => {
    renderer.setSize(host.clientWidth, host.clientHeight);
    camera.aspect = host.clientWidth / host.clientHeight; camera.updateProjectionMatrix();
  });
  wire(R_);
  return R_;
}

async function compositeI432() {
  const [u, g] = await Promise.all(["data/model/tex_units.png", "data/model/tex_i432.webp"].map((src) =>
    new Promise((ok) => { const im = new Image(); im.onload = () => ok(im); im.src = src; })));
  const c = document.createElement("canvas");
  c.width = g.width; c.height = g.height;
  const x = c.getContext("2d");
  x.drawImage(u, 0, 0, c.width, c.height);
  x.drawImage(g, 0, 0);
  return new THREE.CanvasTexture(c);
}

function applyVex(R_) {
  const v = R_.vex, p = R_.geo.attributes.position;
  for (let n = 0; n < R_.base.length; n++) p.setZ(n, R_.base[n] * v);
  p.needsUpdate = true; R_.geo.computeVertexNormals();
  const m = new THREE.Matrix4();
  R_.evPos.forEach(([x, y, z, r], i) => { m.makeScale(r, r, r).setPosition(x, y, z * v); R_.evMesh.setMatrixAt(i, m); });
  R_.evMesh.instanceMatrix.needsUpdate = true;
  const sp = R_.sensors.geometry.attributes.position;
  R_.sBase.forEach((z, i) => sp.setZ(i, z * v)); sp.needsUpdate = true;
  const fp = R_.fiber.geometry.attributes.position;
  R_.fBase.forEach((z, i) => fp.setZ(i, z * v)); fp.needsUpdate = true;
  const zt = 4.4, zb = R_.zb;
  R_.box.scale.set(1, 1, (zt - zb) * v); R_.box.position.z = ((zt + zb) / 2) * v;
  R_.sections.forEach((ms) => { ms.scale.y = v; ms.position.z = ms.userData.zmid * v; });
  if (R_.slice) R_.slice.position.z = R_.slice.userData.z * v;
}

async function refresh() {
  if (!R) return;
  const { state, subName } = window.atlasData, name = subName();
  // sections
  R.sections.forEach((m) => { R.scene.remove(m); m.geometry.dispose(); m.material.map.dispose(); m.material.dispose(); });
  R.sections = [];
  for (const sec of state.sections) {
    const r = await Sub.section(name, sec.A, sec.B, { zmin: state.zmin, width: 1400, height: 700 });
    const t = new THREE.CanvasTexture(r.canvas);
    t.colorSpace = THREE.SRGBColorSpace;
    const h = (r.zmax - r.zmin) / 1000, len = r.len / 1000;
    const mesh = new THREE.Mesh(new THREE.PlaneGeometry(len, h),
      new THREE.MeshBasicMaterial({ map: t, transparent: true, side: THREE.DoubleSide, opacity: sec === state.active ? 1 : 0.85 }));
    const [ax, ay] = R.K(r.xa, r.ya), [bx, by] = R.K(r.xb, r.yb);
    mesh.rotation.order = "ZXY";
    mesh.rotation.set(Math.PI / 2, 0, Math.atan2(by - ay, bx - ax));
    mesh.userData.zmid = (r.zmax + r.zmin) / 2000;
    mesh.position.set((ax + bx) / 2, (ay + by) / 2, mesh.userData.zmid);
    mesh.visible = $("#ug-sections").checked;
    mesh.renderOrder = 1;
    R.scene.add(mesh); R.sections.push(mesh);
  }
  // terrain cut along the active section: keep the far side of the line from the camera
  const act = state.active && state.active.result;
  if ($("#ug-cut").checked && act) {
    const [ax, ay] = R.K(act.xa, act.ya), [bx, by] = R.K(act.xb, act.yb);
    let n = new THREE.Vector3(-(by - ay), bx - ax, 0).normalize();
    const cam = R.camera.position, side = n.x * (cam.x - ax) + n.y * (cam.y - ay);
    if (side > 0) n = n.negate();
    R.terrainMat.clippingPlanes = [new THREE.Plane(n, -(n.x * ax + n.y * ay))];
  } else R.terrainMat.clippingPlanes = [];
  // sensors and fiber sit on the terrain: cut them with it
  [R.sensors.material, R.fiber.material].forEach((m) => { m.clippingPlanes = R.terrainMat.clippingPlanes; m.needsUpdate = true; });
  R.terrainMat.needsUpdate = true;
  // depth slice
  if (R.slice) { R.scene.remove(R.slice); R.slice.geometry.dispose(); R.slice.material.map.dispose(); R.slice.material.dispose(); R.slice = null; }
  if ($("#ug-slice").checked) {
    const s = await Sub.slice(name, state.sliceZ, 250), [x0, y0, x1, y1] = s.bounds;
    const t = new THREE.CanvasTexture(s.canvas);
    t.colorSpace = THREE.SRGBColorSpace;
    const [cx, cy] = R.K((x0 + x1) / 2, (y0 + y1) / 2);
    R.slice = new THREE.Mesh(new THREE.PlaneGeometry((x1 - x0) / 1000, (y1 - y0) / 1000),
      new THREE.MeshBasicMaterial({ map: t, transparent: true, side: THREE.DoubleSide, opacity: 0.9 }));
    R.slice.userData.z = state.sliceZ / 1000;
    R.slice.position.set(cx, cy, 0);
    R.scene.add(R.slice);
  }
  applyVex(R);
  $("#ug-cbar").innerHTML = Sub.colorbar(name) +
    `<div class="hint">slice at ${(state.sliceZ / 1000).toFixed(2)} km · sections to ${state.zmin / 1000} km</div>`;
}

function wire(R_) {
  $("#ug-close").addEventListener("click", () => { $("#ug").classList.add("hidden"); R_.open = false; });
  $("#ug-tex").addEventListener("change", (e) => { R_.terrainMat.map = R_.tex[e.target.value] || R_.tex.units; R_.terrainMat.needsUpdate = true; });
  $("#ug-op").addEventListener("input", (e) => { R_.terrainMat.opacity = +e.target.value; R_.terrain.visible = +e.target.value > 0.01; });
  $("#ug-vex").addEventListener("input", (e) => { R_.vex = +e.target.value; $("#ug-vex-lbl").textContent = `Vertical ×${R_.vex}`; applyVex(R_); });
  ["#ug-cut", "#ug-slice"].forEach((id) => $(id).addEventListener("change", refresh));
  $("#ug-sections").addEventListener("change", (e) => R_.sections.forEach((m) => (m.visible = e.target.checked)));
  $("#ug-events").addEventListener("change", (e) => (R_.evMesh.visible = e.target.checked));
  $("#ug-sensors").addEventListener("change", (e) => { R_.sensors.visible = R_.fiber.visible = e.target.checked; });
  const loop = () => { if (R_.open) { R_.controls.update(); R_.renderer.render(R_.scene, R_.camera); } requestAnimationFrame(loop); };
  loop();
}

window.Underground = {
  async open() {
    $("#ug").classList.remove("hidden");
    if (!R) R = await build();
    R.open = true;
    R.renderer.setSize($("#ug-canvas").clientWidth, $("#ug-canvas").clientHeight);
    R.camera.aspect = $("#ug-canvas").clientWidth / $("#ug-canvas").clientHeight; R.camera.updateProjectionMatrix();
    await refresh();
  },
  refresh,
  isOpen: () => !!(R && R.open),
};
