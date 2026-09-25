import { describe, expect, it } from "vitest";
import { DEFAULT_MASS_FILTER, massCounts, passesMass } from "./massEvents.js";

const ev = [
  { cls: "rock_avalanche", date: "2011-06-24 16:40:54", located: "seismic" },
  { cls: "rock_avalanche", date: "", located: "crown" },
  { cls: "slide", date: "2009-01-08", located: "crown" },
  { cls: "complex", date: "", located: "crown" },
];

describe("mass-movement filter", () => {
  it("is off by default", () => {
    expect(ev.filter(e => passesMass(e, DEFAULT_MASS_FILTER))).toHaveLength(0);
  });
  it("shows all, then only dated events, then one class", () => {
    const f = { ...DEFAULT_MASS_FILTER, on: true };
    expect(ev.filter(e => passesMass(e, f))).toHaveLength(4);
    expect(ev.filter(e => passesMass(e, { ...f, dated: true }))).toHaveLength(2);
    expect(ev.filter(e => passesMass(e, { ...f, classes: new Set(["rock_avalanche"]) }))).toHaveLength(2);
  });
  it("counts per class under the date filter only", () => {
    expect(massCounts(ev, { dated: false, classes: new Set(["slide"]) })).toEqual({ rock_avalanche: 2, slide: 1, complex: 1 });
    expect(massCounts(ev, { dated: true })).toEqual({ rock_avalanche: 1, slide: 1 });
  });
});

describe("mass-event height", async () => {
  const { groundTopKm } = await import("../scene/MassEventPoints.js");
  it("sits 15 m above the highest ground within 60 m", () => {
    const cliff = (x) => (x > 0.03 ? 2.0 : 1.9);   // a 100 m step 30 m east of the point
    expect(groundTopKm(cliff, 0, 0)).toBeCloseTo(2.015, 6);
    expect(groundTopKm(() => 1.5, 0, 0)).toBeCloseTo(1.515, 6);
  });
  it("ignores samples off the grid", () => {
    expect(groundTopKm((x) => (x < 0 ? null : 1.2), 0, 0)).toBeCloseTo(1.215, 6);
  });
});
