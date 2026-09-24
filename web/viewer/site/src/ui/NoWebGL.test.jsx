import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { hasWebGL } from "../scene/webgl.js";
import { bundleFixture } from "../test/fixtures.js";
import NoWebGL from "./NoWebGL.jsx";

describe("without WebGL", () => {
  it("jsdom has no WebGL context", () => { expect(hasWebGL()).toBe(false); });
  it("shows a message and the stations as a table", () => {
    const b = bundleFixture();
    render(<NoWebGL bundle={b} />);
    expect(screen.getByRole("alert")).toHaveTextContent(/needs WebGL/);
    expect(screen.getAllByRole("row")).toHaveLength(1 + b.stations.sites.length);
    expect(screen.getByRole("cell", { name: "Camp Muir" })).toBeInTheDocument();
  });
});
