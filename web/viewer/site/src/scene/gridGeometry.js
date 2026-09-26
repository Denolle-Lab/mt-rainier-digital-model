import * as THREE from "three";

// n × m vertex grid. posAt(c, r) → [x, z, sx, sz] (km; sx/sz = spacing for the slope), heights in km,
// uvAt(c, r) → [u, v]. skirtKm > 0 adds a ring of vertices dropped below the edge to hide cracks between
// detail levels; those vertices carry skirt = 1 so the shader can draw them as rock (or drop them from below).
export function gridArrays(n, m, posAt, heights, uvAt, skirtKm = 0) {
  const count = n * m + (skirtKm ? 2 * (n + m) - 4 : 0);   // the edge ring: every border vertex once
  const position = new Float32Array(count * 3), uv = new Float32Array(count * 2), normal = new Float32Array(count * 3), skirt = new Float32Array(count);
  const H = (r, c) => heights[Math.min(m - 1, Math.max(0, r)) * n + Math.min(n - 1, Math.max(0, c))];
  let i = 0;
  for (let r = 0; r < m; r++) for (let c = 0; c < n; c++, i++) {
    const [x, z, sx, sz] = posAt(c, r);
    position[i * 3] = x; position[i * 3 + 1] = heights[i]; position[i * 3 + 2] = z;
    const [u, v] = uvAt(c, r); uv[i * 2] = u; uv[i * 2 + 1] = v;
    const gx = (H(r, c + 1) - H(r, c - 1)) / ((Math.min(n - 1, c + 1) - Math.max(0, c - 1)) * sx);
    const gz = (H(r + 1, c) - H(r - 1, c)) / ((Math.min(m - 1, r + 1) - Math.max(0, r - 1)) * sz);
    const l = Math.hypot(gx, 1, gz);
    normal[i * 3] = -gx / l; normal[i * 3 + 1] = 1 / l; normal[i * 3 + 2] = -gz / l;
  }
  // typed from the start: a plain array of 13 M indices for the overview costs ~100 MB before the copy
  const nRing = skirtKm ? 2 * (n + m) - 4 : 0;
  const index = new (count > 65535 ? Uint32Array : Uint16Array)(6 * ((n - 1) * (m - 1) + nRing));
  let q = 0;
  for (let r = 0; r < m - 1; r++) for (let c = 0; c < n - 1; c++) {
    const a = r * n + c, b = a + 1, d = a + n, e = d + 1;
    index[q++] = a; index[q++] = d; index[q++] = b; index[q++] = b; index[q++] = d; index[q++] = e;
  }
  if (skirtKm) {
    const ring = [];
    for (let c = 0; c < n; c++) ring.push(c);
    for (let r = 1; r < m; r++) ring.push(r * n + n - 1);
    for (let c = n - 2; c >= 0; c--) ring.push((m - 1) * n + c);
    for (let r = m - 2; r >= 1; r--) ring.push(r * n);
    const base = i;
    ring.forEach((src, k) => {
      const j = base + k;
      position[j * 3] = position[src * 3]; position[j * 3 + 1] = position[src * 3 + 1] - skirtKm; position[j * 3 + 2] = position[src * 3 + 2];
      uv[j * 2] = uv[src * 2]; uv[j * 2 + 1] = uv[src * 2 + 1];
      normal.set(normal.subarray(src * 3, src * 3 + 3), j * 3);
      skirt[j] = 1;
    });
    for (let k = 0; k < ring.length; k++) {
      const a = ring[k], b = ring[(k + 1) % ring.length], a2 = base + k, b2 = base + ((k + 1) % ring.length);
      index[q++] = a; index[q++] = b; index[q++] = a2; index[q++] = b; index[q++] = b2; index[q++] = a2;
    }
  }
  return { position, uv, normal, skirt, index };
}

// Every s-th sample of an n × m height grid (rows of n), keeping the last row and column when (n - 1) is a
// multiple of s. Returns { heights, n, m, s }: the smaller grid, its size and the stride (sample c of the new
// grid is sample c * s of the old).
export function decimate(heights, n, m, s) {
  if (s <= 1) return { heights, n, m, s: 1 };
  const n2 = Math.floor((n - 1) / s) + 1, m2 = Math.floor((m - 1) / s) + 1, h = new Float32Array(n2 * m2);
  for (let r = 0; r < m2; r++) for (let c = 0; c < n2; c++) h[r * n2 + c] = heights[r * s * n + c * s];
  return { heights: h, n: n2, m: m2, s };
}

export function gridGeometry(...args) {
  const a = gridArrays(...args);
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.BufferAttribute(a.position, 3));
  g.setAttribute("uv", new THREE.BufferAttribute(a.uv, 2));
  g.setAttribute("normal", new THREE.BufferAttribute(a.normal, 3));
  g.setAttribute("skirt", new THREE.BufferAttribute(a.skirt, 1));
  g.setIndex(new THREE.BufferAttribute(a.index, 1));
  return g;
}
