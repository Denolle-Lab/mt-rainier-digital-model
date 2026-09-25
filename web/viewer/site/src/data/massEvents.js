// Mass-movement catalogue (atlas/model/mass_events.json, written by rainier3d S24/S11): mapped landslides at their
// crown, recent landslides, and seismically recorded rock falls, avalanches and debris flows. The flow deposits
// (lahars, debris flows) are a draped model layer, "mass_flows", not points.

export async function loadMassEvents(base) {
  try {
    const r = await fetch(`${base}model/mass_events.json`);
    return r.ok ? await r.json() : null;
  } catch { return null; }
}

// on: the layer is shown; classes: null = all; dated: only events with a date (observed or seismically recorded)
export const DEFAULT_MASS_FILTER = { on: false, classes: null, dated: false };

export const isSeismic = e => e.located === "seismic";

export function passesMass(e, f) {
  if (!f.on) return false;
  if (f.dated && !e.date) return false;
  return !f.classes || f.classes.has(e.cls);
}

// Count per class under the date filter, not the class filter (the legend shows what a click would bring back).
export function massCounts(events, f) {
  const out = {};
  for (const e of events) if (!f.dated || e.date) out[e.cls] = (out[e.cls] ?? 0) + 1;
  return out;
}
