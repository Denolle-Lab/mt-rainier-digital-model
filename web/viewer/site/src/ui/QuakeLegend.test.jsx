import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import QuakeLegend from "./QuakeLegend.jsx";

describe("QuakeLegend", () => {
  it("states how many events the layers actually leave out", () => {
    render(<QuakeLegend meta={{ count: 15660, from: "1980-01-02", to: "2026-09-23", magMin: -1.6, magMax: 4.9, aboveGround: 439 }} drawn={15164} />);
    expect(screen.getByText(/496 at or above the ground surface are not drawn/)).toBeInTheDocument();
  });
});
