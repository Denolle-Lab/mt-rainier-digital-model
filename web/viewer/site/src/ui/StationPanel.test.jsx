import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { bundleFixture } from "../test/fixtures.js";
import StationPanel, { links } from "./StationPanel.jsx";

describe("StationPanel", () => {
  const b = bundleFixture();
  it("lists every code of a merged site and its instruments", () => {
    render(<StationPanel site={b.siteById["UW.LON"]} bundle={b} onClose={() => {}} onFly={() => {}} />);
    for (const c of ["UW.LO2", "UW.LON", "UW.LON9"]) expect(screen.getByText(c)).toBeInTheDocument();
    expect(screen.getByText("Broadband seismometer · HHE HHN HHZ · 100 Hz")).toBeInTheDocument();
    expect(screen.getByText("Tiltmeter · HAE HAN · 40 Hz")).toBeInTheDocument();
    expect(screen.getByText(/as of 2026-09-23/)).toBeInTheDocument();
  });
  it("links UW stations to PNSN and CC stations to CVO, and a borehole shows its depth", () => {
    expect(links(b.siteById["UW.RCM"].stations[0]).map(l => l.label)).toContain("PNSN station page");
    expect(links(b.siteById["CC.PALI"].stations[0]).map(l => l.label)).toContain("USGS Cascades Volcano Observatory");
    const pb = links(b.siteById["PB.B941"].stations[0]).map(l => l.label);
    expect(pb).not.toContain("PNSN station page");
    render(<StationPanel site={b.siteById["PB.B941"]} bundle={b} onClose={() => {}} onFly={() => {}} />);
    expect(screen.getByText(/153 m below the surface/)).toBeInTheDocument();
  });
  it("the dataselect link asks for the last hour of the vertical channel", () => {
    const d = links(b.siteById["UW.RCM"].stations[0]).find(l => l.label.startsWith("Last hour"));
    expect(d.url).toMatch(/dataselect\/1\/query\?net=UW&sta=RCM&loc=\*&cha=HHZ&starttime=/);
  });
  it("a site outside the map says so and offers no flight", () => {
    render(<StationPanel site={b.siteById["PB.B941"]} bundle={b} onClose={() => {}} onFly={() => {}} />);
    expect(screen.getByText(/outside the map area/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /fly to/i })).toBeNull();
  });
  it("fly and close", () => {
    const onFly = vi.fn(), onClose = vi.fn();
    render(<StationPanel site={b.siteById["UW.RCM"]} bundle={b} onClose={onClose} onFly={onFly} />);
    fireEvent.click(screen.getByRole("button", { name: /fly to/i })); fireEvent.click(screen.getByRole("button", { name: /close/i }));
    expect(onFly).toHaveBeenCalledWith(b.siteById["UW.RCM"]); expect(onClose).toHaveBeenCalled();
  });
});
