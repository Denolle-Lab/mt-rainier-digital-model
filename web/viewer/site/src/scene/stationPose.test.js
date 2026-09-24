import { describe, expect, it } from "vitest";
import { PLACES, placePose, STATION_VIEW, stationPose } from "./stationPose.js";

const len = v => Math.hypot(...v);
const sub = (a, b) => a.map((x, i) => x - b[i]);

describe("stationPose", () => {
  it("frames a station from 9 km at 28° on the side away from the summit", () => {
    const { pos, target } = stationPose({ x: 5, z: 0, y: 2 }, [0, 30, 60]);
    const off = sub(pos, target);
    expect(target).toEqual([5, 2, 0]);
    expect(len(off)).toBeCloseTo(STATION_VIEW.dist);
    expect((Math.asin(off[1] / len(off)) * 180) / Math.PI).toBeCloseTo(28, 1);
    expect(off[0]).toBeGreaterThan(0);
    expect(Math.abs(off[2])).toBeLessThan(1e-9);
  });
  it("near the summit keeps the current heading", () => {
    const { pos, target } = stationPose({ x: 0.3, z: 0.2, y: 3.4 }, [-10, 4, 0.2]);
    const off = sub(pos, target);
    expect(off[0]).toBeLessThan(0);
    expect(Math.abs(off[2])).toBeLessThan(0.01 * len(off));
  });
  it("from underground the camera still ends above the station", () => {
    const { pos, target } = stationPose({ x: 0.1, z: 0.1, y: 4.3 }, [0.1, -30, 0.1]);   // straight below: no heading
    expect(pos[1]).toBeGreaterThan(target[1] + 4);
    expect(len(sub(pos, target))).toBeCloseTo(STATION_VIEW.dist);
  });
});

describe("places", () => {
  it("lists the eight places", () => {
    expect(PLACES.map(p => p.key)).toEqual(["home", "summit", "paradise", "carbon", "white", "nisqually", "under", "side"]);
  });
  it("puts a river place's target on the ground, 12 km out at 35° from the south-west", () => {
    const p = placePose(PLACES.find(p => p.key === "paradise"), () => 1.6);
    const off = sub(p.pos, p.target);
    expect(p.target[1]).toBe(1.6);
    expect(len(off)).toBeCloseTo(12);
    expect(off[0]).toBeLessThan(0); expect(off[2]).toBeGreaterThan(0);
  });
});
