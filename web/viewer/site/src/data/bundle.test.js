import { afterEach, describe, expect, it, vi } from "vitest";
import { BundleMissingError, loadBundle } from "./bundle.js";
import { KINDS } from "./kinds.js";

const stations = {
  asOf: "2026-09-23", kinds: KINDS.map(k => k.key), counts: { stations: 3, sites: 2, sitesOnMap: 2, stationsOnMap: 3 },
  sites: [
    { id: "UW.RCM", name: "Camp Muir", codes: ["UW.RCM"], major: "Camp Muir, broadband + GNSS", onMap: true, kinds: ["seismometer"], stations: [{}] },
    { id: "CC.COPP", name: "Copper Mountain", codes: ["CC.COPP", "CC.X"], major: null, onMap: true, kinds: ["infrasound"], stations: [{}, {}] },
  ],
};
const files = {
  "atlas/terrain/terrain.json": { cols: 2, rows: 1, x0: 0, z0: 0, dx: 1, dz: 1 },
  "atlas/terrain/overview.bin": new Int16Array([100, 200]).buffer,
  "atlas/summit/index.json": { tile: 256, levels: [] },
  "atlas/stations.json": stations,
};
const respond = body => ({ ok: true, status: 200, json: async () => body, arrayBuffer: async () => body });

afterEach(() => vi.unstubAllGlobals());

describe("loadBundle", () => {
  it("loads terrain, summit index and stations, and indexes sites", async () => {
    vi.stubGlobal("fetch", vi.fn(async url => (url in files ? respond(files[url]) : { ok: false, status: 404 })));
    const b = await loadBundle("atlas/");
    expect(Array.from(b.terrain.heights)).toEqual([100, 200]);
    expect(b.terrain.imageUrl).toBe("atlas/terrain/overview.jpg");
    expect(b.siteById["CC.COPP"].name).toBe("Copper Mountain");
    expect(b.majors.map(s => s.id)).toEqual(["UW.RCM"]);
  });
  it("loads the earthquakes when the bundle has them, and tolerates their absence", async () => {
    const withQuakes = { ...files, "atlas/quakes.bin": new Float32Array([1, -2, 3, 1.5]).buffer, "atlas/quakes.json": { count: 1 } };
    vi.stubGlobal("fetch", vi.fn(async url => (url in withQuakes ? respond(withQuakes[url]) : { ok: false, status: 404 })));
    const b = await loadBundle("atlas/");
    expect(Array.from(b.quakes.records)).toEqual([1, -2, 3, 1.5]);
    expect(b.quakes.meta.count).toBe(1);
    vi.stubGlobal("fetch", vi.fn(async url => (url in files ? respond(files[url]) : { ok: false, status: 404 })));
    expect((await loadBundle("atlas/")).quakes).toBeNull();
  });
  it("reports a missing bundle", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => ({ ok: false, status: 404 })));
    await expect(loadBundle("atlas/")).rejects.toBeInstanceOf(BundleMissingError);
  });
  it("kinds match the bundle's kind list, each with a glyph and no blue", () => {
    expect(KINDS.map(k => k.key)).toEqual(["seismometer", "geophone", "infrasound", "accelerometer", "gnss", "tiltmeter", "strainmeter"]);
    const hue = hex => {
      const [r, g, b] = [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16) / 255);
      const mx = Math.max(r, g, b), d = mx - Math.min(r, g, b);
      const h = mx === r ? ((g - b) / d) % 6 : mx === g ? (b - r) / d + 2 : (r - g) / d + 4;
      return (h * 60 + 360) % 360;
    };
    for (const k of KINDS) {
      expect(k.glyph).toBeTruthy();
      const h = hue(k.color);
      expect(h > 195 && h < 235, `${k.key} ${k.color} hue ${h.toFixed(0)}° is earthquake blue`).toBe(false);
    }
    expect(new Set(KINDS.map(k => k.glyph)).size).toBe(KINDS.length);
  });
});
