import * as THREE from "three";
import { MarchingCubes } from "three/examples/jsm/objects/MarchingCubes.js";
import { blur3d, GRID, massThresholds, splat, trimAboveGround } from "./density.js";

// Density shells: nested isosurfaces of a smoothed 3D density grid enclosing 70%, 45% and 20% of the events,
// trimmed to below the ground (on the grid and again per fragment).
export const SHELLS = [
  { fraction: 0.7, color: 0x2d6fc0, opacity: 0.16 },
  { fraction: 0.45, color: 0x6fa6ec, opacity: 0.3 },
  { fraction: 0.2, color: 0xdcebff, opacity: 0.85 },
];

function groundClip(mat, ground) {
  mat.onBeforeCompile = sh => {
    Object.assign(sh.uniforms, ground.uniforms);
    sh.vertexShader = sh.vertexShader.replace("#include <common>", "#include <common>\nvarying vec3 vWorldQ;")
      .replace("#include <project_vertex>", "#include <project_vertex>\nvWorldQ = (modelMatrix * vec4(transformed, 1.0)).xyz;");
    sh.fragmentShader = sh.fragmentShader.replace("#include <common>", "#include <common>\nvarying vec3 vWorldQ;\n" + ground.glsl)
      .replace("void main() {", "void main() {\n  if (vWorldQ.y > groundKm(vWorldQ.xz) - 0.02) discard;");
  };
  return mat;
}

export function makeShells(records, ground, g = GRID) {
  const group = new THREE.Group();
  const field = blur3d(splat(records, g), g.res, [1.2, 1.6, 1.2]);
  trimAboveGround(field, g, ground.elevKm);
  const thr = massThresholds(field, SHELLS.map(s => s.fraction));
  SHELLS.forEach((s, k) => {
    if (!thr[k]) return;
    const mat = groundClip(new THREE.MeshLambertMaterial({ color: s.color, transparent: true, opacity: s.opacity, side: THREE.DoubleSide, depthWrite: k === 2 }), ground);
    const mc = new MarchingCubes(g.res, mat, false, false, 120000);
    mc.isolation = thr[k]; mc.field.set(field); mc.update();
    mc.scale.set(g.xz, (g.top - g.bottom) / 2, g.xz); mc.position.set(0, (g.bottom + g.top) / 2, 0);
    mc.renderOrder = 1 + (2 - k);
    group.add(mc);
  });
  return group;
}
