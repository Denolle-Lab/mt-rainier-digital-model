import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import LayerPanel from "./LayerPanel.jsx";

function setup() {
  const state = { cloud: true, shells: true, dots: false };
  const layers = { get state() { return { ...state }; }, set: vi.fn((k, v) => { state[k] = v; }) };
  const scene = { setSeeThrough: vi.fn(), setCut: vi.fn() };
  const onStations = vi.fn();
  render(<LayerPanel layers={layers} scene={scene} onStations={onStations} />);
  return { layers, scene, onStations };
}

describe("LayerPanel", () => {
  it("toggles a layer on click", () => {
    const { layers } = setup();
    fireEvent.click(screen.getByRole("switch", { name: /Dots/ }));
    expect(layers.set).toHaveBeenCalledWith("dots", true);
    expect(screen.getByRole("switch", { name: /Dots/ })).toHaveAttribute("aria-checked", "true");
  });
  it("keys toggle layers, but not while typing in a field", () => {
    const { layers } = setup();
    fireEvent.keyDown(window, { key: "g" });
    expect(layers.set).toHaveBeenCalledWith("cloud", false);
    const slider = screen.getByRole("slider", { name: /See-through/ });
    fireEvent.keyDown(slider, { key: "s" });
    expect(layers.set).not.toHaveBeenCalledWith("shells", false);
    fireEvent.keyDown(window, { key: "d", metaKey: true });
    expect(layers.set).not.toHaveBeenCalledWith("dots", true);
  });
  it("see-through and cut drive the scene", () => {
    const { scene } = setup();
    fireEvent.change(screen.getByRole("slider", { name: /See-through/ }), { target: { value: "45" } });
    expect(scene.setSeeThrough).toHaveBeenCalledWith(45);
    fireEvent.click(screen.getByRole("switch", { name: /Cut away terrain/ }));
    expect(scene.setCut).toHaveBeenLastCalledWith({ on: true, angle: 90, offset: 0 });
    fireEvent.change(screen.getByRole("slider", { name: /Direction/ }), { target: { value: "30" } });
    expect(scene.setCut).toHaveBeenLastCalledWith({ on: true, angle: 30, offset: 0 });
  });
  it("stations toggle", () => {
    const { onStations } = setup();
    fireEvent.keyDown(window, { key: "t" });
    expect(onStations).toHaveBeenCalledWith(false);
  });
});
