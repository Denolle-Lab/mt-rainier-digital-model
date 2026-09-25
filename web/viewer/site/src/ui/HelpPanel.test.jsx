import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { bundleFixture } from "../test/fixtures.js";
import HelpPanel, { HelpHint, helpSeen, markHelpSeen } from "./HelpPanel.jsx";

describe("HelpPanel", () => {
  it("explains moving the map and carries the network counts", () => {
    render(<HelpPanel bundle={bundleFixture()} />);
    expect(screen.getAllByText("Rotate and tilt", { selector: "b" }).length).toBeGreaterThan(0);
    expect(screen.getByTestId("n-stations")).toHaveTextContent("7");
    expect(screen.getByTestId("n-sites")).toHaveTextContent("3");
    expect(screen.getByTestId("n-kinds")).toHaveTextContent("6");   // kinds present in the network
  });
});

describe("HelpHint", () => {
  beforeEach(() => localStorage.clear());
  it("shows on a first visit; ? opens help and the hint does not come back", () => {
    const onHelp = vi.fn();
    const { unmount } = render(<HelpHint onHelp={onHelp} />);
    fireEvent.click(screen.getByRole("button", { name: "More help" }));
    expect(onHelp).toHaveBeenCalled();
    expect(screen.queryByRole("status")).toBeNull();
    expect(helpSeen()).toBe(true);
    unmount(); render(<HelpHint onHelp={onHelp} />);
    expect(screen.queryByRole("status")).toBeNull();
  });
  it("can be dismissed", () => {
    render(<HelpHint onHelp={() => {}} />);
    expect(screen.getByRole("status")).toHaveTextContent(/Drag to move/);
    fireEvent.click(screen.getByRole("button", { name: "Dismiss" }));
    expect(screen.queryByRole("status")).toBeNull();
    expect(helpSeen()).toBe(true);
  });
});


describe("HelpHint, more", () => {
  beforeEach(() => localStorage.clear());
  afterEach(() => vi.unstubAllGlobals());
  it("speaks touch on a touch screen", () => {
    vi.stubGlobal("matchMedia", q => ({ matches: q === "(pointer: coarse)" }));
    render(<HelpHint onHelp={() => {}} />);
    expect(screen.getByRole("status")).toHaveTextContent("Drag to move · two fingers to rotate · pinch to zoom");
  });
  it("goes away once help has been opened some other way", () => {
    const { rerender } = render(<HelpHint onHelp={() => {}} />);
    markHelpSeen();
    rerender(<HelpHint onHelp={() => {}} hidden />);
    expect(screen.queryByRole("status")).toBeNull();
    expect(helpSeen()).toBe(true);
  });
});
