import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { isMoveKey } from "../scene/cameraMath.js";
import { bundleFixture } from "../test/fixtures.js";
import GoTo from "./GoTo.jsx";
import Header from "./Header.jsx";

describe("Header", () => {
  const b = bundleFixture();
  it("shows the bundle's counts", () => {
    render(<Header bundle={b} detail="1 m" onPick={() => {}} />);
    expect(screen.getByTestId("n-stations")).toHaveTextContent("7");
    expect(screen.getByTestId("n-sites")).toHaveTextContent("3");
    expect(screen.getByTestId("n-kinds")).toHaveTextContent("6");   // kinds present in the network
    expect(screen.getByText("1 m")).toBeInTheDocument();
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
  it("lists six places and the major stations", () => {
    const b = bundleFixture(), onPlace = vi.fn(), onSite = vi.fn();
    render(<GoTo majors={b.majors} onPlace={onPlace} onSite={onSite} active={null} />);
    expect(screen.getAllByRole("button", { name: /Whole area|Summit crater|Paradise|Carbon River|White River|Nisqually/ })).toHaveLength(6);
    fireEvent.click(screen.getByRole("button", { name: "RCM" }));
    expect(onSite).toHaveBeenCalledWith(b.siteById["UW.RCM"]);
    fireEvent.click(screen.getByRole("button", { name: "Paradise" }));
    expect(onPlace).toHaveBeenCalledWith("paradise");
  });
});
