import { describe, expect, it } from "vitest";
import { nearestLevel, segmentPositions } from "./strainBars.js";

describe("strain bars", () => {
  it("picks the level nearest the slice elevation", () => {
    const levels = [4, 3, 2, 1, 0, -1, -2];
    expect(nearestLevel(levels, -2)).toBe(6);
    expect(nearestLevel(levels, 0.4)).toBe(4);
    expect(nearestLevel(levels, 9)).toBe(0);
    expect(nearestLevel([], 0)).toBe(-1);
  });

  it("turns x0, z0, x1, z1 lists into line-segment positions at one height", () => {
    const p = segmentPositions([1, 2, 3, 4, 5, 6, 7, 8], -2);
    expect(Array.from(p)).toEqual([1, -2, 2, 3, -2, 4, 5, -2, 6, 7, -2, 8]);
    expect(segmentPositions([1, 2, 3]).length).toBe(0);   // an incomplete segment is dropped
  });
});
