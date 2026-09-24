import * as THREE from "three";

// The ground surface from the overview grid: a bilinear sampler for JS, and a height texture + GLSL helper that
// every underground layer uses to drop fragments that would sit above the surface. The texture holds 2 × 2 block
// maxima so the test never lets anything through a ridge.
export const GROUND_GLSL = `
  uniform sampler2D uHeight; uniform vec4 uHRect;
  float groundKm(vec2 xz) { return texture2D(uHeight, (xz - uHRect.xy) / uHRect.zw).r; }`;

export function makeGround(meta, heights) {
  const { cols, rows, x0, z0, dx, dz } = meta;
  const hAt = (r, c) => heights[Math.min(rows - 1, Math.max(0, r)) * cols + Math.min(cols - 1, Math.max(0, c))];
  const elevKm = (x, z) => {
    const fc = (x - x0) / dx - 0.5, fr = (z - z0) / dz - 0.5;
    if (fc < 0 || fr < 0 || fc > cols - 1 || fr > rows - 1) return null;
    const c = Math.floor(fc), r = Math.floor(fr), tc = fc - c, tr = fr - r;
    return ((hAt(r, c) * (1 - tc) + hAt(r, c + 1) * tc) * (1 - tr) + (hAt(r + 1, c) * (1 - tc) + hAt(r + 1, c + 1) * tc) * tr) / 1000;
  };
  const s = 2, w = Math.floor(cols / s), h = Math.floor(rows / s), d = new Float32Array(w * h);
  for (let r = 0; r < h; r++) for (let c = 0; c < w; c++) {
    let mx = -1e9;
    for (let i = 0; i < s; i++) for (let j = 0; j < s; j++) mx = Math.max(mx, hAt(r * s + i, c * s + j));
    d[r * w + c] = mx / 1000;
  }
  const texture = new THREE.DataTexture(d, w, h, THREE.RedFormat, THREE.FloatType);
  texture.minFilter = texture.magFilter = THREE.NearestFilter; texture.needsUpdate = true;
  const rect = new THREE.Vector4(x0, z0, cols * dx, rows * dz);
  return { elevKm, texture, rect, glsl: GROUND_GLSL, uniforms: { uHeight: { value: texture }, uHRect: { value: rect } } };
}
