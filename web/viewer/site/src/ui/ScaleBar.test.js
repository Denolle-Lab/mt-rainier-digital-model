import { describe, expect, it } from "vitest";
import { kmPerPixel, niceScale } from "./ScaleBar.jsx";

describe("scale bar", () => {
  it("km per pixel at the view centre of a perspective camera", () => {
    // 32 deg field of view, 100 km away, 900 px tall: 2 * 100 * tan(16 deg) / 900
    expect(kmPerPixel(32, 100, 900)).toBeCloseTo(0.0637, 3);
  });
  it("picks a round length drawn close to 110 px and at most 150 px", () => {
    expect(niceScale(0.0637)).toEqual({ km: 5, px: 5 / 0.0637 });
    expect(niceScale(0.001).km).toBe(0.1);
    expect(niceScale(0.00001)).toEqual({ km: 0.001, px: 100 });   // zoomed in: 1 m at 100 px, not 0.1 km at 10,000 px
    expect(niceScale(0.00001).px).toBeLessThanOrEqual(150);
    expect(niceScale(0.3).km).toBe(20);            // 50 km would be 167 px
  });
});
