import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const base = process.env.STUDIO_URL || "http://127.0.0.1:15177";
const output = process.env.RETAIL_SHOWCASE_OUTPUT || "/tmp/retail-showcase-tests";
const playwright = process.env.PLAYWRIGHT_MODULE;
assert.ok(playwright, "Set PLAYWRIGHT_MODULE to the installed Playwright module");
const { chromium } = await import(playwright);
const scenarios = [
  { title: "Demand Forecasting with Regression", kind: "forecast", courseCase: "retail-demand-forecasting", file: "notebooks/demand-forecasting/backup/02_forecast_simulator.html" },
  { title: "Next Best Product", kind: "recommendations", courseCase: "retail-product-recommendations", file: "notebooks/product-recommendations/backup/02_recommendation_simulator.html" },
];
fs.mkdirSync(output, { recursive: true });
const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROMIUM_PATH || "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge" });
try {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, reducedMotion: "reduce" });
  const errors = [], failures = [], unexpectedApis = [];
  context.on("page", page => {
    page.on("pageerror", error => errors.push(error.message));
    page.on("console", message => { if (message.type() === "error") errors.push(message.text()); });
  });
  context.on("response", response => { if (response.status() >= 400) failures.push(`${response.status()}: ${response.url()}`); });
  context.on("request", request => { if (/\/api\/(forecast|recommend)\b/.test(request.url())) unexpectedApis.push(request.url()); });
  const page = await context.newPage();

  async function frameFor(host, scenario) {
    const locator = host.locator("iframe.retail-demo-frame");
    await locator.waitFor();
    assert.equal(await locator.getAttribute("title"), `${scenario.title} simulator`);
    const frame = await (await locator.elementHandle()).contentFrame();
    await frame.waitForFunction(() => Boolean(window.retailSimulator));
    return frame;
  }
  async function layoutCheck(host, frame, name) {
    assert.ok(await host.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), `${name}: outer overflow`);
    assert.ok(await frame.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), `${name}: simulator overflow`);
    assert.ok(await frame.evaluate(() => [...document.images].every(image => image.complete && image.naturalWidth > 0)), `${name}: image missing`);
    await frame.waitForFunction(() => [...document.querySelectorAll(".js-plotly-plot")].every(plot => Math.abs(plot._fullLayout.width - plot.clientWidth) < 2));
  }

  for (const scenario of scenarios) {
    for (const viewportWidth of [1440, 390]) {
      await page.setViewportSize({ width: viewportWidth, height: 1000 });
      await page.goto(`${base}/showcase?industry=retail`);
      const card = page.locator(".use-case-card").filter({ hasText: scenario.title });
      await card.waitFor();
      for (const name of ["Workflow", "Demo"]) assert.equal(await card.getByRole("button", { name, exact: name !== "Demo" }).count(), 1);
      assert.equal(await card.getByRole("button").count(), 2);
      assert.equal(await card.getByRole("button", { name: /Simulator/ }).count(), 0);
      await card.getByRole("button", { name: "Workflow", exact: true }).click();
      await page.waitForURL(`**/workflow?courseCase=${scenario.courseCase}`);
      await page.getByRole("heading", { name: scenario.title, exact: true }).waitFor();
      assert.equal(await page.getByRole("button", { name: "Simulator", exact: true }).count(), 0);
      const canvas = page.locator(".business-flow-canvas");
      assert.ok(await canvas.evaluate(element => element.scrollWidth > element.clientWidth), "Retail workflow should retain readable, scrollable spacing");
      await canvas.focus();
      await page.keyboard.press("ArrowRight");
      assert.ok(await canvas.evaluate(element => element.scrollLeft > 0));
      await page.getByRole("button", { name: "Open workflow full screen", exact: true }).click();
      await page.locator(".workflow-canvas-shell.is-fullscreen").waitFor();
      await page.keyboard.press("Escape");
      await page.getByRole("button", { name: /Judge AI fit/ }).click();
      await page.getByRole("button", { name: /Design what survives/ }).click();
      const design = await page.locator(".design-stack").innerText();
      assert.match(design, scenario.kind === "forecast" ? /HistGradientBoostingRegressor/ : /15 outgoing neighbors/);
      await page.screenshot({ path: path.join(output, `${scenario.kind}-workflow-${viewportWidth}.png`), fullPage: true });
      await page.getByRole("button", { name: "Open demo", exact: true }).click();
      await page.waitForURL(`**/${scenario.kind}`);
      const frame = await frameFor(page, scenario);
      assert.equal(await page.getByRole("link", { name: /Open simulator/ }).count(), 0);
      assert.equal(await page.locator('a[href$="-simulator"]').count(), 0);
      const source = await page.locator("iframe").getAttribute("src");
      if (process.env.RETAIL_VERIFY_BUILD === "1") {
        const response = await page.request.get(new URL(source, base).href);
        assert.ok((await response.body()).equals(fs.readFileSync(path.join(root, scenario.file))), "Built simulator bytes differ from tested classroom export");
      }
      if (scenario.kind === "forecast") {
        assert.equal(await frame.locator("#week-counter").innerText(), "0 of 26");
        await frame.locator("#step").click();
        assert.equal(await frame.locator("#phase-chip").innerText(), "Forecast made / week not revealed");
        assert.equal(await frame.locator("#actual-value").innerText(), "--");
        await frame.locator("#step").click();
        assert.notEqual(await frame.locator("#actual-value").innerText(), "--");
        assert.equal(await frame.locator("#scoreboard tr").count(), 1);
        await frame.locator("#whatif > summary").click();
        await frame.locator("#increase").click();
        assert.equal(await frame.locator("#week-inputs input").count(), 8);
        assert.match(await frame.locator("#additive-check").innerText(), /passed/);
        await frame.locator("#restore").click();
      } else {
        const initial = await frame.evaluate(() => { const state = retailSimulator.getState(); return { history: [...state.history], ranking: state.ranking.map(row => row.index) }; });
        await frame.locator('[data-mode="neighbor"]').click();
        assert.equal(await frame.evaluate(() => retailSimulator.getState().mode), "neighbor");
        await frame.locator('[data-mode="history"]').click();
        const product = initial.ranking[0];
        await frame.locator(`#ranking [data-add="${product}"]`).click();
        assert.deepEqual(await frame.evaluate(() => retailSimulator.getState().history), initial.history);
        await frame.locator("#workbench > summary").click();
        await frame.locator("#purchase-button").click();
        assert.equal(await frame.evaluate(() => retailSimulator.getState().history.length), initial.history.length + 1);
        assert.ok(!await frame.evaluate(index => retailSimulator.getState().ranking.some(row => row.index === index), product));
        await frame.locator("#undo").click();
        assert.deepEqual(await frame.evaluate(() => retailSimulator.getState().ranking.map(row => row.index)), initial.ranking);
      }
      await layoutCheck(page, frame, `${scenario.kind}/${viewportWidth}`);
      await frame.locator("h1").scrollIntoViewIfNeeded();
      await page.evaluate(() => window.scrollTo(0, 0));
      await page.screenshot({ path: path.join(output, `${scenario.kind}-demo-${viewportWidth}.png`), fullPage: true });
      await page.getByRole("link", { name: "Workflow", exact: true }).click();
      await page.waitForURL(`**/workflow?courseCase=${scenario.courseCase}`);
      await page.getByRole("button", { name: "Back to Industry Workflows", exact: true }).click();
      await page.waitForURL("**/showcase?industry=retail");
      await page.locator(".use-case-card").filter({ hasText: scenario.title }).getByRole("button", { name: /Demo/ }).click();
      await page.waitForURL(`**/${scenario.kind}`);
      await frameFor(page, scenario);
      await page.reload();
      await frameFor(page, scenario);
      console.log(`PASS: ${scenario.title} / ${viewportWidth}px: Workflow + Demo only, three workflow lenses, demo inference, return and deep-link reload`);
    }
  }
  assert.deepEqual(unexpectedApis, [], "Current retail demo unexpectedly depends on old API");
  assert.deepEqual(failures, []);
  assert.deepEqual(errors, []);
  console.log(`PASS: no failed requests, browser errors, or legacy API calls. Screenshots: ${output}`);
} finally { await browser.close(); }