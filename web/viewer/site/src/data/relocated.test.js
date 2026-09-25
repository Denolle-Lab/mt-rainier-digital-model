import { describe, expect, it } from "vitest";
import { countAboveGround, selectCatalog, shiftSegments } from "./relocated.js";

const fields = ["x_cc", "y_cc", "z_cc", "x_1d", "y_1d", "z_1d", "x_3d", "y_3d", "z_3d", "mag", "quality", "gap"];
// two events: A-quality (all three located) and C-quality (3D located, ComCat above the ground)
const reloc = {
  meta: { fields },
  records: new Float32Array([
    1, -5, 2, 1.1, -6, 2.1, 1.2, -7, 2.2, 2.0, 3, 80,
    4, 1.5, 4, 4.1, -1, 4.1, 4.2, -2, 4.2, 1.0, 1, 250,
  ]),
};

describe("relocated catalogue", () => {
  it("selects one catalogue and filters by quality", () => {
    const a = selectCatalog(reloc, "3d", 2);
    expect(a.n).toBe(1);
    expect(Array.from(a.pos)).toEqual([1.2, -7, 2.2].map(Math.fround));
    expect(selectCatalog(reloc, "cc", 1).n).toBe(2);
  });
  it("builds 1D -> 3D shift segments", () => {
    const s = shiftSegments(reloc, "1d", "3d", 1);
    expect(s.length).toBe(12);
    expect(Array.from(s.slice(0, 6))).toEqual([1.1, -6, 2.1, 1.2, -7, 2.2].map(Math.fround));
  });
  it("counts locations above the ground", () => {
    const cc = selectCatalog(reloc, "cc", 1);
    expect(countAboveGround(cc.pos, () => 1.0)).toBe(1);   // the second ComCat location is at +1.5 km
    expect(countAboveGround(cc.pos, () => null)).toBe(0);   // outside the terrain: not counted
  });
});
