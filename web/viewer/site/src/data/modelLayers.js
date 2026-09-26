// rainier3d model surface layers (atlas/model/layers.json, written by mt-rainier-digital-model S11).
// Textures and value grids sit on the overview lon/lat box with square-degree pixels, rows north to south.

export async function loadModelLayers(base) {
  const r = await fetch(`${base}model/layers.json`);
  if (!r.ok) return null;   // the model bundle is optional
  const meta = await r.json();
  return { ...meta, base: `${base}model/`, byKey: Object.fromEntries(meta.layers.map(l => [l.key, l])) };
}

const cache = new Map();
// Value grid of a layer, or null when it cannot be fetched (the readout then stays off); failures are not cached.
export function loadValues(model, layer) {
  const url = model.base + layer.values.file;
  if (!cache.has(url)) {
    const p = fetch(url)
      .then(r => (r.ok ? r.arrayBuffer() : null))
      .then(b => (b ? new Uint16Array(b) : null))
      .catch(() => null)
      .then(v => { if (!v) cache.delete(url); return v; });
    cache.set(url, p);
  }
  return cache.get(url);
}

// Value at lon/lat, or null outside the model or where the layer has no data.
export function sampleValue(layer, values, box, lon, lat) {
  const { width: w, height: h, scale, offset, nodata } = layer.values;
  const c = Math.floor(((lon - box.west) / (box.east - box.west)) * w), r = Math.floor(((box.north - lat) / (box.north - box.south)) * h);
  if (c < 0 || r < 0 || c >= w || r >= h) return null;
  const q = values[r * w + c];
  if (q === nodata) return null;
  return layer.kind === "categorical" ? q : offset + q * scale;
}

export function formatValue(layer, v) {
  if (v == null) return "no data";
  if (layer.kind === "categorical") return layer.legend.classes.find(c => c.value === v)?.label ?? `class ${v}`;
  const a = Math.abs(v), d = a >= 100 ? 0 : a >= 10 ? 1 : 2;
  return `${v.toFixed(d)} ${layer.units}`.trim();
}

// Legend tick labels: ends and middle, in log space for log ramps; ≤ and ≥ mark ends where the colours saturate.
export function rampTicks(legend) {
  const { min, max, log, saturates } = legend;
  const mid = log ? Math.sqrt(min * max) : (min + max) / 2;
  const f = v => (Math.abs(v) >= 100 ? v.toFixed(0) : Math.abs(v) >= 10 ? v.toFixed(0) : v.toPrecision(2).replace(/\.?0+$/, ""));
  return saturates ? [`≤ ${f(min)}`, f(mid), `≥ ${f(max)}`] : [f(min), f(mid), f(max)];
}

export function groups(layers) {
  const out = [];
  for (const l of layers) {
    let g = out.find(x => x.name === l.group);
    if (!g) out.push((g = { name: l.group, layers: [] }));
    g.layers.push(l);
  }
  return out;
}
