import assert from "node:assert/strict";
import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
const engine = require("../engine.js");
const read = (name) => JSON.parse(fs.readFileSync(path.join(here, "..", "data", name), "utf8"));
const dataset = engine.makeDataset(read("dataset.json"));
const vectors = read("vectors.json");

const close = (a, b, label, rel = 1e-9) => {
  const scale = Math.max(1, Math.abs(b));
  assert.ok(Math.abs(a - b) <= rel * scale, `${label}: ${a} vs ${b}`);
};

test("metrics match the Python model for every company and year", () => {
  for (const [key, expected] of Object.entries(vectors.metrics)) {
    const [company, year] = key.split("|");
    const actual = engine.metrics(dataset, company, Number(year));
    for (const [name, value] of Object.entries(expected)) close(actual[name], value, `${key} ${name}`);
    assert.equal("revenue_growth" in actual, "revenue_growth" in expected);
  }
});

test("currency conversion matches the Python model", () => {
  for (const [key, expected] of Object.entries(vectors.eur)) {
    const [company, year] = key.split("|");
    close(engine.toEur(dataset, company, Number(year), dataset.get(company, Number(year), "revenue"), "flow"), expected.revenue_flow, key);
    close(engine.toEur(dataset, company, Number(year), dataset.get(company, Number(year), "cash"), "balance"), expected.cash_balance, key);
  }
});

test("DCF scenarios and the bridge match the Python model", () => {
  for (const [name, scenario] of Object.entries(vectors.scenarios)) {
    const result = engine.enterpriseValue(scenario.inputs);
    for (const [field, value] of Object.entries(scenario.enterprise_value)) close(result[field], value, `${name} ${field}`);
    const bridge = engine.equityBridge(dataset, "Novartis", 2025, result.enterprise_value);
    close(bridge.equity_value, scenario.bridge.equity_value, `${name} equity`);
    assert.equal(bridge.items.length, scenario.bridge.items.length);
  }
});

test("bridge options match the Python model", () => {
  for (const [company, expected] of Object.entries(vectors.bridges)) {
    close(engine.equityBridge(dataset, company, 2025, 100000).equity_value, expected.book.equity_value, `${company} book`);
    close(engine.equityBridge(dataset, company, 2025, 100000, { nciMethod: "earnings_multiple" }).equity_value, expected.multiple.equity_value, `${company} multiple`);
  }
});

test("sensitivity grid matches the Python model and behaves sensibly", () => {
  const inputs = vectors.scenarios.base.inputs;
  const grid = engine.sensitivityGrid(inputs, vectors.grid.waccs, vectors.grid.growths);
  grid.forEach((row, i) => row.forEach((value, j) => close(value, vectors.grid.values[i][j], `grid ${i},${j}`)));
  for (const row of grid) assert.deepEqual([...row].sort((a, b) => a - b), row);
});

test("guards: WACC must exceed terminal growth, lengths must match", () => {
  const inputs = vectors.scenarios.base.inputs;
  assert.throws(() => engine.enterpriseValue({ ...inputs, wacc: 0.01, terminal_growth: 0.02 }));
  assert.throws(() => engine.project({ ...inputs, growth: [0.1] }));
});

test("a flat business is worth NOPAT over WACC", () => {
  const inputs = { base_revenue: 1000, growth: [0, 0, 0, 0, 0], operating_margin: [0.3, 0.3, 0.3, 0.3, 0.3], tax_rate: 0.2, da_pct_revenue: 0.05, capex_pct_revenue: 0.05, nwc_pct_revenue: 0, base_nwc: 0, wacc: 0.08, terminal_growth: 0 };
  close(engine.enterpriseValue(inputs).enterprise_value, (1000 * 0.3 * 0.8) / 0.08, "perpetuity", 1e-12);
});
