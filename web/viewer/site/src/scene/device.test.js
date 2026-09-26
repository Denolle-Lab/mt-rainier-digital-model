import { describe, expect, it } from "vitest";
import { PROFILES, deviceProfile, liteProfile } from "./device.js";

const win = ({ search = "", coarse = false, deviceMemory } = {}) => ({
  location: { search },
  matchMedia: q => ({ matches: q === "(pointer: coarse)" && coarse }),
  navigator: deviceMemory == null ? {} : { deviceMemory },
});

describe("device profile", () => {
  it("desktop is full, a touch screen or a 4 GB device is lite", () => {
    expect(liteProfile(win())).toBe(false);
    expect(liteProfile(win({ coarse: true }))).toBe(true);
    expect(liteProfile(win({ deviceMemory: 4 }))).toBe(true);
    expect(liteProfile(win({ deviceMemory: 8 }))).toBe(false);
  });
  it("?lite=1 and ?lite=0 override the detection", () => {
    expect(liteProfile(win({ search: "?lite=1" }))).toBe(true);
    expect(liteProfile(win({ search: "?lite=0", coarse: true }))).toBe(false);
  });
  it("the lite profile has 4x fewer terrain vertices and a smaller tile cache", () => {
    expect(deviceProfile(win({ coarse: true }))).toBe(PROFILES.lite);
    expect(PROFILES.lite.terrainStride).toBe(2);
    expect(PROFILES.lite.summitCap).toBeLessThan(PROFILES.full.summitCap);
  });
  it("no window (tests, SSR) is full", () => {
    expect(liteProfile(undefined)).toBe(false);
  });
});
