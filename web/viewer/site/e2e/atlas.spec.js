import { expect, test } from "@playwright/test";

const ready = page => page.waitForFunction(() => window.__rainier && window.__rainier.frame.finest >= 0, null, { timeout: 60_000 });
const cam = page => page.evaluate(() => {
  const r = window.__rainier, sph = r.camera.position.clone().sub(r.controls.target);
  return { target: r.controls.target.toArray(), dist: sph.length(), az: Math.atan2(sph.x, sph.z), flight: !!r.flight };
});
const settle = page => page.waitForFunction(() => !window.__rainier.flight, null, { timeout: 10_000 });

test.beforeEach(async ({ page }) => { await page.goto("./"); await ready(page); });

test("(a) loads the map with stations and counts", async ({ page }) => {
  await expect(page.getByTestId("n-stations")).toHaveText("52");
  const visible = await page.locator(".station").evaluateAll(els => els.filter(e => +getComputedStyle(e).opacity > 0.5).length);
  expect(visible).toBeGreaterThanOrEqual(30);
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
