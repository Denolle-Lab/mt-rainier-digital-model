import * as THREE from "three";
import { describe, expect, it } from "vitest";
import { cutUniform, isUnder, terrainOrder } from "./groundControls.js";
import { terrainMaterial } from "./terrainMaterial.js";

describe("ground controls", () => {
  it("draws the terrain after the underground layers above ground, before them below", () => {
    expect(terrainOrder(false)).toBe(10); expect(terrainOrder(true)).toBe(-1);
  });
  it("cut plane from direction and position", () => {
    const [nx, ny, nz, w] = cutUniform(90, 2);
    expect(nx).toBeCloseTo(0, 9); expect(ny).toBe(0); expect(nz).toBeCloseTo(1, 9); expect(w).toBe(2);
    expect(cutUniform(0, -3).map(v => +v.toFixed(9))).toEqual([1, 0, 0, -3]);
  });
  it("under ground when the camera is below the surface at its position", () => {
    expect(isUnder([0, -1, 0], () => 0.5)).toBe(true);
    expect(isUnder([0, 1, 0], () => 0.5)).toBe(false);
    expect(isUnder([99, -1, 0], () => null)).toBe(true);   // off the map: sea level counts as ground
    expect(isUnder([0, 0.3, 0], () => 0.5, 1)).toBe(false);   // 2D: the ground is flat at 0
  });
  it("summit tiles share the cut, see-through and underside uniforms with the overview", () => {
    const U = { clip: { value: new THREE.Vector4() }, clipOn: { value: 0 }, alpha: { value: 1 }, under: { value: 0 }, style: { value: 0 }, flat: { value: 0 }, hole: { value: new THREE.Vector4() }, holeOn: { value: 0 } };
    const a = terrainMaterial(U, null, { hole: true }), b = terrainMaterial(U, null);
    for (const k of ["uClip", "uClipOn", "uAlpha", "uUnder"]) expect(a.uniforms[k]).toBe(b.uniforms[k]);
    expect(b.uniforms.uHoleOn).not.toBe(U.holeOn);
  });
});
