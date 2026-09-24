// A small stations bundle shaped like site/public/atlas/stations.json.
const inst = (kind, band, channels, rate = 100) => ({ kind, band, channels, rate });
const station = (code, extra = {}) => ({ code, network: code.split(".")[0], operator: "Pacific Northwest Seismic Network", siteName: `${code.split(".")[1]} vault`, elev: 1000, depth: 0, since: "2010-01-01", instruments: [inst("seismometer", "broadband", ["HHE", "HHN", "HHZ"])], ...extra });
export function bundleFixture() {
  const sites = [
    { id: "UW.RCM", name: "Camp Muir", codes: ["UW.RCM"], x: 2.07, z: 1.9, elev: 3076, kinds: ["seismometer", "gnss"], since: "2024-09-09", onMap: true, major: "Camp Muir, broadband + GNSS",
      stations: [station("UW.RCM", { elev: 3076, instruments: [inst("seismometer", "broadband", ["HHE", "HHN", "HHZ"]), inst("gnss", null, ["GAN"], 1)] })] },
    { id: "UW.LON", name: "Longmire", codes: ["UW.LO2", "UW.LON", "UW.LON9"], x: -3.8, z: 11.4, elev: 853, kinds: ["seismometer", "accelerometer", "tiltmeter"], since: "2009-01-28", onMap: true, major: "Longmire, broadband + accelerometer + tiltmeters",
      stations: [station("UW.LO2", { instruments: [inst("seismometer", "short period", ["EHZ"])] }), station("UW.LON"), station("UW.LON9", { instruments: [inst("tiltmeter", null, ["HAE", "HAN"], 40)] })] },
    { id: "CC.PALI", name: "Palisades", codes: ["CC.PALI"], x: 3.8, z: -25.3, elev: 1420, kinds: ["seismometer", "infrasound"], since: "2025-09-17", onMap: true, major: null,
      stations: [station("CC.PALI", { network: "CC", operator: "USGS Cascades Volcano Observatory", instruments: [inst("seismometer", "broadband", ["BHZ"], 50), inst("infrasound", null, ["BDF"], 50)] })] },
    { id: "PB.B941", name: "Mt Rainier borehole", codes: ["PB.B941"], x: -35, z: -14.9, elev: 151, kinds: ["seismometer", "strainmeter"], since: "2008-03-18", onMap: false, major: null,
      stations: [station("PB.B941", { network: "PB", operator: "EarthScope borehole network", depth: 153, instruments: [inst("seismometer", "short period", ["EH1", "EH2", "EHZ"]), inst("strainmeter", null, ["BS1"], 20)] })] },
  ];
  const stations = { asOf: "2026-09-23", kinds: ["seismometer", "geophone", "infrasound", "accelerometer", "gnss", "tiltmeter", "strainmeter"], sites,
    counts: { stations: 7, sites: 4, sitesOnMap: 3, stationsOnMap: 6 }, excluded: [{ code: "C0.PALI", reason: "duplicate of CC.PALI" }] };
  return { stations, siteById: Object.fromEntries(sites.map(s => [s.id, s])), majors: sites.filter(s => s.major), base: "atlas/",
    terrain: { meta: { source: "USGS 3DEP elevation and USGS The National Map imagery (public domain)" } } };
}
