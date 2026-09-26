import { describe, expect, it } from "vitest";
import { evictable, selectTiles, tileBounds } from "./summitLod.js";

// 2 × 1 roots of 1 km, three levels
const index = {
  patch: { west_km: 0, north_km: 0, width_km: 2, height_km: 1 }, tile: 256,
  levels: [0, 1, 2].map(k => ({ level: k, cell_x_km: 1 / 256 / 2 ** k, cell_z_km: 1 / 256 / 2 ** k, tiles_x: 2 * 2 ** k, tiles_z: 2 ** k })),
};
const flat = () => [0, 0];
const kids = (ty, tx) => [0, 1].flatMap(i => [0, 1].map(j => `1/${ty * 2 + i}_${tx * 2 + j}`));

describe("tileBounds", () => {
  it("places tiles from the north-west corner", () => {
    expect(tileBounds(index, 1, 0, 3)).toEqual({ x0: 1.5, z0: 0, ex: 0.5, ez: 0.5 });
  });
});

describe("selectTiles", () => {
  it("far away shows only the roots", () => {
    const s = selectTiles(index, [0, 50, 0], () => "ready", flat);
    expect(s.show.sort()).toEqual(["0/0_0", "0/0_1"]);
    expect(s.want.sort()).toEqual(["0/0_0", "0/0_1"]);
  });
  it("close to a root with ready children shows the children", () => {
    const ready = new Set(["0/0_0", "0/0_1", ...kids(0, 0)]);
    const s = selectTiles(index, [0.5, 0.5, 0.5], k => (ready.has(k) ? "ready" : undefined), flat);
    expect(s.show.sort()).toEqual([...kids(0, 0), "0/0_1"].sort());
    expect(s.want).toEqual(expect.arrayContaining([...kids(0, 1), "2/0_0"]));
  });
  it("keeps the parent until every child is ready", () => {
    const st = { "0/0_0": "ready", "0/0_1": "ready", "1/0_0": "ready", "1/0_1": "loading", "1/1_0": "ready", "1/1_1": "ready" };
    const s = selectTiles(index, [0.5, 0.5, 0.5], k => st[k], flat);
    expect(s.show).toContain("0/0_0");
    expect(s.want).toEqual(expect.arrayContaining(kids(0, 0)));
  });
  it("maxLevel stops the refinement; a smaller refine distance refines later", () => {
    const all = () => "ready", cam = [0.5, 0.01, 0.5];
    expect(Math.max(...selectTiles(index, cam, all, flat).show.map(id => +id[0]))).toBe(2);
    expect(Math.max(...selectTiles(index, cam, all, flat, { maxLevel: 1 }).show.map(id => +id[0]))).toBe(1);
    const far = [0.5, 1.5, 0.5];   // 1.5 km above a 1 km root: within 2.5 root widths, beyond 1.25
    expect(selectTiles(index, far, all, flat).show.some(id => id.startsWith("1/"))).toBe(true);
    expect(selectTiles(index, far, all, flat, { refine: 1.25 }).show.every(id => id.startsWith("0/"))).toBe(true);
  });
  it("a failed child keeps the parent", () => {
    const st = { "0/0_0": "ready", "0/0_1": "ready", "1/0_0": "failed", "1/0_1": "ready", "1/1_0": "ready", "1/1_1": "ready" };
    expect(selectTiles(index, [0.5, 0.5, 0.5], k => st[k], flat).show).toContain("0/0_0");
  });
  it("shows nothing for a root that has not loaded, but wants it", () => {
    const s = selectTiles(index, [0, 50, 0], k => (k === "0/0_0" ? "ready" : "loading"), flat);
    expect(s.show).toEqual(["0/0_0"]);
    expect(s.want).toContain("0/0_1");
  });
});

describe("evictable", () => {
  it("never evicts a shown tile or a root, and only old tiles past the cap", () => {
    const tiles = new Map([
      ["0/0_0", { k: 0, state: "ready", used: 0 }],
      ["1/0_0", { k: 1, state: "ready", used: 0 }],
      ["1/0_1", { k: 1, state: "ready", used: 0 }],
      ["1/1_0", { k: 1, state: "ready", used: 190 }],
    ]);
    expect(evictable(tiles, new Set(["1/0_1"]), 200, 2, 120)).toEqual(["1/0_0"]);
    expect(evictable(tiles, new Set(), 200, 10, 120)).toEqual([]);
  });
});
