import { describe, expect, it } from "vitest";
import { ringSize, ringSvg } from "./ring.js";

describe("ring", () => {
  it("one segment per instrument kind, in the kind color", () => {
    const svg = ringSvg(["seismometer", "infrasound"], 20);
    const segs = [...svg.matchAll(/<path class="seg"[^>]*/g)].map(m => m[0]);
    expect(segs).toHaveLength(2);
    expect(segs[0]).toContain('stroke="#d95926"');
    expect(segs[1]).toContain('stroke="#c98500"');
    expect(segs[0]).toContain('data-kind="seismometer"');
  });
  it("a single kind is a full circle", () => {
    const svg = ringSvg(["gnss"], 16);
    expect(svg.match(/<path class="seg"/g)).toHaveLength(1);
    expect(svg).toMatch(/ a [\d.]+ [\d.]+ 0 1 0/);
  });
  it("orders segments by kind order, whatever the input order", () => {
    const svg = ringSvg(["tiltmeter", "seismometer"], 20);
    expect(svg.indexOf("seismometer")).toBeLessThan(svg.indexOf("tiltmeter"));
  });
  it("sizes by the number of kinds", () => { expect([ringSize(1), ringSize(3), ringSize(5)]).toEqual([16, 20, 24]); });
});
