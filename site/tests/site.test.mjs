import assert from "node:assert/strict";
import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const site = path.join(here, "..");
const root = path.join(site, "..");
const require = createRequire(import.meta.url);
const engine = require("../engine.js");
const page = fs.readFileSync(path.join(site, "index.html"), "utf8");
const css = fs.readFileSync(path.join(site, "styles.css"), "utf8");
const readme = fs.readFileSync(path.join(root, "README.md"), "utf8");
const methodology = fs.readFileSync(path.join(root, "docs", "methodology.md"), "utf8");
const read = (name) => JSON.parse(fs.readFileSync(path.join(site, "data", name), "utf8"));

function luminance(hex) {
  const channels = hex.match(/[0-9a-f]{2}/gi).map((v) => Number.parseInt(v, 16) / 255);
  const lin = channels.map((v) => (v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
  return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2];
}
const contrast = (a, b) => {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
};

test("page has the required surfaces and makes no third-party requests", () => {
  assert.equal((page.match(/<h1/g) ?? []).length, 1);
  assert.match(page, /Limits: what this does not show/);
  assert.match(page, /Not investment advice/);
  assert.match(page, /class="skip"/);
  assert.match(css, /prefers-reduced-motion/);
  assert.doesNotMatch(page, /<script[^>]+src="https?:/);
  assert.doesNotMatch(page, /<link[^>]+href="https?:/);
  assert.doesNotMatch(css, /url\(["']?https?:/);
  assert.doesNotMatch(page, /live demo|completed|production/i);
});

test("both themes keep text above WCAG AA contrast", () => {
  const read2 = (block) => Object.fromEntries([...block.matchAll(/--([a-z0-9-]+): (#[0-9a-f]{6})/gi)].map((m) => [m[1], m[2]]));
  const darkStart = css.indexOf(':root[data-theme="dark"]');
  const light = read2(css.slice(0, darkStart));
  const dark = { ...light, ...read2(css.slice(darkStart, css.indexOf("}", darkStart))) };
  for (const colors of [light, dark]) {
    for (const [fg, bg] of [["ink", "ground"], ["ink-2", "ground"], ["ink-3", "ground"], ["ink-3", "panel"], ["accent", "panel"], ["on-ink", "ink"], ["on-ink-2", "ink"], ["s1", "panel"], ["s2", "panel"], ["s3", "panel"]]) {
      assert.ok(contrast(colors[fg], colors[bg]) >= 3, `${fg} on ${bg}`);
    }
    for (const [fg, bg] of [["ink-2", "ground"], ["ink-3", "panel"], ["on-ink-2", "ink"]]) assert.ok(contrast(colors[fg], colors[bg]) >= 4.5, `${fg} on ${bg} text`);
  }
});

test("the dataset the site loads is the committed dataset and the claims in the docs are true", () => {
  const siteData = read("dataset.json");
  const committed = JSON.parse(fs.readFileSync(path.join(root, "data", "dataset.json"), "utf8"));
  assert.deepEqual(siteData, committed);
  assert.match(readme, new RegExp(`${siteData.facts.length} facts`));
  assert.match(methodology, new RegExp(`${siteData.facts.length} facts`));
  const validation = read("validation.json");
  assert.equal(validation.reconciliation.matched, validation.reconciliation.compared);
  assert.equal(validation.identities.passed, validation.identities.total);
  assert.equal(validation.facts, siteData.facts.length);
});

test("the default DCF behaves as the page says", () => {
  const defaults = read("defaults.json");
  const result = engine.enterpriseValue(defaults);
  assert.ok(result.terminal_share_of_value > 0.75 && result.terminal_share_of_value < 0.85, "about four fifths");
  const rate = Number(defaults.wacc);
  assert.ok(rate > 0.06 && rate < 0.075);
  assert.ok(Math.abs(defaults.risk_free_rate.value - 0.0418) < 1e-9);
  assert.match(methodology, /79%/);
  assert.equal(Math.round(result.terminal_share_of_value * 100), 79);
});

test("every shown number that depends on defaults is generated, not typed", () => {
  const appSource = fs.readFileSync(path.join(site, "app.js"), "utf8");
  assert.doesNotMatch(appSource, /326,?8\d\d/);
  assert.match(appSource, /No share prices are shipped/);
});
