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

export const DEFAULT_FILTER = { permanent: true, temporary: true, past: false, kinds: null };   // kinds: null = all

export function passes(site, f) {
  if (site.temporary ? !f.temporary : !f.permanent) return false;
  if (site.status !== "operating" && !f.past) return false;
  return !f.kinds || site.kinds.some(k => f.kinds.has(k));
}

// Points to draw: inventory sites that are not station markers already (matched by NET.STA code), and, for sites
// that are, a point with only the instrument kinds the marker does not show (e.g. a tiltmeter missing from the
// EarthScope "active" list), so no instrument is hidden.
export function extraSites(sensors, stations) {
  const markerKinds = new Map();
  for (const s of stations.sites) for (const c of s.codes) markerKinds.set(c, new Set(s.kinds));
  const out = [];
  for (const s of sensors.sites) {
    const codes = [s.id, ...s.name.split("+").map(c => c.trim())];
    const hit = codes.find(c => markerKinds.has(c));
    if (!hit) { out.push(s); continue; }
    const missing = s.kinds.filter(k => !markerKinds.get(hit).has(k));
    if (missing.length) out.push({ ...s, id: `${s.id}+extra`, kinds: missing });
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
  for (const s of sites) if (passes(s, { ...f, kinds: null })) for (const k of s.kinds) out[k] = (out[k] ?? 0) + 1;
  return out;
}
