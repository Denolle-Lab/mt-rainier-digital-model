import { expect, test } from "@playwright/test";

const ready = page => page.waitForFunction(() => window.__rainier && window.__rainier.frame.finest >= 0, null, { timeout: 60_000 });
const cam = page => page.evaluate(() => {
  const r = window.__rainier, sph = r.camera.position.clone().sub(r.controls.target);
  return { target: r.controls.target.toArray(), dist: sph.length(), az: Math.atan2(sph.x, sph.z), flight: !!r.flight };
});
const settle = page => page.waitForFunction(() => !window.__rainier.flight, null, { timeout: 10_000 });

// the first-visit help card would cover the scene; mark it seen (test (j) checks the card itself)
test.beforeEach(async ({ page }, info) => {
  if (!info.title.startsWith("(j)")) await page.addInitScript(() => { try { localStorage.setItem("rainier-viewer-help-seen", "1"); } catch { /* ignore */ } });
  await page.goto("./"); await ready(page);
});

test("(a) loads the map with stations and counts", async ({ page }) => {
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
  await expect(page.locator(".header .detail")).toContainText("1 m");
});

test("(e) 2D flattens the terrain", async ({ page }) => {
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
  await page.getByRole("button", { name: "2D" }).click();
  await expect(page.locator(".tick").first()).toBeHidden();
  await page.getByRole("button", { name: "3D" }).click();
  await expect(page.locator(".tick").first()).toBeVisible();
});

test("(j) the help card shows on a first visit and does not come back", async ({ page }) => {
  await expect(page.getByRole("dialog", { name: "How to move" })).toBeVisible();
  await page.getByRole("button", { name: "Got it" }).click();
  await expect(page.getByRole("dialog", { name: "How to move" })).toHaveCount(0);
  await page.reload(); await ready(page);
  await expect(page.getByRole("dialog", { name: "How to move" })).toHaveCount(0);
  await page.getByRole("button", { name: "How to move" }).click();   // the ? button reopens it
  await expect(page.getByRole("dialog", { name: "How to move" })).toBeVisible();
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
  await page.getByLabel("Subsurface property").selectOption("vs");
  await page.getByRole("switch", { name: "Section on the cut" }).click();
  await page.waitForFunction(() => window.__rainier.volume.section.visible, null, { timeout: 20_000 });
  expect(await page.evaluate(() => window.__rainier.U.clipOn.value)).toBe(1);   // the section switched the cut on
  await expect(page.getByRole("switch", { name: "Cut away terrain" })).toHaveAttribute("aria-checked", "true");
  await page.getByRole("switch", { name: "Depth slice" }).click();
  await page.getByLabel("Slice elevation").fill("-5");
  expect(await page.evaluate(() => window.__rainier.volume.slice.position.y)).toBe(-5);
});

test("(n) strain properties draw their orientation bars on the depth slice", async ({ page }) => {
  await page.waitForFunction(() => !!window.__rainier.volume, null, { timeout: 30_000 });
  test.skip(!(await page.evaluate(() => !!window.__rainier.volume.meta.bars)), "bundle without strain (S24)");
  await page.waitForFunction(() => !!window.__rainier.volume.bars, null, { timeout: 30_000 });
  const shown = () => page.evaluate(() => Object.entries(window.__rainier.volume.bars.meshes)
    .flatMap(([k, list]) => list.filter(m => m.visible).map(() => k)));
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
  await page.locator(".sf-kind", { hasText: "Geophone" }).click();
  expect(await on()).toBe(nodes2025);                             // operating geophones = the 2025 nodes
  await page.getByRole("button", { name: "Past", exact: true }).click();
  expect(await on()).toBeGreaterThan(nodes2025 + 300);            // + retired nodal deployments (2N, XD, Z5, ...)
  await page.getByRole("button", { name: "Temporary", exact: true }).click();
  expect(await on()).toBe(0);                                     // all nodes are temporary
  expect(await page.evaluate(() => window.__rainier.sensors.fiber.visible)).toBe(false);
});
