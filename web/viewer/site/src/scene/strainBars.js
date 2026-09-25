// Strain orientation bars (atlas/model/strain_bars.json, written by rainier3d S11 from S24): for each elevation level
// (levels_km) and each set ("tectonic": GNSS axis of maximum shortening; "load": SHmax of the edifice load), a flat
// list x0, z0, x1, z1, ... of segment ends in scene km. The viewer draws the set of the selected property at the
// level nearest the depth slice.

export function nearestLevel(levels, km) {
  let best = -1, d = Infinity;
  levels.forEach((l, i) => { const e = Math.abs(l - km); if (e < d) { d = e; best = i; } });
  return best;
}

// flat x0, z0, x1, z1 list -> xyz positions for THREE.LineSegments at height y
export function segmentPositions(flat, y = 0) {
  const n = Math.floor(flat.length / 4), out = new Float32Array(n * 6);
  for (let i = 0; i < n; i++) {
    out.set([flat[4 * i], y, flat[4 * i + 1], flat[4 * i + 2], y, flat[4 * i + 3]], 6 * i);
  }
  return out;
}
