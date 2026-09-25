import { expect, test } from "@playwright/test";

const ready = page => page.waitForFunction(() => window.__rainier && window.__rainier.frame.finest >= 0, null, { timeout: 60_000 });
const cam = page => page.evaluate(() => {
  const r = window.__rainier, sph = r.camera.position.clone().sub(r.controls.target);
  return { target: r.controls.target.toArray(), dist: sph.length(), az: Math.atan2(sph.x, sph.z), flight: !!r.flight };
});
const settle = page => page.waitForFunction(() => !window.__rainier.flight, null, { timeout: 10_000 });
// open a panel from the top-right dock (a no-op when it is already open)
const dock = async (page, name) => {
  const b = page.getByRole("button", { name, exact: true });
  if ((await b.getAttribute("aria-expanded")) !== "true") await b.click();
};

// mark the first-visit hint seen (test (j) checks the hint itself)
test.beforeEach(async ({ page }, info) => {
  if (!info.title.startsWith("(j)")) await page.addInitScript(() => { try { localStorage.setItem("rainier-viewer-help-seen", "1"); } catch { /* ignore */ } });
  await page.goto("./"); await ready(page);
});

test("(a) loads the map with stations and counts", async ({ page }) => {
  await dock(page, "Help");
  await expect(page.getByTestId("n-stations")).toHaveText("52");
  const visible = await page.locator(".station").evaluateAll(els => els.filter(e => +getComputedStyle(e).opacity > 0.5).length);
  expect(visible).toBeGreaterThanOrEqual(25);   // the block view sits low; ridges hide some stations
});

test("(b) Go to RCM frames Camp Muir from 9 km and opens its panel", async ({ page }) => {
  await page.getByRole("button", { name: "RCM", exact: true }).click();
  await expect(page.locator("#panel")).toContainText("Camp Muir");
  await settle(page);
  const c = await cam(page);
  expect(c.dist).toBeGreaterThan(8.5); expect(c.dist).toBeLessThan(9.5);
});

test("(c) arrow keys glide, drag moves, Ctrl-drag rotates", async ({ page }) => {
  await page.getByRole("button", { name: "Paradise", exact: true }).click(); await settle(page);
  const a = await cam(page);
  await page.locator("canvas").click({ position: { x: 700, y: 600 } });   // focus the page, not a field
  await page.keyboard.down("ArrowUp"); await page.waitForTimeout(1000); await page.keyboard.up("ArrowUp");
  const b = await cam(page);
  expect(Math.hypot(b.target[0] - a.target[0], b.target[2] - a.target[2])).toBeGreaterThan(1);
  await page.mouse.move(700, 600); await page.mouse.down(); await page.mouse.move(600, 520, { steps: 8 }); await page.mouse.up();
  await page.waitForTimeout(600);
  const c = await cam(page);
  expect(Math.hypot(c.target[0] - b.target[0], c.target[2] - b.target[2])).toBeGreaterThan(0.2);
  await page.keyboard.down("Control");
  await page.mouse.move(700, 600); await page.mouse.down(); await page.mouse.move(860, 600, { steps: 8 }); await page.mouse.up();
  await page.keyboard.up("Control"); await page.waitForTimeout(800);
  const d = await cam(page);
  expect(Math.abs(d.az - c.az)).toBeGreaterThan(0.1);
  expect(Math.hypot(d.target[0] - c.target[0], d.target[2] - c.target[2])).toBeLessThan(0.05);
});

test("(d) the summit reaches 1 m detail", async ({ page }) => {
  await page.getByRole("button", { name: "Summit crater" }).click();
  await page.waitForFunction(() => window.__rainier.frame.finest === 3, null, { timeout: 30_000 });
  await expect(page.locator(".header .detail-tag")).toContainText("1 m");
});

test("(e) 2D flattens the terrain", async ({ page }) => {
  await dock(page, "Layers");
  await page.getByRole("button", { name: "2D" }).click();
  await page.waitForFunction(() => window.__rainier.U.flat.value > 0.99, null, { timeout: 5_000 });
});

// ---- phase 2: earthquakes ----
const pixels = page => page.evaluate(() => {
  const src = window.__rainier.renderer.domElement, c = document.createElement("canvas");
  c.width = src.width; c.height = src.height;
  const g = c.getContext("2d"); g.drawImage(src, 0, 0);
  return { w: c.width, h: c.height, data: Array.from(g.getImageData(0, 0, c.width, c.height).data) };
});
const frames = (page, n = 30) => page.evaluate(n => new Promise(r => { let i = 0; const f = () => (++i >= n ? r() : requestAnimationFrame(f)); requestAnimationFrame(f); }), n);

test("(f) solid ground: from straight above, the earthquake layers change no pixel", async ({ page }) => {
  await page.evaluate(() => { const r = window.__rainier; r.flight = null; r.camera.position.set(0, 60, 0.001); r.controls.target.set(0, 0, 0); });
  await frames(page, 90);
  const set = on => page.evaluate(on => { for (const k of ["cloud", "shells", "dots"]) window.__rainier.layers.set(k, on); }, on);
  await set(true); await frames(page); const a = await pixels(page);
  await set(false); await frames(page); const b = await pixels(page);
  let diff = 0;
  for (let y = Math.floor(a.h * 0.2); y < a.h * 0.8; y++) for (let x = Math.floor(a.w * 0.2); x < a.w * 0.8; x++) {
    const i = (y * a.w + x) * 4;
    if (Math.abs(a.data[i] - b.data[i]) > 8 || Math.abs(a.data[i + 1] - b.data[i + 1]) > 8 || Math.abs(a.data[i + 2] - b.data[i + 2]) > 8) diff++;
  }
  expect(diff).toBe(0);
});

test("(g) from below, the shells are visible", async ({ page }) => {
  await page.getByRole("button", { name: "From below" }).click(); await settle(page); await frames(page);
  const p = await pixels(page);
  let blue = 0;
  // translucent shells over the dark underside shift pixels toward blue; the rock alone is neutral
  for (let i = 0; i < p.data.length; i += 4) if (p.data[i + 2] - p.data[i] > 15 && p.data[i + 2] - p.data[i + 1] > 5) blue++;
  expect(blue).toBeGreaterThan(20000);
});

test("(h) the cut hides stations on the removed side", async ({ page }) => {
  await page.locator("canvas").click({ position: { x: 700, y: 500 } });
  await page.keyboard.press("x");
  await frames(page);
  const op = id => page.locator(`.station[data-id="${id}"]`).evaluate(e => +e.style.opacity);
  expect(await op("CC.PARA")).toBe(0);   // south of the summit: cut away
  expect(await op("UW.FMW")).toBeGreaterThan(0.1);   // north: kept
});

test("(i) 2D hides the block frame, 3D brings it back", async ({ page }) => {
  await expect(page.locator(".tick").first()).toBeVisible();
  await dock(page, "Layers");
  await page.getByRole("button", { name: "2D" }).click();
  await expect(page.locator(".tick").first()).toBeHidden();
  await page.getByRole("button", { name: "3D" }).click();
  await expect(page.locator(".tick").first()).toBeVisible();
});

test("(j) a first visit gets a one-line hint, not a card over the map; ? opens Help, and the hint does not come back", async ({ page }) => {
  await expect(page.getByRole("status")).toContainText("Drag to move");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.getByRole("button", { name: "More help" }).click();
  await expect(page.getByRole("button", { name: "Help", exact: true })).toHaveAttribute("aria-expanded", "true");
  await expect(page.locator(".helppanel")).toBeVisible();
  await expect(page.getByRole("status")).toHaveCount(0);
  await page.reload(); await ready(page);
  await expect(page.getByRole("status")).toHaveCount(0);
  await page.getByRole("button", { name: "How to move" }).click();   // the nav pad's ? opens Help too
  await expect(page.locator(".helppanel")).toBeVisible();
});

test("(q) the map opens clear: every dock panel starts closed, stays open until its button is clicked again, and the dock moves aside for a station", async ({ page }) => {
  for (const cls of [".controls", ".legend", ".model-panel", ".helppanel"]) await expect(page.locator(cls)).toBeHidden();
  await expect(page.locator(".goto")).toBeVisible();
  await dock(page, "Layers"); await dock(page, "Legend");
  await expect(page.locator(".controls")).toBeVisible(); await expect(page.locator(".legend")).toBeVisible();
  await page.getByRole("button", { name: "Layers", exact: true }).click();
  await expect(page.locator(".controls")).toBeHidden(); await expect(page.locator(".legend")).toBeVisible();
  const right = () => page.locator(".hud-dock").evaluate(e => innerWidth - e.getBoundingClientRect().right);
  expect(await right()).toBeLessThan(20);
  await page.getByRole("button", { name: "RCM", exact: true }).click();
  await expect(page.locator("#panel")).toBeVisible();
  await expect.poll(right).toBeGreaterThan(440);
});

test("(k) the navigation pad rotates about the target and turns north up", async ({ page }) => {
  await settle(page);
  const a = await cam(page);
  await page.getByRole("button", { name: "Rotate right" }).click(); await settle(page);
  const b = await cam(page);
  expect(Math.abs(b.az - a.az)).toBeGreaterThan(0.3); expect(b.dist).toBeCloseTo(a.dist, 1);
  await page.getByRole("button", { name: "North up" }).click(); await settle(page);
  expect(Math.abs((await cam(page)).az)).toBeLessThan(0.01);
});

test("(l) the subsurface section follows the cut and the slice follows its slider", async ({ page }) => {
  await page.waitForFunction(() => !!window.__rainier.volume, null, { timeout: 30_000 });
  await dock(page, "Surface model"); await dock(page, "Layers");
  await page.getByLabel("Subsurface property").selectOption("vs");
  await page.getByRole("switch", { name: "Section on the cut" }).click();
  await page.waitForFunction(() => window.__rainier.volume.section.visible, null, { timeout: 20_000 });
  expect(await page.evaluate(() => window.__rainier.U.clipOn.value)).toBe(1);   // the section switched the cut on
  await expect(page.getByRole("switch", { name: "Cut away terrain" })).toHaveAttribute("aria-checked", "true");
  await page.getByRole("switch", { name: "Depth slice" }).click();
  await page.getByLabel("Slice elevation").fill("-5");
  expect(await page.evaluate(() => window.__rainier.volume.slice.position.y)).toBe(-5);
});

test("(o) strain properties draw their orientation bars on the depth slice", async ({ page }) => {
  await page.waitForFunction(() => !!window.__rainier.volume, null, { timeout: 30_000 });
  test.skip(!(await page.evaluate(() => !!window.__rainier.volume.meta.bars)), "bundle without strain (S24)");
  await page.waitForFunction(() => !!window.__rainier.volume.bars, null, { timeout: 30_000 });
  const shown = () => page.evaluate(() => Object.entries(window.__rainier.volume.bars.meshes)
    .flatMap(([k, list]) => list.filter(m => m.visible).map(() => k)));
  await dock(page, "Surface model");
  await page.getByLabel("Subsurface property").selectOption("wrsz_shear_rate");
  await page.getByRole("switch", { name: "Depth slice" }).click();
  await page.getByLabel("Slice elevation").fill("-5");
  await expect.poll(shown).toEqual(["tectonic"]);
  await page.getByLabel("Subsurface property").selectOption("load_volumetric");
  await expect.poll(shown).toEqual(["load"]);
  await page.getByLabel("Subsurface property").selectOption("vs");
  await expect.poll(shown).toEqual([]);
});

test("(m) the sensor legend filters: geophones show the 2025 nodes, Past adds earlier deployments", async ({ page }) => {
  await page.waitForFunction(() => !!window.__rainier.sensors, null, { timeout: 30_000 });
  const on = () => page.evaluate(() => Array.from(window.__rainier.sensors.onAttr.array).filter(v => v > 0).length);
  // the 2025 UW nodes that sit on the terrain box (the rest lie west of it and are not drawn)
  const nodes2025 = await page.evaluate(() => window.__rainier.sensors.sites.filter(s =>
    s.kinds.includes("geophone") && s.status === "operating" && s.source.startsWith("2025")).length);
  expect(nodes2025).toBeGreaterThan(150);
  await dock(page, "Legend");
  await page.locator(".sf-kind", { hasText: "Geophone" }).click();
  expect(await on()).toBe(nodes2025);                             // operating geophones = the 2025 nodes
  await page.getByRole("button", { name: "Past", exact: true }).click();
  expect(await on()).toBeGreaterThan(nodes2025 + 300);            // + retired nodal deployments (2N, XD, Z5, ...)
  await page.getByRole("button", { name: "Temporary", exact: true }).click();
  expect(await on()).toBe(0);                                     // all nodes are temporary
  expect(await page.evaluate(() => window.__rainier.sensors.fiber.visible)).toBe(false);
});

test("(n) mass movements: events sit on the ground, the legend filters them, Flow deposits drapes the flows", async ({ page }) => {
  await page.waitForFunction(() => !!window.__rainier.mass, null, { timeout: 30_000 });
  const on = () => page.evaluate(() => Array.from(window.__rainier.mass.onAttr.array).filter(v => v > 0).length);
  expect(await on()).toBe(0);                                     // off by default
  const { n, seismic, minOff, maxOff } = await page.evaluate(() => {
    const m = window.__rainier.mass, r = window.__rainier;
    const off = m.events.map((e, i) => m.yKm(i) - r.elevKm(e.x, e.z));
    return { n: m.events.length, seismic: m.events.filter(e => e.located === "seismic").length,
      minOff: Math.min(...off), maxOff: Math.max(...off) };
  });
  expect(n).toBeGreaterThan(400);                                 // events on the terrain box (the model box is larger)
  expect(seismic).toBeGreaterThanOrEqual(19);                     // Allstadt et al. (2017) events in the box
  expect(minOff).toBeGreaterThanOrEqual(0.015 - 1e-6);             // every point at least 15 m above the ground
  expect(maxOff).toBeLessThan(0.3);                               // and on it: the highest ground within 60 m
  await dock(page, "Legend"); await dock(page, "Surface model");
  await page.getByRole("button", { name: "Events", exact: true }).click();
  expect(await on()).toBe(n);
  await page.getByRole("button", { name: "Dated only", exact: true }).click();
  const dated = await page.evaluate(() => window.__rainier.mass.events.filter(e => e.date).length);
  expect(await on()).toBe(dated);
  await page.locator(".mfilter .sf-kind", { hasText: "Snow or ice avalanche" }).click();
  expect(await on()).toBe(2);                                     // the 2010 and 2014 seismic avalanches
  await page.getByRole("button", { name: "Flow deposits", exact: true }).click();
  await expect(page.getByLabel("Surface model layer")).toHaveValue("mass_flows");
  await expect(page.locator(".model-panel")).toContainText("Osceola Mudflow");
});

test("(p) relocated catalogue: switch catalogues, 3D keeps every event below the ground", async ({ page }) => {
  await page.waitForFunction(() => !!window.__rainier.reloc, null, { timeout: 30_000 });
  const r = () => page.evaluate(() => ({ on: window.__rainier.reloc.points.visible, shown: window.__rainier.reloc.shown,
    above: window.__rainier.reloc.above }));
  expect((await r()).on).toBe(false);                             // off by default
  await dock(page, "Surface model");
  await page.getByRole("switch", { name: "Relocated earthquakes" }).click();
  const d3 = await r();
  expect(d3.on).toBe(true);
  expect(d3.shown).toBeGreaterThan(300);                          // grade A and B events of 2023-2025
  expect(d3.above).toBe(0);                                       // the 3D locations respect the topography mask
  await page.getByRole("button", { name: /PNSN 1D/ }).click();
  expect((await r()).shown).toBe(d3.shown);                       // the same events, located in the 1D model
  await page.getByRole("switch", { name: "Shift lines" }).click();
  expect(await page.evaluate(() => window.__rainier.reloc.lines.visible)).toBe(true);
  await expect(page.getByTestId("reloc-count")).toContainText("shown");
});
