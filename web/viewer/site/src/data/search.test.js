import { describe, expect, it } from "vitest";
import { bundleFixture } from "../test/fixtures.js";
import { searchStations } from "./search.js";

describe("searchStations", () => {
  const b = bundleFixture();
  it("finds by site name, majors first", () => { expect(searchStations(b, "muir")[0].id).toBe("UW.RCM"); });
  it("finds by code with or without the network", () => {
    expect(searchStations(b, "lon9").map(r => r.id)).toEqual(["UW.LON"]);
    expect(searchStations(b, "cc.pali").map(r => r.id)).toEqual(["CC.PALI"]);
  });
  it("returns a site once even when several codes match", () => { expect(searchStations(b, "lo").filter(r => r.id === "UW.LON")).toHaveLength(1); });
  it("needs two characters", () => { expect(searchStations(b, "m")).toEqual([]); });
});
