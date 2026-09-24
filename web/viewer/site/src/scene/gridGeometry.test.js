import { describe, expect, it } from "vitest";
import { gridArrays } from "./gridGeometry.js";

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
