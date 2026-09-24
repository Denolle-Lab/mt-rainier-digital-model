// Earthquake density on a regular grid over the map volume, for the density shells.
// Index = res² · k + res · j + i (the MarchingCubes field layout); i → x, j → y, k → z.
export const GRID = { res: 72, xz: 30, bottom: -20, top: 4.6 };

const mid = g => (g.bottom + g.top) / 2, half = g => (g.top - g.bottom) / 2;
const toI = (x, g) => ((x / g.xz + 1) / 2) * (g.res - 1);
const toJ = (y, g) => (((y - mid(g)) / half(g) + 1) / 2) * (g.res - 1);

export function worldOf(i, j, k, g) {
  const u = v => (v / (g.res - 1)) * 2 - 1;
  return [u(i) * g.xz, u(j) * half(g) + mid(g), u(k) * g.xz];
}

export function splat(records, g) {
  const n = g.res, f = new Float32Array(n ** 3);
  for (let r = 0; r < records.length; r += 4) {
    const i = Math.round(toI(records[r], g)), j = Math.round(toJ(records[r + 1], g)), k = Math.round(toI(records[r + 2], g));
    if (i < 1 || j < 1 || k < 1 || i > n - 2 || j > n - 2 || k > n - 2) continue;
    f[n * n * k + n * j + i] += 1;
  }
  return f;
}

// Separable Gaussian blur with a normalized kernel; σ per axis in cells (x, y, z).
export function blur3d(src, n, sig) {
  let a = src;
  for (let axis = 0; axis < 3; axis++) {
    const s = sig[axis], r = Math.ceil(s * 3), k = [];
    let ks = 0;
    for (let i = -r; i <= r; i++) { k.push(Math.exp(-(i * i) / (2 * s * s))); ks += k[k.length - 1]; }
    const stride = [1, n, n * n][axis], b = new Float32Array(src.length);
    for (let z = 0; z < n; z++) for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) {
      const c = [x, y, z][axis], base = n * n * z + n * y + x;
      let acc = 0;
      for (let i = -r; i <= r; i++) { const cc = c + i; if (cc >= 0 && cc < n) acc += a[base + i * stride] * k[i + r]; }
      b[base] = acc / ks;
    }
    a = b;
  }
  return a;
}

export function trimAboveGround(field, g, elevKm) {
  const n = g.res;
  for (let k = 0; k < n; k++) for (let i = 0; i < n; i++) {
    const [x, , z] = worldOf(i, 0, k, g), e = elevKm(x, z) ?? 0;
    for (let j = 0; j < n; j++) if (worldOf(i, j, k, g)[1] > e) field[n * n * k + n * j + i] = 0;
  }
}

// The density level above which the given fraction of all mass lies (one threshold per fraction).
export function massThresholds(field, fractions) {
  const vals = Array.from(field).filter(v => v > 0).sort((a, b) => b - a);
  const total = vals.reduce((s, v) => s + v, 0);
  if (!total) return fractions.map(() => 0);
  return fractions.map(fr => {
    let acc = 0;
    for (const v of vals) { acc += v; if (acc >= fr * total - 1e-9) return v; }
    return vals[vals.length - 1];
  });
}
