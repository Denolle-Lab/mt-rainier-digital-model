import { describe, expect, it } from "vitest";
import { fmtElev, fmtRate, fmtSince } from "./format.js";

describe("format", () => {
  it("elevation in whole meters with separators", () => { expect(fmtElev(3076.4)).toBe("3,076 m"); expect(fmtElev(151)).toBe("151 m"); });
  it("since year", () => { expect(fmtSince("2019-06-19")).toBe("since 2019"); });
  it("sample rate", () => { expect(fmtRate(100)).toBe("100 Hz"); expect(fmtRate(0.1)).toBe("0.1 Hz"); });
});
