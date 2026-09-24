// Subsurface sampling and rendering for the atlas: loads the quantized model cubes written by
// rainier3d.export.web (data/model/), samples them (NaN-aware trilinear; nearest for categorical),
// and renders vertical sections and horizontal depth slices to canvases.
"use strict";

window.Sub = (() => {
  const M = "data/model/";
  let META = null, SURF = null;
  const cache = {};

  // ---------- UTM (WGS84) forward, Snyder (1987) series; zone from meta
  function utm(lon, lat, zone = 10) {
    const a = 6378137, f = 1 / 298.257223563, k0 = 0.9996, e2 = f * (2 - f), ep2 = e2 / (1 - e2);
    const phi = (lat * Math.PI) / 180, lam = (lon * Math.PI) / 180, lam0 = ((zone * 6 - 183) * Math.PI) / 180;
    const s = Math.sin(phi), c = Math.cos(phi), t = Math.tan(phi);
    const N = a / Math.sqrt(1 - e2 * s * s), T = t * t, C = ep2 * c * c, A = c * (lam - lam0);
    const e4 = e2 * e2, e6 = e4 * e2;
    const Mm = a * ((1 - e2 / 4 - (3 * e4) / 64 - (5 * e6) / 256) * phi - ((3 * e2) / 8 + (3 * e4) / 32 + (45 * e6) / 1024) * Math.sin(2 * phi)
      + ((15 * e4) / 256 + (45 * e6) / 1024) * Math.sin(4 * phi) - ((35 * e6) / 3072) * Math.sin(6 * phi));
    const x = k0 * N * (A + ((1 - T + C) * A ** 3) / 6 + ((5 - 18 * T + T * T + 72 * C - 58 * ep2) * A ** 5) / 120) + 500000;
    const y = k0 * (Mm + N * t * ((A * A) / 2 + ((5 - T + 9 * C + 4 * C * C) * A ** 4) / 24
      + ((61 - 58 * T + T * T + 600 * C - 330 * ep2) * A ** 6) / 720));
    return [x, y];
  }

  async function gz(url, Type) {
    const r = await fetch(url);
    if (!r.ok) throw new Error(url + " " + r.status);
    const buf = await new Response(r.body.pipeThrough(new DecompressionStream("gzip"))).arrayBuffer();
    return new Type(buf);
  }

  async function init() {
    if (META) return META;
    META = await (await fetch(M + "meta.json")).json();
    const s = META.surface;
    SURF = { ...s, elev: await gz(M + "surface_elev.i16.gz", Int16Array), ice: await gz(M + "surface_ice.u8.gz", Uint8Array) };
    return META;
  }

  async function load(name) {
    if (!cache[name]) {
      const out = {};
      await Promise.all(Object.keys(META.levels).map(async (L) => (out[L] = await gz(`${M}${L}_${name}.u8.gz`, Uint8Array))));
      cache[name] = out;
    }
    return cache[name];
  }

  function surfaceAt(x, y, what = "elev") {
    const s = SURF, fx = (x - s.x0) / s.dx, fy = (y - s.y0) / s.dx;
    const i = Math.max(0, Math.min(s.nx - 2, Math.floor(fx))), j = Math.max(0, Math.min(s.ny - 2, Math.floor(fy)));
    const tx = Math.min(1, Math.max(0, fx - i)), ty = Math.min(1, Math.max(0, fy - j)), a = s[what];
    const v = (ii, jj) => a[jj * s.nx + ii];
    return (1 - ty) * ((1 - tx) * v(i, j) + tx * v(i + 1, j)) + ty * ((1 - tx) * v(i, j + 1) + tx * v(i + 1, j + 1));
  }

  function levelFor(z) {
    for (const [L, m] of Object.entries(META.levels)) if (z <= m.z_top && z >= m.z_bot) return L;
    return null;
  }

  // value in physical units at (x, y, z), NaN in air / outside
  function sample(name, cube, x, y, z) {
    const L = levelFor(z);
    if (!L) return NaN;
    const m = META.levels[L], v = META.vars[name], a = cube[L];
    const fi = (x - m.x0) / m.dx, fj = (y - m.y0) / m.dx, fk = (m.z_top - z) / m.dz - 0.5;
    if (fi < -0.5 || fj < -0.5 || fi > m.nx - 0.5 || fj > m.ny - 0.5) return NaN;
    const at = (i, j, k) => a[(Math.min(m.nz - 1, Math.max(0, k)) * m.ny + Math.min(m.ny - 1, Math.max(0, j))) * m.nx
      + Math.min(m.nx - 1, Math.max(0, i))];
    if (v.categorical) {
      const q = at(Math.round(fi), Math.round(fj), Math.round(fk));
      return q === 255 ? NaN : q;
    }
    const i0 = Math.floor(fi), j0 = Math.floor(fj), k0 = Math.floor(fk);
    const tx = fi - i0, ty = fj - j0, tz = fk - k0;
    let sw = 0, sv = 0;
    for (let dk = 0; dk < 2; dk++) for (let dj = 0; dj < 2; dj++) for (let di = 0; di < 2; di++) {
      const q = at(i0 + di, j0 + dj, k0 + dk);
      if (q === 255) continue;
      const w = (di ? tx : 1 - tx) * (dj ? ty : 1 - ty) * (dk ? tz : 1 - tz);
      sw += w; sv += w * q;
    }
    return sw > 1e-6 ? v.vmin + ((sv / sw) / 254) * (v.vmax - v.vmin) : NaN;
  }

  function color(name, val) {
    const v = META.vars[name];
    if (Number.isNaN(val)) return null;
    const idx = v.categorical ? Math.min(255, val) : Math.round(255 * Math.min(1, Math.max(0, (val - v.vmin) / (v.vmax - v.vmin))));
    return v.lut[idx];
  }

  // ---------- vertical section: A, B = [lon, lat]; returns canvas + geometry for overlays/3D
  async function section(name, A, B, { zmin = -6000, width = 900, height = 360 } = {}) {
    await init();
    const cube = await load(name);
    const [xa, ya] = utm(...A), [xb, yb] = utm(...B);
    const len = Math.hypot(xb - xa, yb - ya);
    const surf = [];
    for (let c = 0; c < width; c++) {
      const t = c / (width - 1);
      surf.push(surfaceAt(xa + t * (xb - xa), ya + t * (yb - ya)));
    }
    const zmax = Math.max(...surf) + 250;
    const cv = document.createElement("canvas");
    cv.width = width; cv.height = height;
    const g = cv.getContext("2d"), img = g.createImageData(width, height);
    const vals = new Float32Array(width * height).fill(NaN);
    for (let c = 0; c < width; c++) {
      const t = c / (width - 1), x = xa + t * (xb - xa), y = ya + t * (yb - ya);
      let last = NaN;
      for (let r = height - 1; r >= 0; r--) { // bottom-up so the top cells under the ground inherit values
        const z = zmax - (r / (height - 1)) * (zmax - zmin);
        if (z > surf[c]) break;
        let v = sample(name, cube, x, y, z);
        if (Number.isNaN(v)) v = last; else last = v;
        vals[r * width + c] = v;
        const rgb = color(name, v);
        if (!rgb) continue;
        const p = 4 * (r * width + c);
        img.data[p] = rgb[0]; img.data[p + 1] = rgb[1]; img.data[p + 2] = rgb[2]; img.data[p + 3] = 255;
      }
    }
    g.putImageData(img, 0, 0);
    return { canvas: cv, vals, surf, zmin, zmax, len, xa, ya, xb, yb, width, height, name };
  }

  // ---------- horizontal slice at elevation z over the whole domain (L1 grid spacing or given)
  async function slice(name, z, step = 250) {
    await init();
    const cube = await load(name);
    const L = META.levels.L1, s = META.surface;
    const x0 = s.x0 - s.dx / 2, y0 = s.y0 - s.dx / 2, x1 = x0 + s.nx * s.dx, y1 = y0 + s.ny * s.dx;
    const nx = Math.round((x1 - x0) / step), ny = Math.round((y1 - y0) / step);
    const cv = document.createElement("canvas");
    cv.width = nx; cv.height = ny;
    const g = cv.getContext("2d"), img = g.createImageData(nx, ny);
    for (let j = 0; j < ny; j++) for (let i = 0; i < nx; i++) {
      const x = x0 + (i + 0.5) * step, y = y1 - (j + 0.5) * step; // image rows north -> south
      if (z > surfaceAt(x, y)) continue;
      const rgb = color(name, sample(name, cube, x, y, z));
      if (!rgb) continue;
      const p = 4 * (j * nx + i);
      img.data[p] = rgb[0]; img.data[p + 1] = rgb[1]; img.data[p + 2] = rgb[2]; img.data[p + 3] = 235;
    }
    g.putImageData(img, 0, 0);
    void L;
    return { canvas: cv, bounds: [x0, y0, x1, y1] };
  }

  function colorbar(name, el) {
    const v = META.vars[name];
    if (v.categorical) return "";
    const stops = v.lut.filter((_, i) => i % 16 === 0 || i === 255).map((c, i, arr) =>
      `rgb(${c}) ${(100 * i) / (arr.length - 1)}%`).join(",");
    return `<div class="cbar" style="background:linear-gradient(90deg,${stops})"></div>
      <div class="cbar-lbl"><span>${v.vmin}</span><span>${v.label}${v.units ? " (" + v.units + ")" : ""}</span><span>${v.vmax}</span></div>`;
  }

  return { init, load, sample, section, slice, surfaceAt, utm, colorbar, color, meta: () => META, surf: () => SURF };
})();
