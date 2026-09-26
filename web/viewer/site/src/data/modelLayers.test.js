import { describe, expect, it, vi } from "vitest";
import { formatValue, groups, rampTicks, sampleValue } from "./modelLayers.js";

const box = { west: -122, east: -121, south: 46, north: 47 };
const cont = { kind: "continuous", units: "m", values: { width: 2, height: 2, scale: 0.5, offset: 1, nodata: 65535 } };
const cat = { kind: "categorical", units: "", values: { width: 2, height: 2, scale: 1, offset: 0, nodata: 65535 },
  legend: { classes: [{ value: 6, label: "Mount Rainier andesite", color: "#e07a5f" }] } };

describe("model layers", () => {
  it("samples rows north to south and decodes scale/offset", () => {
    const v = new Uint16Array([0, 2, 4, 65535]);
    expect(sampleValue(cont, v, box, -121.9, 46.9)).toBe(1);      // north-west cell
    expect(sampleValue(cont, v, box, -121.1, 46.9)).toBe(2);      // north-east
    expect(sampleValue(cont, v, box, -121.9, 46.1)).toBe(3);      // south-west
    expect(sampleValue(cont, v, box, -121.1, 46.1)).toBeNull();   // no data
    expect(sampleValue(cont, v, box, -123, 46.5)).toBeNull();     // outside
  });
  it("formats values and classes", () => {
    expect(formatValue(cont, 1.234)).toBe("1.23 m");
    expect(formatValue(cont, 123.4)).toBe("123 m");
    expect(formatValue(cat, 6)).toBe("Mount Rainier andesite");
    expect(formatValue(cont, null)).toBe("no data");
  });
  it("puts log-ramp middle tick at the geometric mean", () => {
    expect(rampTicks({ min: 0.1, max: 100, log: true })).toEqual(["0.1", "3.2", "100"]);
    expect(rampTicks({ min: 0, max: 250, log: false })).toEqual(["0", "125", "250"]);
    expect(rampTicks({ min: 3450, max: 6600, log: false, saturates: true })).toEqual(["≤ 3450", "5025", "≥ 6600"]);
  });
  it("groups layers in first-seen order", () => {
    expect(groups([{ key: "a", group: "G" }, { key: "b", group: "H" }, { key: "c", group: "G" }]).map(g => g.layers.length)).toEqual([2, 1]);
  });
});

describe("loadValues", () => {
  it("resolves to null on a failed fetch and does not cache the failure", async () => {
    const { loadValues } = await import("./modelLayers.js");
    const model = { base: "/m/" }, layer = { values: { file: "x.u16.bin" } };
    const f = vi.fn(async () => ({ ok: false, status: 404 }));
    vi.stubGlobal("fetch", f);
    expect(await loadValues(model, layer)).toBeNull();
    vi.stubGlobal("fetch", vi.fn(async () => ({ ok: true, arrayBuffer: async () => new Uint16Array([7, 8]).buffer })));
    expect(Array.from(await loadValues(model, layer))).toEqual([7, 8]);   // retried, not served from cache
    vi.unstubAllGlobals();
  });
});
