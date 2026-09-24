// Stations by code (with or without the network) or site name. Majors rank first; a site appears once.
export function searchStations(bundle, q) {
  const s = q.trim().toLowerCase();
  if (s.length < 2) return [];
  const hits = [];
  for (const site of bundle.stations.sites) {
    const codes = site.codes.map(c => c.toLowerCase()), shorts = codes.map(c => c.split(".")[1]);
    const exact = codes.includes(s) || shorts.includes(s);
    const match = exact || codes.some(c => c.includes(s)) || site.name.toLowerCase().includes(s);
    if (match) hits.push({ id: site.id, title: site.name, sub: site.codes.join(" · "), rank: (exact ? 0 : 2) + (site.major ? 0 : 1) });
  }
  return hits.sort((a, b) => a.rank - b.rank || a.title.localeCompare(b.title)).slice(0, 8).map(({ rank, ...r }) => r);
}
