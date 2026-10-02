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

const fdsnCode = p => /^\w+\.\w+$/.test(p);

// The station marker an inventory site belongs to, by NET.STA code. Co-location is the inventory's (S8, 60 m): a GNSS
// site farther from the vault keeps its own point (MRSD 127 m from CC.PARA, P431 183 m from UW.WATCH, STAR 72 m from
// UW.STAR).
function markerOf(s, byCode) {
  return [s.id, ...s.name.split("+").map(c => c.trim())].map(c => byCode.get(c)).find(Boolean);
}
const codeIndex = stations => new Map(stations.sites.flatMap(s => s.codes.map(c => [c, s])));

// Points to draw: the inventory sites that do not belong to a station marker.
export function extraSites(sensors, stations) {
  const byCode = codeIndex(stations);
  return sensors.sites.filter(s => !markerOf(s, byCode));
}

// Instruments of the inventory sites that belong to a station marker and that the marker lacks (e.g. the GNSS MUIR,
// 17 m from UW.RCM; a tiltmeter missing from the EarthScope "active" list): marker id -> { kinds, names, retired }.
// They join the marker (ring, cards) instead of a second point, so no instrument is hidden and none is drawn twice.
// retired: the kinds that have ended there (all kinds of an ended site), with their dates.
export function mergedKinds(sensors, stations) {
  const byCode = codeIndex(stations), out = new Map(), live = new Set();
  for (const s of sensors.sites) {
    const hit = markerOf(s, byCode);
    const kinds = hit ? s.kinds.filter(k => !hit.kinds.includes(k)) : [];
    if (!kinds.length) continue;
    const m = out.get(hit.id) ?? { kinds: [], names: [], retired: {} };
    const ended = s.status === "operating" ? (s.retiredKinds ?? {}) : Object.fromEntries(kinds.map(k => [k, [s.start, s.end]]));
    for (const k of kinds) {
      if (!m.kinds.includes(k)) m.kinds.push(k);
      if (!ended[k]) { live.add(`${hit.id}|${k}`); delete m.retired[k]; }
      else if (!live.has(`${hit.id}|${k}`)) m.retired[k] = ended[k];
    }
    // the merged non-FDSN sites by name (e.g. "MUIR Camp Muir"); FDSN codes are on the marker already
    m.names.push(...s.name.split("+").map(c => c.trim()).filter(c => !fdsnCode(c)));
    out.set(hit.id, m);
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
