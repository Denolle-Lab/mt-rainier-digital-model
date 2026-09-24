import { describe, expect, it } from "vitest";
import { makeGround } from "./ground.js";

const meta = { cols: 4, rows: 4, x0: 0, z0: 0, dx: 1, dz: 1 };

describe("makeGround", () => {
  it("interpolates between cell centers and returns null outside", () => {
    const h = new Int16Array(16).fill(1000);
    h[5] = 2000;   // row 1, col 1 → centered at (1.5, 1.5)
    const g = makeGround(meta, h);
    expect(g.elevKm(1.5, 1.5)).toBeCloseTo(2);
    expect(g.elevKm(2.0, 1.5)).toBeCloseTo(1.5);
    expect(g.elevKm(-3, 1)).toBeNull();
  });
  it("the clip texture holds the lowest ground nearby, so nothing passes above a dip in the surface", () => {
    const h = new Int16Array(16).fill(1000);
    h[5] = 200;   // one low sample in block (0, 0)
    const g = makeGround(meta, h);
    expect(g.texture.image.width).toBe(2);
    for (const v of g.texture.image.data) expect(v).toBeCloseTo(0.2);   // block min, then spread to neighbors
    expect(g.minKm(3.5, 3.5)).toBeCloseTo(0.2);
    expect(g.glsl).toContain("float groundKm(vec2 xz)");
    expect(g.rect.toArray()).toEqual([0, 0, 4, 4]);
  });
});
