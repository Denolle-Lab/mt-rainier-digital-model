import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it } from "vitest";
import HudDock from "./HudDock.jsx";

function Counter() {
  const [n, setN] = useState(0);
  return <button onClick={() => setN(n + 1)}>count {n}</button>;
}
const items = [
  { key: "layers", label: "Layers", icon: "layers", node: <Counter /> },
  { key: "model", label: "Surface model", icon: "model", node: <p>model body</p> },
  { key: "help", label: "Help", icon: "help", node: <p>help body</p> },
];
function Harness() {
  const [open, setOpen] = useState(new Set());
  const toggle = k => setOpen(o => { const n = new Set(o); if (!n.delete(k)) n.add(k); return n; });
  return <HudDock items={items} open={open} onToggle={toggle} />;
}
const btn = name => screen.getByRole("button", { name });
const pop = key => document.getElementById(`hud-pop-${key}`);

describe("HudDock", () => {
  it("starts with every panel closed", () => {
    render(<Harness />);
    for (const name of ["Layers", "Surface model", "Help"]) expect(btn(name)).toHaveAttribute("aria-expanded", "false");
    for (const k of ["layers", "model", "help"]) expect(pop(k)).not.toHaveClass("open");
  });
  it("a button opens its panel, which stays open until the same button is clicked again", () => {
    render(<Harness />);
    fireEvent.click(btn("Layers"));
    expect(btn("Layers")).toHaveAttribute("aria-expanded", "true");
    expect(pop("layers")).toHaveClass("open");
    fireEvent.click(btn("Layers"));
    expect(pop("layers")).not.toHaveClass("open");
  });
  it("several open panels stack in the buttons' order", () => {
    render(<Harness />);
    fireEvent.click(btn("Help")); fireEvent.click(btn("Layers"));
    const open = [...document.querySelectorAll(".dock-pop.open")].map(e => e.id);
    expect(open).toEqual(["hud-pop-layers", "hud-pop-help"]);
  });
  it("a closed panel keeps its state", () => {
    render(<Harness />);
    fireEvent.click(btn("Layers"));
    fireEvent.click(screen.getByText("count 0"));
    fireEvent.click(btn("Layers")); fireEvent.click(btn("Layers"));
    expect(screen.getByText("count 1")).toBeInTheDocument();
  });
});
