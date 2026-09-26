import { describe, expect, it } from "vitest";
import { decimate, gridArrays } from "./gridGeometry.js";

const at = (c, r) => [c, r, 1, 1];
const uv = (c, r) => [c, r];

describe("gridArrays", () => {
  it("builds vertices, indices and up normals on flat ground", () => {
    const a = gridArrays(3, 2, at, new Float32Array(6).fill(2), uv);
    expect(a.position.length).toBe(6 * 3);
    expect(a.index.length).toBe(2 * 1 * 6);
    const [nx, ny, nz] = a.normal.slice(0, 3);
    expect(nx).toBeCloseTo(0); expect(ny).toBe(1); expect(nz).toBeCloseTo(0);
    expect(a.position[1]).toBe(2);
  });
  it("tilts normals against the slope", () => {
    const h = new Float32Array([0, 1, 2, 0, 1, 2]);   // h = x
    const a = gridArrays(3, 2, at, h, uv);
    const [nx, ny, nz] = a.normal.slice(3, 6);
    expect(nx).toBeCloseTo(-Math.SQRT1_2); expect(ny).toBeCloseTo(Math.SQRT1_2); expect(nz).toBeCloseTo(0);
  });
  it("adds a skirt ring dropped below each edge vertex", () => {
    const a = gridArrays(3, 2, at, new Float32Array(6).fill(2), uv, 0.05);
    expect(a.position.length / 3).toBe(6 + 2 * (3 + 2) - 4);   // each border vertex once
    for (let j = 6; j < a.position.length / 3; j++) {
      expect(a.position[j * 3 + 1]).toBeCloseTo(1.95);
      expect(a.skirt[j]).toBe(1);
    }
    expect(a.skirt[0]).toBe(0);
  });
});

// the index as the builder wrote it before it was typed from the start (plain array, then copied)
function legacyIndex(n, m, skirt) {
  const index = [];
  for (let r = 0; r < m - 1; r++) for (let c = 0; c < n - 1; c++) { const a = r * n + c, b = a + 1, d = a + n, e = d + 1; index.push(a, d, b, b, d, e); }
  if (skirt) {
    const ring = [];
    for (let c = 0; c < n; c++) ring.push(c);
    for (let r = 1; r < m; r++) ring.push(r * n + n - 1);
    for (let c = n - 2; c >= 0; c--) ring.push((m - 1) * n + c);
    for (let r = m - 2; r >= 1; r--) ring.push(r * n);
    const base = n * m;
    for (let k = 0; k < ring.length; k++) index.push(ring[k], ring[(k + 1) % ring.length], base + k, ring[(k + 1) % ring.length], base + ((k + 1) % ring.length), base + k);
  }
  return index;
}

describe("gridArrays index", () => {
  const at = (c, r) => [c, r, 1, 1], uv = (c, r) => [c, r];
  it.each([[5, 4, 0], [5, 4, 0.1], [300, 250, 0.1]])("matches the plain-array build for %i x %i (skirt %s)", (n, m, skirt) => {
    const a = gridArrays(n, m, at, new Float32Array(n * m), uv, skirt);
    expect(Array.from(a.index)).toEqual(legacyIndex(n, m, skirt));
    expect(a.index).toBeInstanceOf(n * m + (skirt ? 2 * (n + m) - 4 : 0) > 65535 ? Uint32Array : Uint16Array);
  });
});

describe("decimate", () => {
  it("keeps every s-th sample, and both edges when (n - 1) is a multiple of s", () => {
    const n = 5, m = 3, h = Float32Array.from({ length: n * m }, (_, i) => i);
    const d = decimate(h, n, m, 2);
    expect([d.n, d.m, d.s]).toEqual([3, 2, 2]);
    expect(Array.from(d.heights)).toEqual([0, 2, 4, 10, 12, 14]);
  });
  it("stride 1 returns the grid unchanged", () => {
    const h = new Float32Array(6);
    expect(decimate(h, 3, 2, 1).heights).toBe(h);
  });
  it("a 257-vertex summit tile keeps its edges at stride 2", () => {
    const d = decimate(new Float32Array(257 * 257), 257, 257, 2);
    expect([d.n, d.m]).toEqual([129, 129]);
  });
});

