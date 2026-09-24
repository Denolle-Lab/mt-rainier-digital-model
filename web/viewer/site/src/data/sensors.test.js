import { describe, expect, it } from "vitest";
import { DEFAULT_FILTER, classifyMarker, extraSites, isTemporaryNet, kindCounts, passes } from "./sensors.js";

const node = { id: "node-1", kinds: ["geophone"], temporary: true, status: "operating" };
const old = { id: "XD.A1", kinds: ["seismometer"], temporary: true, status: "retired" };
const gnss = { id: "gnss-P432", kinds: ["gnss"], temporary: false, status: "operating" };

describe("sensors", () => {
  it("classifies FDSN temporary networks", () => {
    expect(["XD", "Z5", "2N", "TA"].every(isTemporaryNet)).toBe(true);
    expect(["UW", "CC", "PB", "NP"].some(isTemporaryNet)).toBe(false);
    expect(classifyMarker({ codes: ["UW.STAR"] }).temporary).toBe(false);
  });
  it("filters by permanence, past deployments and kind", () => {
    expect(passes(node, DEFAULT_FILTER)).toBe(true);
    expect(passes(old, DEFAULT_FILTER)).toBe(false);                       // past deployments off by default
    expect(passes(old, { ...DEFAULT_FILTER, past: true })).toBe(true);
    expect(passes(node, { ...DEFAULT_FILTER, temporary: false })).toBe(false);
    expect(passes(gnss, { ...DEFAULT_FILTER, kinds: new Set(["geophone"]) })).toBe(false);
  });
  it("does not draw station-marker sites twice and counts per kind", () => {
    const sensors = { sites: [{ ...node, name: "Node 1" }, { ...gnss, name: "P432" }, { id: "UW.STAR", name: "UW.STAR", kinds: ["seismometer"], temporary: false, status: "operating" }] };
    expect(extraSites(sensors, { sites: [{ codes: ["UW.STAR"], kinds: ["seismometer"] }] }).map(s => s.id)).toEqual(["node-1", "gnss-P432"]);
    const pupy = { id: "UW.PUPY", name: "UW.PUPY", kinds: ["seismometer", "tiltmeter"], temporary: false, status: "operating" };
    const extra = extraSites({ sites: [pupy] }, { sites: [{ codes: ["UW.PUPY"], kinds: ["seismometer"] }] });
    expect(extra.map(s => [s.id, s.kinds])).toEqual([["UW.PUPY+extra", ["tiltmeter"]]]);   // only what the marker lacks
    expect(kindCounts([node, old, gnss], DEFAULT_FILTER)).toEqual({ geophone: 1, gnss: 1 });
  });
});
