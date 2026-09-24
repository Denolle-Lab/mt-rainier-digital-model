export class BundleMissingError extends Error {
  constructor() { super("The atlas data bundle has not been built yet."); this.name = "BundleMissingError"; }
}
export const BUILD_COMMAND = "cd data && ../.venv/bin/python -m rainier.build --out ../site/public/atlas --cache cache";

async function get(url, kind) {
  const r = await fetch(url);
  if (!r.ok) throw Object.assign(new Error(`${url}: HTTP ${r.status}`), { status: r.status });
  return kind === "bin" ? r.arrayBuffer() : r.json();
}

export async function loadBundle(base = `${import.meta.env.BASE_URL}atlas/`) {
  let meta;
  try { meta = await get(`${base}terrain/terrain.json`); } catch (e) { if (e.status === 404) throw new BundleMissingError(); throw e; }
  const [heights, summit, stations] = await Promise.all([
    get(`${base}terrain/overview.bin`, "bin").then(b => new Int16Array(b)),
    get(`${base}summit/index.json`),
    get(`${base}stations.json`),
  ]);
  const siteById = Object.fromEntries(stations.sites.map(s => [s.id, s]));
  const quakes = await Promise.all([get(`${base}quakes.bin`, "bin"), get(`${base}quakes.json`)])
    .then(([bin, meta]) => ({ records: new Float32Array(bin), meta }), () => null);   // phase 2 data is optional
  return {
    base, summit, stations, siteById, quakes,
    terrain: { meta, heights, imageUrl: `${base}terrain/overview.jpg` },
    majors: stations.sites.filter(s => s.major),
  };
}
