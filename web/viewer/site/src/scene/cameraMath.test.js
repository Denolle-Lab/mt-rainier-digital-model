import { describe, expect, it } from "vitest";
import { approach, ease, isMoveKey, isTypingTarget, motionDuration, moveStep, orbitPose } from "./cameraMath.js";

describe("cameraMath", () => {
  it("arrow keys move forward along the ground at 0.3 × distance per second", () => {
    const d = moveStep(new Set(["ArrowUp"]), [0, 10, 10], [0, 0, 0], 1);
    expect(d[0]).toBeCloseTo(0);
    expect(d[1]).toBe(0);
    expect(d[2]).toBeCloseTo(-0.3 * Math.hypot(10, 10));
  });
  it("opposite keys cancel", () => {
    expect(moveStep(new Set(["ArrowLeft", "ArrowRight"]), [0, 10, 10], [0, 0, 0], 1)).toEqual([0, 0, 0]);
  });
  it("typing targets", () => {
    const input = document.createElement("input");
    const div = document.createElement("div");
    const editable = document.createElement("div");
    editable.contentEditable = "true";
    expect(isTypingTarget(input)).toBe(true);
    expect(isTypingTarget(div)).toBe(false);
    expect(isTypingTarget(editable)).toBe(true);
  });
  it("ease", () => {
    expect(ease(0)).toBe(0);
    expect(ease(1)).toBe(1);
    expect(ease(0.5)).toBeCloseTo(0.5);
  });
  it("reduced motion makes flights instant and snaps uniform easing", () => {
    expect(motionDuration(1800, false)).toBe(1800);
    expect(motionDuration(1800, true)).toBe(0);
    expect(approach(0, 1, 0.016, 5, false)).toBeCloseTo(0.08);
    expect(approach(0, 1, 0.016, 5, true)).toBe(1);
    expect(approach(0, 1, 1, 5, false)).toBe(1);
  });
  it("arrow keys move only without Cmd/Ctrl/Alt and outside form fields", () => {
    const div = document.createElement("div"), input = document.createElement("input");
    expect(isMoveKey({ key: "ArrowUp", target: div })).toBe(true);
    expect(isMoveKey({ key: "a", target: div })).toBe(false);
    expect(isMoveKey({ key: "ArrowUp", target: input })).toBe(false);
    for (const mod of ["metaKey", "ctrlKey", "altKey"]) expect(isMoveKey({ key: "ArrowLeft", target: div, [mod]: true })).toBe(false);
  });
  it("a keydown without a key (Chrome autofill) is not a move key", () => {
    expect(isMoveKey({ key: undefined, target: document.createElement("div") })).toBe(false);
    expect(isMoveKey({ target: document.createElement("div") })).toBe(false);
  });
});

describe("orbitPose", () => {
  const T = [0, 0, 0];
  it("rotates about the vertical and keeps the distance", () => {
    const p = orbitPose([0, 10, 10], T, { dAz: 90 });
    expect(p[0]).toBeCloseTo(10); expect(p[1]).toBeCloseTo(10); expect(p[2]).toBeCloseTo(0);
  });
  it("tilts toward the horizon and clamps the polar angle", () => {
    const p = orbitPose([0, 10, 0.001], T, { dPol: 45 });
    expect(p[1]).toBeCloseTo(10 * Math.cos(Math.PI / 4), 2);
    expect(orbitPose([0, 10, 0.001], T, { dPol: 500 })[1]).toBeLessThan(0);   // may go below ground, not past the pole
  });
  it("zooms and turns north up", () => {
    const p = orbitPose([10, 0, 0], T, { zoom: 0.5, northUp: true });
    expect(p[0]).toBeCloseTo(0); expect(p[2]).toBeCloseTo(5);   // camera south of the target, looking north
  });
});
