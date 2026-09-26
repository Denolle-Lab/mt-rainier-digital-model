// Hydrometeorological events (atlas/events/, written by rainier3d S29): hourly rain on the overview box and river
// discharge at gauges and seismic "virtual gauges". Optional: a bundle without events has no Events panel.

export async function loadEvents(base) {
  try {
    const r = await fetch(`${base}events/index.json`);
    return r.ok ? (await r.json()).events ?? [] : [];
  } catch { return []; }
}

export async function loadEvent(base, entry) {
  const doc = await (await fetch(`${base}${entry.path}`)).json();
  const dir = entry.path.replace(/[^/]+$/, "");
  const buf = await (await fetch(`${base}${dir}${doc.rain.file}`)).arrayBuffer();
  const frames = new Uint8Array(buf);
  if (frames.length !== doc.frames.count * doc.rain.width * doc.rain.height) throw new Error("rain frames: size mismatch");
  return { doc, frames };
}

// frame k -> its end time (UTC), as a Date
export const frameTime = (doc, k) => new Date(Date.parse(doc.frames.start) + k * doc.frames.stepHours * 3600e3);

// the AR window (seis-hydro-2-sed labels) that holds time t, or null
export function windowAt(doc, t) {
  const ms = t.getTime();
  return doc.windows.find(w => Date.parse(w.start) <= ms && ms < Date.parse(w.end)) ?? null;
}

// rain (mm/h) at a lon/lat from frame k; null outside the grid or where MRMS had no data
export function rainAt(doc, frames, k, lon, lat) {
  const { width: w, height: h, extent: e, scale, nodata } = doc.rain;
  const c = Math.floor(((lon - e.west) / (e.east - e.west)) * w), r = Math.floor(((e.north - lat) / (e.north - e.south)) * h);
  if (c < 0 || c >= w || r < 0 || r >= h) return null;
  const q = frames[k * w * h + r * w + c];
  return q === nodata ? null : q * scale;
}

// UTC and Pacific labels of a frame end time
export function timeLabels(t) {
  const utc = t.toISOString().slice(0, 16).replace("T", " ") + " UTC";
  const pst = new Date(t.getTime() - 8 * 3600e3).toISOString().slice(5, 16).replace("T", " ") + " PST";
  return { utc, pst };
}
