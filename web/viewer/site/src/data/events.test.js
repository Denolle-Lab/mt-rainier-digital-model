import { describe, expect, it } from "vitest";
import { frameTime, rainAt, timeLabels, windowAt } from "./events.js";

const doc = {
  frames: { start: "2025-12-05T01:00Z", stepHours: 1, count: 3 },
  rain: { width: 2, height: 2, scale: 0.25, nodata: 255, extent: { west: -122, east: -121, south: 46, north: 47 } },
  windows: [{ label: "AR1", start: "2025-12-05T01:30:00+00:00", end: "2025-12-05T03:00:00+00:00" }],
};

describe("events", () => {
  it("frame k ends k hours after the first frame", () => {
    expect(frameTime(doc, 2).toISOString()).toBe("2025-12-05T03:00:00.000Z");
  });
  it("finds the AR window of a time (end excluded)", () => {
    expect(windowAt(doc, frameTime(doc, 0))).toBeNull();
    expect(windowAt(doc, frameTime(doc, 1)).label).toBe("AR1");
    expect(windowAt(doc, frameTime(doc, 2))).toBeNull();
  });
  it("reads rain (mm/h) from the frame, rows north to south; no data and outside are null", () => {
    const frames = new Uint8Array([0, 0, 0, 0, 4, 8, 255, 12, 0, 0, 0, 0]);
    expect(rainAt(doc, frames, 1, -121.9, 46.9)).toBe(1);      // north-west cell: 4 x 0.25
    expect(rainAt(doc, frames, 1, -121.1, 46.1)).toBe(3);      // south-east: 12 x 0.25
    expect(rainAt(doc, frames, 1, -121.9, 46.1)).toBeNull();   // 255
    expect(rainAt(doc, frames, 1, -123, 46.5)).toBeNull();
  });
  it("labels UTC and Pacific standard time", () => {
    expect(timeLabels(new Date("2025-12-09T12:00:00Z"))).toEqual({ utc: "2025-12-09 12:00 UTC", pst: "12-09 04:00 PST" });
  });
});
