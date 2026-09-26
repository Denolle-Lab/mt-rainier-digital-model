import { describe, expect, it } from "vitest";
import { shrink } from "./RainierScene.js";

const tex = () => ({ image: { width: 4080, height: 2754 }, needsUpdate: false });
const doc = ctx => ({ createElement: () => ({ getContext: () => ctx }) });

describe("shrink", () => {
  it("draws the drape at maxWidth, keeping the aspect ratio", () => {
    const t = shrink(tex(), 2048, doc({ drawImage: () => {} }));
    expect([t.image.width, t.image.height]).toEqual([2048, 1382]);
    expect(t.needsUpdate).toBe(true);
  });
  it("keeps the original image without a 2D context", () => {
    const t = tex(), im = t.image;
    expect(shrink(t, 2048, doc(null)).image).toBe(im);
  });
  it("keeps the original image when drawing throws", () => {
    const t = tex(), im = t.image;
    expect(shrink(t, 2048, doc({ drawImage: () => { throw new Error("tainted"); } })).image).toBe(im);
  });
  it("leaves a small image alone", () => {
    const t = { image: { width: 1000, height: 500 } };
    expect(shrink(t, 2048, doc({ drawImage: () => {} })).image.width).toBe(1000);
  });
});
