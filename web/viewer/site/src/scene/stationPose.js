import { toX, toZ } from "./geo.js";

// A station is framed from 9 km out, 28° above the horizon, on the side away from the summit so the mountain rises
// behind it. Within 1 km of the summit there is no "away", so the current heading is kept (south if there is none).
export const STATION_VIEW = { dist: 9, elevDeg: 28 };

export function stationPose(site, cam) {
  const target = [site.x, site.y, site.z];
  let hx = site.x, hz = site.z;
  if (Math.hypot(hx, hz) < 1) { hx = cam[0] - site.x; hz = cam[2] - site.z; }
  if (Math.hypot(hx, hz) < 1e-6) { hx = 0; hz = 1; }
  const hl = Math.hypot(hx, hz), el = (STATION_VIEW.elevDeg * Math.PI) / 180, d = STATION_VIEW.dist;
  return { pos: [site.x + (hx / hl) * Math.cos(el) * d, site.y + Math.sin(el) * d, site.z + (hz / hl) * Math.cos(el) * d], target };
}

// Places in Go to. Fixed poses for the overview and the summit crater; the valleys are framed 12 km out at 35° from
// the south-west, targeting the ground at the place.
export const PLACES = [
  { key: "home", label: "Whole area", pos: [-34, 30, 58], target: [0, 0.5, 2] },
  { key: "summit", label: "Summit crater", pos: [-0.55, 4.72, 0.95], target: [0.05, 4.33, 0] },
  { key: "paradise", label: "Paradise", lat: 46.786, lon: -121.735 },
  { key: "carbon", label: "Carbon River", lat: 46.99, lon: -121.92 },
  { key: "white", label: "White River", lat: 46.9, lon: -121.64 },
  { key: "nisqually", label: "Nisqually", lat: 46.74, lon: -121.8 },
];

export function placePose(place, elevKm) {
  if (place.pos) return { pos: place.pos, target: place.target };
  const x = toX(place.lon), z = toZ(place.lat), y = elevKm(x, z) ?? 0;
  const el = (35 * Math.PI) / 180, d = 12, h = Math.cos(el) * d * Math.SQRT1_2;
  return { pos: [x - h, y + Math.sin(el) * d, z + h], target: [x, y, z] };
}
