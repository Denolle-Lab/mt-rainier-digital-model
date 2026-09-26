import * as THREE from "three";
import { decimate, gridGeometry } from "./gridGeometry.js";

// Summit terrain in detail levels (8, 4, 2, 1 m). A tile splits into its four children when the camera is closer
// than REFINE tile widths; the parent stays until all four children are ready, so the view never has a hole.
export const REFINE = 2.5;
const key = (k, ty, tx) => `${k}/${ty}_${tx}`;
const parse = id => { const [k, rest] = id.split("/"); const [ty, tx] = rest.split("_"); return [+k, +ty, +tx]; };

export function tileBounds(index, k, ty, tx) {
  const L = index.levels[k], ex = L.cell_x_km * index.tile, ez = L.cell_z_km * index.tile;
  return { x0: index.patch.west_km + tx * ex, z0: index.patch.north_km + ty * ez, ex, ez };
}

function distance(index, k, ty, tx, cam, [lo, hi]) {
  const { x0, z0, ex, ez } = tileBounds(index, k, ty, tx);
  const dx = Math.max(x0 - cam[0], 0, cam[0] - (x0 + ex)), dz = Math.max(z0 - cam[2], 0, cam[2] - (z0 + ez));
  const dy = Math.max(lo - cam[1], 0, cam[1] - hi);
  return Math.hypot(dx, dy, dz);
}

// Pure: which tiles to draw now (show) and which to have loaded (want).
// `refine` (tile widths) and `maxLevel` bound the detail: the phone profile refines later and stops at 2 m.
export function selectTiles(index, cam, state, heightRange, { refine = REFINE, maxLevel = Infinity } = {}) {
  const max = Math.min(index.levels.length - 1, maxLevel), show = [], want = [];
  const visit = (k, ty, tx) => {
    const id = key(k, ty, tx);
    want.push(id);
    const L = index.levels[k];
    if (k < max && distance(index, k, ty, tx, cam, heightRange(k, ty, tx)) < Math.max(L.cell_x_km, L.cell_z_km) * index.tile * refine) {
      const kids = [];
      for (let i = 0; i < 2; i++) for (let j = 0; j < 2; j++) kids.push([k + 1, ty * 2 + i, tx * 2 + j]);
      kids.forEach(c => want.push(key(...c)));
      if (kids.every(c => state(key(...c)) === "ready")) {
        want.splice(want.length - 4, 4);   // visit() re-adds them
        kids.forEach(c => visit(...c));
        return;
      }
    }
    show.push(id);
  };
  const L0 = index.levels[0];
  for (let ty = 0; ty < L0.tiles_z; ty++) for (let tx = 0; tx < L0.tiles_x; tx++) {
    if (state(key(0, ty, tx)) === "ready") visit(0, ty, tx);
    else want.push(key(0, ty, tx));
  }
  return { show, want };
}

// Pure: tiles to drop once there are more than `cap`: ready, not a root, not shown, unused for `maxAge` frames.
export function evictable(tiles, shown, frame, cap, maxAge) {
  if (tiles.size <= cap) return [];
  const out = [];
  for (const [id, t] of tiles) if (t.state === "ready" && t.k > 0 && !shown.has(id) && frame - t.used > maxAge) out.push(id);
  return out;
}

export class SummitLod {
  constructor(index, base, makeMaterial, group, { inflight = 6, cap = 360, stride = 1, refine = REFINE, maxLevel = Infinity } = {}) {
    Object.assign(this, { index, base, makeMaterial, group, maxInflight: inflight, cap, stride, refine, maxLevel });
    this.tiles = new Map(); this.chunks = new Map(); this.inflight = 0; this.frameNo = 0; this.finest = -1; this.failures = 0;
    this.allRootsReady = false;
  }

  _state = id => this.tiles.get(id)?.state;
  _range = (k, ty, tx) => { const t = this.tiles.get(key(k, ty, tx)); return t?.range ?? [1.8, 4.4]; };

  _chunk(k, ty, tx) {
    const L = this.index.levels[k], r = Math.floor((ty * this.index.tile) / L.chunk_h), c = Math.floor((tx * this.index.tile) / L.chunk_w);
    const id = `img${k}_${r}_${c}`;
    let ch = this.chunks.get(id);
    if (!ch) {
      ch = { id, r, c, refs: 0 };
      ch.ready = new THREE.TextureLoader().loadAsync(`${this.base}summit/img/${id}.jpg`).then(tex => {
        tex.flipY = false; tex.colorSpace = THREE.NoColorSpace; tex.anisotropy = 8; tex.needsUpdate = true;
        ch.tex = tex; ch.mat = this.makeMaterial(tex); return ch;
      });
      this.chunks.set(id, ch);
    }
    return ch;
  }

  _load(id) {
    const [k, ty, tx] = parse(id), t = this.tiles.get(id), T = this.index.tile, L = this.index.levels[k];
    this.inflight++; t.state = "loading";
    const ch = this._chunk(k, ty, tx); ch.refs++; t.chunk = ch;
    Promise.all([fetch(`${this.base}summit/${k}/${ty}_${tx}.bin`).then(r => { if (!r.ok) throw new Error(r.status); return r.arrayBuffer(); }), ch.ready])
      .then(([buf]) => {
        const q = new Uint16Array(buf), n = T + 1, h = new Float32Array(n * n);
        let lo = 1e9, hi = -1e9;
        for (let i = 0; i < q.length; i++) { h[i] = q[i] / 10000; lo = Math.min(lo, h[i]); hi = Math.max(hi, h[i]); }
        t.range = [lo, hi];
        const { x0, z0 } = tileBounds(this.index, k, ty, tx), sx = L.cell_x_km, sz = L.cell_z_km;
        const d = decimate(h, n, n, this.stride), s = d.s;   // tile = 256 cells: stride 2 keeps both edges
        const g = gridGeometry(d.n, d.m, (c, r) => [x0 + (c * s + 0.5) * sx, z0 + (r * s + 0.5) * sz, sx * s, sz * s], d.heights,
          (c, r) => [((tx * T + c * s + 0.5) - ch.c * L.chunk_w) / L.chunk_w, ((ty * T + r * s + 0.5) - ch.r * L.chunk_h) / L.chunk_h], 12 * sz);
        t.mesh = new THREE.Mesh(g, ch.mat); t.mesh.visible = false;
        t.mesh.frustumCulled = false;   // 2D flattens heights in the shader, so the geometry's bounds are wrong
        this.group.add(t.mesh); t.state = "ready";
      })
      .catch(() => { t.state = "failed"; this.failures++; ch.refs--; })
      .finally(() => { this.inflight--; });
  }

  update(camera, flat = 0) {
    this.frameNo++;
    const cam = camera.position.toArray();
    const range = (k, ty, tx) => this._range(k, ty, tx).map(h => h * (1 - flat));
    const { show, want } = selectTiles(this.index, cam, this._state, range, { refine: this.refine, maxLevel: this.maxLevel });
    for (const id of want) {
      let t = this.tiles.get(id);
      if (!t) { t = { k: parse(id)[0], state: "queued", used: this.frameNo }; this.tiles.set(id, t); }
      t.used = this.frameNo;
    }
    const L0 = this.index.levels[0];
    this.allRootsReady = this.tiles.size > 0 && [...Array(L0.tiles_z * L0.tiles_x).keys()]
      .every(i => this._state(key(0, Math.floor(i / L0.tiles_x), i % L0.tiles_x)) === "ready");
    const on = new Set(this.allRootsReady ? show : []);
    this.finest = -1;
    for (const [id, t] of this.tiles) if (t.mesh) {
      t.mesh.visible = on.has(id);
      if (t.mesh.visible) this.finest = Math.max(this.finest, t.k);
    }
    // queue: newest wanted first, coarse before fine; drop what nobody has wanted for 30 frames
    const queued = [...this.tiles].filter(([, t]) => t.state === "queued").sort(([, a], [, b]) => b.used - a.used || a.k - b.k);
    for (const [id, t] of queued) {
      if (this.frameNo - t.used > 30) { this.tiles.delete(id); continue; }
      if (this.inflight >= this.maxInflight) break;
      this._load(id);
    }
    for (const id of evictable(this.tiles, on, this.frameNo, this.cap, 120)) {
      const t = this.tiles.get(id);
      this.group.remove(t.mesh); t.mesh.geometry.dispose(); this.tiles.delete(id);
      if (--t.chunk.refs <= 0) { t.chunk.tex?.dispose(); t.chunk.mat?.dispose(); this.chunks.delete(t.chunk.id); }
    }
    return this.finest;
  }

  dispose() {
    for (const t of this.tiles.values()) t.mesh?.geometry.dispose();
    for (const ch of this.chunks.values()) { ch.tex?.dispose(); ch.mat?.dispose(); }
    this.tiles.clear(); this.chunks.clear();
  }
}
