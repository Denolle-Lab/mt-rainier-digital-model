import * as THREE from "three";

// The open-sided block under the map: a floor grid every 10 km, corner posts from sea level to the floor, and a depth
// ruler at the south-west corner. No side walls: the open sides are how the default view shows what is underground.
export function makeFrame({ xmin, xmax, zmin, zmax, bottom = -20 }) {
  const group = new THREE.Group(), pts = [], clampZ = z => Math.max(zmin, Math.min(zmax, z));
  for (let x = -30; x <= 30; x += 10) pts.push(x, bottom, zmin, x, bottom, zmax);
  for (let z = -30; z <= 30; z += 10) pts.push(xmin, bottom, clampZ(z), xmax, bottom, clampZ(z));
  for (const [x, z] of [[xmin, zmin], [xmax, zmin], [xmin, zmax], [xmax, zmax]]) pts.push(x, 0, z, x, bottom, z);
  const g = new THREE.BufferGeometry(); g.setAttribute("position", new THREE.Float32BufferAttribute(pts, 3));
  group.add(new THREE.LineSegments(g, new THREE.LineBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.08 })));
  const rp = [], ticks = [];
  for (let d = 0; d >= bottom; d -= 5) {
    rp.push(xmin, d, zmax, xmin - 0.7, d, zmax);
    ticks.push({ label: d === 0 ? "sea level" : `${-d} km`, pos: new THREE.Vector3(+(xmin - 0.7).toFixed(6), d, zmax) });
  }
  const rg = new THREE.BufferGeometry(); rg.setAttribute("position", new THREE.Float32BufferAttribute(rp, 3));
  group.add(new THREE.LineSegments(rg, new THREE.LineBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.4 })));
  return { group, ticks };
}
