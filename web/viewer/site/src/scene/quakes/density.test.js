import { describe, expect, it } from "vitest";
import { blur3d, GRID, massThresholds, splat, trimAboveGround, worldOf } from "./density.js";

const rec = (...evs) => new Float32Array(evs.flat());
const argmax = f => f.reduce((best, v, i) => (v > f[best] ? i : best), 0);
const ijk = (idx, n) => [idx % n, Math.floor(idx / n) % n, Math.floor(idx / (n * n))];

describe("density grid", () => {
  it("splats an event into the nearest cell and drops events outside", () => {
    const f = splat(rec([0, -5, 0, 1], [80, -5, 0, 1]), GRID);
    expect(f.reduce((a, b) => a + b, 0)).toBe(1);
    const [i, j, k] = ijk(argmax(f), GRID.res), [x, y, z] = worldOf(i, j, k, GRID);
    expect(Math.abs(x)).toBeLessThan(0.5); expect(Math.abs(z)).toBeLessThan(0.5); expect(Math.abs(y + 5)).toBeLessThan(0.2);
  });
  it("blurring keeps the mass away from the edges", () => {
    const f = splat(rec([0, -8, 0, 1]), GRID);
    const b = blur3d(f, GRID.res, [1.2, 1.6, 1.2]);
    expect(b.reduce((a, v) => a + v, 0)).toBeCloseTo(1, 2);
    expect(b.reduce((m, v) => Math.max(m, v), 0)).toBeLessThan(0.5);
  });
  it("trims cells above the ground", () => {
    const n = GRID.res, f = new Float32Array(n ** 3).fill(1);
    trimAboveGround(f, GRID, () => 1);
    for (let j = 0; j < n; j++) {
      const y = worldOf(0, j, 0, GRID)[1], v = f[n * n * 10 + n * j + 10];
      expect(v).toBe(y > 1 ? 0 : 1);
    }
  });
});

describe("massThresholds", () => {
  it("finds the density above which a fraction of the mass lies", () => {
    expect(massThresholds(new Float32Array([4, 3, 2, 1]), [0.7])).toEqual([3]);
    expect(massThresholds(new Float32Array([4, 3, 2, 1]), [0.3, 1])).toEqual([4, 1]);
  });
  it("an empty field gives zero thresholds without throwing", () => {
    expect(massThresholds(new Float32Array(8), [0.7, 0.45, 0.2])).toEqual([0, 0, 0]);
  });
});
