// The relocated PNSN catalogue (rainier3d S26): each event as located by ComCat, by NonLinLoc in the PNSN 1D model,
// and by NonLinLoc in the rainier3d 3D model, in the scene frame (km; y is elevation). Optional: null when the bundle
// has no quakes_relocated.* files. Record layout: meta.fields (x_cc … z_3d, mag, quality 3/2/1 = A/B/C, gap).
export async function loadRelocated(base) {
  try {
    const [b, j] = await Promise.all([fetch(`${base}quakes_relocated.bin`), fetch(`${base}quakes_relocated.json`)]);
    if (!b.ok || !j.ok) return null;
    return { records: new Float32Array(await b.arrayBuffer()), meta: await j.json() };
  } catch { return null; }
}

// on: the layer is shown; catalog: cc | 1d | 3d; lines: 1D -> 3D shift segments; minQuality: 2 = A and B, 1 = all
export const DEFAULT_RELOCATED = { on: false, catalog: "3d", lines: false, minQuality: 2 };

const col = (meta, name) => meta.fields.indexOf(name);

// Positions (x, y, z per event) and magnitudes of one catalogue, for events of at least `minQuality`.
export function selectCatalog({ records, meta }, catalog, minQuality = 2) {
  const k = meta.fields.length, n = records.length / k;
  const [ix, iy, iz] = ["x", "y", "z"].map(a => col(meta, `${a}_${catalog}`));
  const im = col(meta, "mag"), iq = col(meta, "quality");
  const pos = [], mag = [];
  for (let i = 0; i < n; i++) {
    const r = records.subarray(i * k, (i + 1) * k);
    if (r[iq] < minQuality || ![r[ix], r[iy], r[iz], r[im]].every(Number.isFinite)) continue;
    pos.push(r[ix], r[iy], r[iz]); mag.push(r[im]);
  }
  return { pos: new Float32Array(pos), mag: new Float32Array(mag), n: mag.length };
}

// Line segments (6 floats per event) from one catalogue's location to another's, for events of at least `minQuality`.
export function shiftSegments({ records, meta }, from, to, minQuality = 2) {
  const k = meta.fields.length, n = records.length / k, iq = col(meta, "quality");
  const a = ["x", "y", "z"].map(c => col(meta, `${c}_${from}`)), b = ["x", "y", "z"].map(c => col(meta, `${c}_${to}`));
  const out = [];
  for (let i = 0; i < n; i++) {
    const r = records.subarray(i * k, (i + 1) * k);
    if (r[iq] < minQuality || ![...a, ...b].every(j => Number.isFinite(r[j]))) continue;
    out.push(...a.map(j => r[j]), ...b.map(j => r[j]));
  }
  return new Float32Array(out);
}

// Events whose location lies above the ground (elevKm(x, z) returns the terrain elevation in km, or null outside).
export function countAboveGround(pos, elevKm) {
  let n = 0;
  for (let i = 0; i < pos.length; i += 3) { const g = elevKm(pos[i], pos[i + 2]); if (g != null && pos[i + 1] > g) n++; }
  return n;
}
