import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { isMoveKey } from "../scene/cameraMath.js";
import { bundleFixture } from "../test/fixtures.js";
import GoTo from "./GoTo.jsx";
import Header from "./Header.jsx";

describe("Header", () => {
  const b = bundleFixture();
  it("is a slim title bar: title, summit detail and search, with the counts moved to Help", () => {
    render(<Header bundle={b} detail="1 m" onPick={() => {}} />);
    expect(screen.getByRole("heading", { name: "Mount Rainier Seismic Atlas" })).toBeInTheDocument();
    expect(screen.getByTitle("Summit terrain detail")).toHaveTextContent("1 m");
    expect(screen.getByRole("searchbox")).toBeInTheDocument();
    expect(screen.queryByTestId("n-stations")).toBeNull();
  });
  it("arrow keys in the search box move the list, not the camera", () => {
    const onPick = vi.fn();
    render(<Header bundle={b} detail="—" onPick={onPick} />);
    const input = screen.getByRole("searchbox");
    fireEvent.change(input, { target: { value: "lo" } });
    const ev = { key: "ArrowDown", target: input };
    expect(isMoveKey(ev)).toBe(false);
    fireEvent.keyDown(input, { key: "ArrowDown" });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onPick).toHaveBeenCalledTimes(1);
    expect(screen.queryAllByRole("option")).toHaveLength(0);   // closed after picking
  });
});

describe("GoTo", () => {
  it("lists eight places and the major stations", () => {
    const b = bundleFixture(), onPlace = vi.fn(), onSite = vi.fn();
    render(<GoTo majors={b.majors} onPlace={onPlace} onSite={onSite} active={null} />);
    expect(screen.getAllByRole("button", { name: /Whole area|Summit crater|Paradise|Carbon River|White River|Nisqually|From below|Side on/ })).toHaveLength(8);
    fireEvent.click(screen.getByRole("button", { name: "RCM" }));
    expect(onSite).toHaveBeenCalledWith(b.siteById["UW.RCM"]);
    fireEvent.click(screen.getByRole("button", { name: "Paradise" }));
    expect(onPlace).toHaveBeenCalledWith("paradise");
  });
});
