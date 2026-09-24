import * as THREE from "three";
import { describe, expect, it } from "vitest";
import { makeGround } from "../ground.js";
import { makeFrame } from "./frame.js";
import { QuakeLayers } from "./quakeLayers.js";

function fakeScene() {
  const meta = { cols: 60, rows: 60, x0: -30, z0: -30, dx: 1, dz: 1 };
  return {
    scene: new THREE.Scene(), camera: new THREE.PerspectiveCamera(32, 1.6, 0.1, 2000),
    renderer: { getPixelRatio: () => 1, domElement: { height: 900 } },
    ground: makeGround(meta, new Int16Array(3600).fill(1000)), terrainMeta: meta,
  };
}
const quakes = { records: new Float32Array([0, -5, 0, 1.5, 1, -4, 1, 0.2, -10, -12, 4, 2.2]), meta: { count: 3 } };

describe("QuakeLayers", () => {
  it("adds the cloud, dots and shells with defaults glow + shells", () => {
    const rs = fakeScene(), q = new QuakeLayers(rs, quakes);
    expect(q.state).toEqual({ cloud: true, shells: true, dots: false });
    expect(rs.scene.children).toEqual(expect.arrayContaining([q.cloud, q.dots, q.shells, q.frame.group]));
    expect(q.cloud.visible).toBe(true); expect(q.dots.visible).toBe(false); expect(q.shells.visible).toBe(true);
    q.set("dots", true);
    expect(q.dots.visible).toBe(true); expect(q.state.dots).toBe(true);
  });
  it("every layer is clipped to below the ground", () => {
    const q = new QuakeLayers(fakeScene(), quakes);
    expect(q.cloud.material.fragmentShader).toContain("groundKm(");
    expect(q.dots.material.vertexShader).toContain("ground");
    for (const mc of q.shells.children) expect(typeof mc.material.onBeforeCompile).toBe("function");
  });
  it("hiding everything for 2D keeps the toggles", () => {
    const q = new QuakeLayers(fakeScene(), quakes);
    q.set("shells", false); q.set("dots", true);
    q.setVisibleAll(false);
    expect([q.cloud.visible, q.dots.visible, q.shells.visible, q.frame.group.visible]).toEqual([false, false, false, false]);
    q.setVisibleAll(true);
    expect(q.state).toEqual({ cloud: true, shells: false, dots: true });
    expect([q.cloud.visible, q.dots.visible, q.shells.visible, q.frame.group.visible]).toEqual([true, true, false, true]);
  });
  it("events above the ground are left out of the geometry (a zero point size still draws a pixel on some GPUs)", () => {
    const q = new QuakeLayers(fakeScene(), { records: new Float32Array([0, -5, 0, 1, 0, 2.5, 0, 1, 3, 0.965, 3, 1]), meta: { count: 3 } });
    expect(q.dots.geometry.attributes.position.count).toBe(1);   // ground is 1 km; y = 2.5 and 0.965 (35 m under, inside the 40 m margin) are out
  });
  it("an empty catalog builds without throwing", () => {
    const q = new QuakeLayers(fakeScene(), { records: new Float32Array(0), meta: { count: 0 } });
    expect(q.shells.children).toHaveLength(0);
  });
});

describe("depth ruler labels", () => {
  it("hide when terrain stands between the camera and the ruler", () => {
    const overlay = document.createElement("div");
    const q = new QuakeLayers(fakeScene(), quakes, overlay);
    const project = () => [100, 100, 0.5];
    q.update(project, [60, 1, -60], () => 1);      // the sight line runs under 1 km ground
    expect(q.tickEls.every(el => el.style.opacity === "0")).toBe(true);
    q.update(project, [-40, 30, 60], () => -30);   // nothing in the way
    expect(q.tickEls.every(el => el.style.opacity === "1")).toBe(true);
  });
});

describe("makeFrame", () => {
  it("puts the depth ruler at the south-west corner, sea level to 20 km", () => {
    const f = makeFrame({ xmin: -30, xmax: 30, zmin: -30, zmax: 30, bottom: -20 });
    expect(f.ticks.map(t => t.label)).toEqual(["sea level", "5 km", "10 km", "15 km", "20 km"]);
    expect(f.ticks[4].pos.toArray()).toEqual([-30.7, -20, 30]);
  });
});
