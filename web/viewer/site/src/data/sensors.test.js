import { describe, expect, it } from "vitest";
import { DEFAULT_FILTER, classifyMarker, extraSites, faded, fiberOn, isTemporaryNet, kindCounts, liveKinds, mergedKinds, passes } from "./sensors.js";

const node = { id: "node-1", kinds: ["geophone"], temporary: true, status: "operating" };
const old = { id: "XD.A1", kinds: ["seismometer"], temporary: true, status: "retired" };
const gnss = { id: "gnss-P432", kinds: ["gnss"], temporary: false, status: "operating" };
const z5 = { id: "Z5.001", kinds: ["geophone"], temporary: true, status: "retired", survey: "nodes_2025" };

describe("sensors", () => {
  it("classifies FDSN temporary networks", () => {
    expect(["XD", "Z5", "2N", "TA"].every(isTemporaryNet)).toBe(true);
    expect(["UW", "CC", "PB", "NP"].some(isTemporaryNet)).toBe(false);
    expect(classifyMarker({ codes: ["UW.STAR"] }).temporary).toBe(false);
  });
  it("filters by status, survey and kind", () => {
    expect(passes(node, DEFAULT_FILTER)).toBe(true);
    expect(passes(old, DEFAULT_FILTER)).toBe(false);                       // past deployments off by default
    expect(passes(old, { ...DEFAULT_FILTER, past: true })).toBe(true);
    expect(passes(node, { ...DEFAULT_FILTER, current: false })).toBe(false);
    expect(passes(gnss, { ...DEFAULT_FILTER, kinds: new Set(["geophone"]) })).toBe(false);
  });
  it("shows a survey that is on whatever Current and Past say, and leaves it to them when off", () => {
    const off = { ...DEFAULT_FILTER, surveysOff: new Set(["nodes_2025", "mora_das"]) };
    expect(passes(z5, DEFAULT_FILTER)).toBe(true);                        // surveys on by default, though retired
    expect(passes(z5, { ...DEFAULT_FILTER, current: false, past: false })).toBe(true);
    expect(passes(z5, off)).toBe(false);                                  // off: retired, so under Past (off)
    expect(passes(z5, { ...off, past: true })).toBe(true);
    expect(faded(z5, DEFAULT_FILTER)).toBe(false);                        // opaque while its survey is on
    expect(faded(z5, off)).toBe(true);
    expect(faded(node, off)).toBe(false);                                 // operating: never faded
    const das = { survey: "mora_das", status: "operating" };
    expect(fiberOn(das, DEFAULT_FILTER)).toBe(true);
    expect(fiberOn(das, off)).toBe(true);                                 // off: operating, so under Current
    expect(fiberOn(das, { ...off, current: false })).toBe(false);
  });
  it("does not draw station-marker sites twice and counts per kind", () => {
    const sensors = { sites: [{ ...node, name: "Node 1" }, { ...gnss, name: "P432" }, { id: "UW.STAR", name: "UW.STAR", kinds: ["seismometer"], temporary: false, status: "operating" }] };
    expect(extraSites(sensors, { sites: [{ codes: ["UW.STAR"], kinds: ["seismometer"] }] }).map(s => s.id)).toEqual(["node-1", "gnss-P432"]);
    const pupy = { id: "UW.PUPY", name: "UW.PUPY", kinds: ["seismometer", "tiltmeter"], temporary: false, status: "operating" };
    const markers = { sites: [{ id: "UW.PUPY", codes: ["UW.PUPY"], kinds: ["seismometer"] },
      { id: "UW.RCM", codes: ["UW.RCM"], kinds: ["seismometer"] }] };
    const rcm = { id: "UW.RCM", name: "UW.RCM + MUIR Camp Muir", kinds: ["gnss", "seismometer"], status: "operating" };
    expect(extraSites({ sites: [pupy, rcm] }, markers)).toEqual([]);     // merged into the markers, not drawn again
    expect([...mergedKinds({ sites: [pupy, rcm] }, markers)]).toEqual([   // only what the marker lacks
      ["UW.PUPY", { kinds: ["tiltmeter"], names: [], retired: {} }],
      ["UW.RCM", { kinds: ["gnss"], names: ["MUIR Camp Muir"], retired: {} }]]);
    expect(kindCounts([node, old, gnss], DEFAULT_FILTER)).toEqual({ geophone: 1, gnss: 1 });
  });
  it("joins a GNSS site to a station marker within 200 m, and only a GNSS site", () => {
    const para = { id: "CC.PARA", codes: ["CC.PARA"], kinds: ["seismometer"], lat: 46.786, lon: -121.7424 };
    const mrsd = { id: "gnss-MRSD", name: "MRSD Mount Rainier Ski Dorm Bldg", kinds: ["gnss"], status: "operating",
      lat: 46.7853, lon: -121.7420 };                                                     // 127 m from CC.PARA
    const snrs = { ...mrsd, id: "gnss-SNRS", name: "SNRS Sunrise Ski Dorm", lat: 46.8190 };   // 3.7 km
    const kchw1 = { ...mrsd, id: "syn-KCHW1", name: "KCHW1", kinds: ["hydromet"] };          // weather: not by distance
    expect(extraSites({ sites: [mrsd, snrs, kchw1] }, { sites: [para] }).map(s => s.id)).toEqual(["gnss-SNRS", "syn-KCHW1"]);
    expect(mergedKinds({ sites: [mrsd] }, { sites: [para] }).get("CC.PARA"))
      .toEqual({ kinds: ["gnss"], names: ["MRSD Mount Rainier Ski Dorm Bldg"], retired: {} });
    const star = { ...mrsd, status: "retired", start: "2008-09-11", end: "2011-09-11" };   // an ended GNSS site
    expect(mergedKinds({ sites: [star] }, { sites: [para] }).get("CC.PARA").retired).toEqual({ gnss: ["2008-09-11", "2011-09-11"] });
  });
  it("keeps an ended instrument in the site's kinds but not in the filter and counts", () => {
    const pr01 = { id: "CC.PR01", name: "CC.PR01", kinds: ["infrasound", "seismometer"], temporary: false, status: "operating",
      retiredKinds: { infrasound: ["2018-10-04", "2020-06-08"] } };
    const m = mergedKinds({ sites: [pr01] }, { sites: [{ id: "CC.PR01", codes: ["CC.PR01"], kinds: ["seismometer"] }] });
    expect(m.get("CC.PR01")).toEqual({ kinds: ["infrasound"], names: [], retired: { infrasound: ["2018-10-04", "2020-06-08"] } });
    expect(liveKinds(pr01)).toEqual(["seismometer"]);
    expect(passes(pr01, { ...DEFAULT_FILTER, kinds: new Set(["infrasound"]) })).toBe(false);   // no infrasound now
    expect(kindCounts([pr01], DEFAULT_FILTER)).toEqual({ seismometer: 1 });
  });
});
