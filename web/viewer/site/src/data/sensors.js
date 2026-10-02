// All sensors: the rainier3d inventory (atlas/model/sensors.json, written by S11 from S8) merged with the
// EarthScope stations of the base bundle. Sites already drawn as station markers are not drawn twice.

// FDSN convention: network codes starting with a digit or X, Y, Z are temporary; TA is a moving deployment.
export const isTemporaryNet = net => /^[0-9XYZ]/.test(net) || net === "TA";

export async function loadSensors(base) {
  try {
    const r = await fetch(`${base}model/sensors.json`);
    return r.ok ? await r.json() : null;
  } catch { return null; }
}

// Current / Past split the sites by status. A survey (sensors.json "surveys", configs/sensor_surveys.yaml) that is
// on shows all its sites whatever Current / Past say; one that is off leaves them to Current / Past like any other
// site. Permanent / temporary stays on each site for its glyph (disc / ring).
export const DEFAULT_FILTER = { current: true, past: false, surveysOff: new Set(), kinds: null };   // kinds: null = all

export const surveyOn = (f, key) => !f.surveysOff.has(key);

const inSurvey = (site, f) => !!site.survey && surveyOn(f, site.survey);
const byStatus = (site, f) => (site.status === "operating" ? f.current : f.past);

// Kinds for the kind toggles and counts: at a running site, not those whose instruments have all ended (the
// infrasound of CC.PR01, 2018-10 – 2020-06). The ring and the cards keep them, with their dates: a site's kinds say
// what it holds or has held.
export const liveKinds = site => site.kinds.filter(k => !site.retiredKinds?.[k]);

export function passes(site, f) {
  if (!inSurvey(site, f) && !byStatus(site, f)) return false;
  return !f.kinds || liveKinds(site).some(k => f.kinds.has(k));
}

// Faded (past) unless operating or shown by its survey.
export const faded = (site, f) => site.status !== "operating" && !inSurvey(site, f);

// The DAS fiber, like a site: its survey's toggle, else Current / Past by its status.
export const fiberOn = (das, f) => !!das && (inSurvey(das, f) || byStatus(das, f));

// Points to draw: the inventory sites that are not station markers already (matched by NET.STA code).
export function extraSites(sensors, stations) {
  const codes = new Set(stations.sites.flatMap(s => s.codes));
  return sensors.sites.filter(s => ![s.id, ...s.name.split("+").map(c => c.trim())].some(c => codes.has(c)));
}

// Instruments the inventory merged into a station marker's site that the marker lacks (e.g. the GNSS MUIR, 17 m
// from UW.RCM; a tiltmeter missing from the EarthScope "active" list): marker id -> { kinds, names }. They join the
// marker (ring, card) instead of a second point, so no instrument is hidden and none is drawn twice.
export function mergedKinds(sensors, stations) {
  const byCode = new Map(stations.sites.flatMap(s => s.codes.map(c => [c, s])));
  const out = new Map();
  for (const s of sensors.sites) {
    const parts = s.name.split("+").map(c => c.trim());
    const hit = [s.id, ...parts].map(c => byCode.get(c)).find(Boolean);
    const kinds = hit ? s.kinds.filter(k => !hit.kinds.includes(k)) : [];
    if (!kinds.length) continue;
    // the merged non-FDSN sites by name (e.g. "MUIR Camp Muir"); FDSN codes are on the marker already
    const retired = Object.fromEntries(kinds.filter(k => s.retiredKinds?.[k]).map(k => [k, s.retiredKinds[k]]));
    out.set(hit.id, { kinds, names: parts.filter(p => !/^\w+\.\w+$/.test(p)), retired });
  }
  return out;
}

// Station markers get the same classification (all EarthScope stations here are operating).
export function classifyMarker(site) {
  return { ...site, temporary: site.codes.every(c => isTemporaryNet(c.split(".")[0])), status: "operating" };
}

// Count per kind for the legend, under the network and past filters but not the kind filter.
export function kindCounts(sites, f) {
  const out = {};
  for (const s of sites) if (passes(s, { ...f, kinds: null })) for (const k of liveKinds(s)) out[k] = (out[k] ?? 0) + 1;
  return out;
}
