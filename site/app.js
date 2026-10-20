"use strict";

const E = window.PharmaEngine;
const $ = (selector, root = document) => root.querySelector(selector);
const COMPANIES = ["Novartis", "GSK", "Novo Nordisk"];
const YEARS = [2023, 2024, 2025];
const SERIES = { Novartis: "s1", GSK: "s2", "Novo Nordisk": "s3" };
const SVG = "http://www.w3.org/2000/svg";
const state = { view: "eur", prices: {}, dcf: null, bridge: { ...E.DEFAULT_BRIDGE }, price: "" };
let dataset;
let defaults;
let validation;

/* ---- small helpers ---- */
const minus = (text) => text.replace("-", "−");
const num = (value, digits = 0) => minus(value.toLocaleString("en-GB", { minimumFractionDigits: digits, maximumFractionDigits: digits }));
const pct = (value, digits = 1) => minus((value * 100).toFixed(digits)) + "%";
const times = (value) => minus(value.toFixed(2)) + "x";

function h(tag, attributes = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attributes)) {
    if (key === "class") node.className = value;
    else if (key === "html") node.innerHTML = value;
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else if (value !== false && value !== null && value !== undefined) node.setAttribute(key, value === true ? "" : value);
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child.nodeType ? child : document.createTextNode(String(child)));
  }
  return node;
}

function svgEl(name, attributes = {}, text) {
  const node = document.createElementNS(SVG, name);
  for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, value);
  if (text !== undefined) node.textContent = text;
  return node;
}

/* ---- theme toggle and entrances ---- */
const root = document.documentElement;
const toggle = $("#theme-toggle");
const syncToggle = () => toggle.setAttribute("aria-label", root.dataset.theme === "dark" ? "Switch to light theme" : "Switch to dark theme");
syncToggle();
toggle.addEventListener("click", () => {
  root.dataset.theme = root.dataset.theme === "dark" ? "light" : "dark";
  try {
    localStorage.setItem("theme", root.dataset.theme);
  } catch (error) {
    /* storage unavailable: the choice lasts for this visit only */
  }
  syncToggle();
});
const risers = document.querySelectorAll(".rise");
if ("IntersectionObserver" in window) {
  const observer = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          entry.target.classList.add("in");
          observer.unobserve(entry.target);
        }
      }
    },
    { threshold: 0.12 },
  );
  risers.forEach((node) => observer.observe(node));
} else {
  risers.forEach((node) => node.classList.add("in"));
}

/* ---- sources beside figures ---- */
function sourceList(fields, years = YEARS) {
  const items = [];
  for (const company of COMPANIES) {
    for (const field of fields) {
      for (const year of years) {
        if (!dataset.has(company, year, field)) continue;
        const f = dataset.fact(company, year, field);
        items.push(
          h("li", {}, `${company} FY${year}, ${field.replace(/_/g, " ")}: `, h("a", { href: f.source_url, rel: "noreferrer" }, `${f.accession} ${f.source_page}`), ` ("${f.line_label.slice(0, 60)}")`),
        );
      }
    }
  }
  return h("details", { class: "sources" }, h("summary", {}, "Sources for these figures"), h("ul", {}, items));
}

/* ---- charts ---- */
function chartFrame(width, height, label, caption) {
  const svg = svgEl("svg", { class: "chart", viewBox: `0 0 ${width} ${height}`, role: "img", "aria-label": label });
  svg.append(svgEl("title", {}, label));
  return svg;
}

function groupedBars(title, rows, formatValue) {
  // rows: [{ company, values: {2023, 2024, 2025} }]
  const width = 720;
  const height = 300;
  const left = 64;
  const top = 16;
  const bottom = 250;
  const svg = chartFrame(width, height, `${title}: ${rows.map((r) => `${r.company} ${YEARS.map((y) => formatValue(r.values[y])).join(", ")}`).join("; ")}`);
  const max = Math.max(...rows.flatMap((r) => YEARS.map((y) => r.values[y])), 0);
  const min = Math.min(...rows.flatMap((r) => YEARS.map((y) => r.values[y])), 0);
  const span = max - min || 1;
  const y = (v) => bottom - ((v - min) / span) * (bottom - top);
  for (let i = 0; i <= 4; i += 1) {
    const value = min + (span * i) / 4;
    svg.append(svgEl("line", { x1: left, x2: width - 8, y1: y(value), y2: y(value), class: "grid-line" }));
    svg.append(svgEl("text", { x: left - 8, y: y(value) + 5, "text-anchor": "end" }, formatValue(value)));
  }
  const groupWidth = (width - left - 16) / YEARS.length;
  const barWidth = Math.min(46, (groupWidth - 24) / rows.length);
  YEARS.forEach((year, gi) => {
    const x0 = left + gi * groupWidth + (groupWidth - barWidth * rows.length) / 2;
    rows.forEach((row, ri) => {
      const v = row.values[year];
      const top2 = Math.min(y(v), y(0));
      svg.append(svgEl("rect", { x: x0 + ri * barWidth + 2, y: top2, width: barWidth - 4, height: Math.max(1, Math.abs(y(v) - y(0))), rx: 5, class: SERIES[row.company] }));
    });
    svg.append(svgEl("text", { x: left + gi * groupWidth + groupWidth / 2, y: bottom + 26, "text-anchor": "middle" }, `FY${year}`));
  });
  svg.append(svgEl("line", { x1: left, x2: width - 8, y1: y(0), y2: y(0), class: "axis-line" }));
  return svg;
}

function lines(title, rows, formatValue) {
  const width = 720;
  const height = 300;
  const left = 64;
  const top = 16;
  const bottom = 250;
  const svg = chartFrame(width, height, `${title}: ${rows.map((r) => `${r.company} ${YEARS.map((y) => formatValue(r.values[y])).join(", ")}`).join("; ")}`);
  const all = rows.flatMap((r) => YEARS.map((y) => r.values[y]));
  const min = Math.min(...all, 0);
  const max = Math.max(...all);
  const span = max - min || 1;
  const y = (v) => bottom - ((v - min) / span) * (bottom - top);
  const x = (i) => left + 40 + (i * (width - left - 100)) / (YEARS.length - 1);
  for (let i = 0; i <= 4; i += 1) {
    const value = min + (span * i) / 4;
    svg.append(svgEl("line", { x1: left, x2: width - 8, y1: y(value), y2: y(value), class: "grid-line" }));
    svg.append(svgEl("text", { x: left - 8, y: y(value) + 5, "text-anchor": "end" }, formatValue(value)));
  }
  YEARS.forEach((year, i) => svg.append(svgEl("text", { x: x(i), y: bottom + 26, "text-anchor": "middle" }, `FY${year}`)));
  rows.forEach((row) => {
    const d = YEARS.map((year, i) => `${i === 0 ? "M" : "L"}${x(i)},${y(row.values[year])}`).join(" ");
    svg.append(svgEl("path", { d, class: `line ${SERIES[row.company]}` }));
    YEARS.forEach((year, i) => svg.append(svgEl("circle", { cx: x(i), cy: y(row.values[year]), r: 6, class: `dot ${SERIES[row.company]}` })));
    const last = row.values[YEARS[YEARS.length - 1]];
    svg.append(svgEl("text", { x: x(YEARS.length - 1) + 12, y: y(last) + 5, class: "label-strong" }, row.company.split(" ")[0]));
  });
  return svg;
}

function legend() {
  return h("div", { class: "legend" }, COMPANIES.map((c) => h("span", {}, h("i", { class: SERIES[c] }), c)));
}

function dataTable(caption, columns, rows) {
  return h(
    "details",
    { style: "margin-top: 0.75rem" },
    h("summary", {}, "Show the numbers as a table"),
    h(
      "div",
      { class: "table-wrap", style: "margin-top: 0.5rem" },
      h(
        "table",
        {},
        h("caption", {}, caption),
        h("thead", {}, h("tr", {}, columns.map((c, i) => h("th", { scope: "col", class: i ? "num" : "" }, c)))),
        h("tbody", {}, rows.map((r) => h("tr", {}, r.map((cell, i) => h(i ? "td" : "th", { scope: i ? null : "row", class: i ? "num" : "" }, cell))))),
      ),
    ),
  );
}

/* ---- comparison ---- */
function valueFor(company, year, name, kind) {
  const m = E.metrics(dataset, company, year);
  const v = m[name];
  if (v === undefined) return undefined;
  if (state.view === "eur" && kind) return E.toEur(dataset, company, year, v, kind);
  return v;
}

function renderCompare() {
  const rootNode = $("#compare-root");
  rootNode.replaceChildren();
  const unit = state.view === "eur" ? "EUR millions" : "millions of reporting currency";
  const per = (name, kind) => COMPANIES.map((company) => ({ company, values: Object.fromEntries(YEARS.map((y) => [y, valueFor(company, y, name, kind)])) }));

  // snapshot table
  const snap = [
    ["Revenue (net sales)", (c) => num(valueFor(c, 2025, "revenue", "flow")), `${unit}, FY2025`],
    ["Revenue growth", (c) => pct(E.metrics(dataset, c, 2025).revenue_growth), "FY2025 vs FY2024, reporting currency"],
    ["Operating margin", (c) => pct(E.metrics(dataset, c, 2025).operating_margin), "reported operating income / net sales"],
    ["R&D as % of revenue", (c) => pct(E.metrics(dataset, c, 2025).r_and_d_intensity), "reported R&D expense / net sales"],
    ["Free cash flow margin", (c) => pct(E.metrics(dataset, c, 2025).fcf_margin), "after tax and net interest; see notes"],
    ["Free cash flow / net income", (c) => times(E.metrics(dataset, c, 2025).fcf_to_net_income), "cash conversion"],
    ["Net debt / operating income", (c) => times(E.metrics(dataset, c, 2025).net_debt_to_operating_income), "net debt includes debt-like contingent consideration"],
  ];
  rootNode.append(
    h(
      "div",
      { class: "panel rise in" },
      h("h3", {}, "FY2025 at a glance"),
      h("p", { class: "small" }, "Each line is defined once and computed the same way for every company."),
      h(
        "div",
        { class: "table-wrap" },
        h(
          "table",
          {},
          h("caption", {}, `FY2025 comparison. Money in ${unit}.`),
          h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Measure"), COMPANIES.map((c) => h("th", { scope: "col", class: "num" }, c)), h("th", { scope: "col", class: "left" }, "Definition"))),
          h("tbody", {}, snap.map(([label, fn, def]) => h("tr", {}, h("th", { scope: "row" }, label), COMPANIES.map((c) => h("td", { class: "num" }, fn(c))), h("td", { class: "left small" }, def)))),
        ),
      ),
      sourceList(["revenue", "operating_income", "r_and_d", "cfo", "capex_ppe", "capex_intangibles"], [2025]),
    ),
  );

  const chartRows = [
    ["Revenue", `Revenue, ${unit}`, per("revenue", "flow"), groupedBars, (v) => num(v), ["revenue"]],
    ["Operating margin", "Operating margin, reported", per("operating_margin"), lines, (v) => pct(v, 0), ["revenue", "operating_income"]],
    ["Free cash flow margin", "Free cash flow as % of revenue", per("fcf_margin"), lines, (v) => pct(v, 0), ["cfo", "capex_ppe", "capex_intangibles", "interest_paid_outside_cfo", "interest_received_outside_cfo"]],
  ];
  const grid = h("div", { class: "grid-2" });
  const left = h("div", { class: "stack" });
  const right = h("div", { class: "stack" });
  chartRows.forEach(([name, title, rows, fn, fmt, fields], index) => {
    const panel = h(
      "figure",
      { class: "panel rise in" },
      h("h3", {}, name),
      h("p", { class: "small" }, title),
      fn(title, rows, fmt),
      legend(),
      dataTable(
        title,
        ["Company", ...YEARS.map((y) => `FY${y}`)],
        rows.map((r) => [r.company, ...YEARS.map((y) => (name === "Revenue" ? num(r.values[y]) : pct(r.values[y])))]),
      ),
      sourceList(fields),
    );
    (index === 1 ? right : left).append(panel);
  });
  grid.append(left, right);
  rootNode.append(grid);

  rootNode.append(renderMultiples(), renderNotes());
}

function renderMultiples() {
  const panel = h("div", { class: "panel rise in" });
  panel.append(h("h3", {}, "Valuation multiples, from your prices"), h("p", { class: "small" }, "No share prices are shipped with this tool: no public price source with a clear reuse licence was available. Enter a price per ordinary share, in the company's reporting currency, as of a date you choose. Enterprise value = market value of equity plus net debt, post-employment liabilities and non-controlling interests, less associates and financial investments (the same bridge as the DCF, run in reverse)."));
  const controls = h("div", { class: "controls", style: "margin-top: 1rem" });
  COMPANIES.forEach((company) => {
    const input = h("input", { type: "number", min: "0", step: "any", inputmode: "decimal", id: `price-${company}`, value: state.prices[company] ?? "" });
    input.addEventListener("input", () => {
      state.prices[company] = input.value;
      updateMultiples(result);
    });
    controls.append(h("label", { class: "numfield" }, h("span", {}, `${company} price (${dataset.currency(company)} per share)`), input));
  });
  const result = h("div", { style: "margin-top: 1rem" });
  panel.append(controls, result);
  updateMultiples(result);
  return panel;
}

function updateMultiples(target) {
  target.replaceChildren();
  const entered = COMPANIES.filter((c) => Number(state.prices[c]) > 0);
  if (!entered.length) {
    target.append(h("div", { class: "state" }, "Enter a price to see enterprise value, EV/revenue, EV/operating income, P/E and free cash flow yield. Until then, the filings-only measures above are the comparison."));
    return;
  }
  const rows = entered.map((company) => {
    const price = Number(state.prices[company]);
    const shares = dataset.get(company, 2025, "shares_outstanding_cover");
    const marketCap = price * shares;
    const bridge = E.equityBridge(dataset, company, 2025, 0, { nciMethod: state.bridge.nciMethod, includePension: state.bridge.includePension, includeEquityMethod: state.bridge.includeEquityMethod, includeOtherFinancial: state.bridge.includeOtherFinancial });
    const ev = marketCap - bridge.equity_value; // bridge.equity_value with EV = 0 equals minus net claims
    const m = E.metrics(dataset, company, 2025);
    return [company, num(marketCap), num(ev), times(ev / m.revenue), times(ev / m.operating_income), times(marketCap / m.net_income), pct(m.free_cash_flow / marketCap)];
  });
  target.append(
    h(
      "div",
      { class: "table-wrap" },
      h(
        "table",
        {},
        h("caption", {}, "Multiples on FY2025 reported figures, reporting currency. P/E uses net income including non-controlling interests."),
        h("thead", {}, h("tr", {}, ["Company", "Market value of equity", "Enterprise value", "EV / revenue", "EV / operating income", "P/E", "FCF yield"].map((c, i) => h("th", { scope: "col", class: i ? "num" : "" }, c)))),
        h("tbody", {}, rows.map((r) => h("tr", {}, r.map((cell, i) => h(i ? "td" : "th", { scope: i ? null : "row", class: i ? "num" : "" }, cell))))),
      ),
    ),
    h("p", { class: "small", style: "margin-top: 0.75rem" }, "Share counts are cover-page figures stated on the filing (GSK: 1 ADS = 2 ordinary shares; Novo Nordisk: classes A and B together, including treasury shares). Prices must be per ordinary share."),
  );
}

function renderNotes() {
  const items = [
    ["Fiscal years.", "All three end on 31 December, so periods align without calendarisation."],
    ["Currencies.", "Flows convert at the ECB annual-average rate and balances at the year-end rate, so EUR levels are comparable in size. Ratios do not depend on currency."],
    ["Continuing operations.", "Novartis figures exclude the 2023 Sandoz spin-off. Without that, 2023 net income would be 14,854 instead of 8,572 USD million."],
    ["Revenue.", "Net product sales. Novartis other revenues and GSK royalty income are excluded from revenue but sit inside operating income, which slightly flatters margins on net sales."],
    ["Interest in cash flow.", "Novartis and Novo Nordisk report interest inside operating cash flow; GSK reports it in investing and financing. Free cash flow here deducts net interest for all three."],
    ["Debt.", "GSK and Novo Nordisk include lease liabilities in borrowings; Novartis shows leases separately. Gross debt includes both. GSK's contingent consideration (about GBP 6.7 billion at FY2025) is treated as debt-like."],
    ["Non-controlling interests.", "GSK's book value is negative (ViiV Healthcare), so book value is not a good measure of the claim. The bridge offers an earnings-multiple alternative."],
  ];
  return h("div", { class: "panel panel-tone rise in" }, h("h3", {}, "Why raw numbers are not comparable, and how each is handled"), h("div", { class: "note-list", style: "margin-top: 1rem" }, items.map(([a, b]) => h("p", {}, h("strong", {}, a), " ", b))));
}

/* ---- DCF explorer ---- */
function dcfInputs() {
  const s = state.dcf;
  const base = defaults;
  return {
    ...base,
    growth: base.growth.map((g) => g + s.growthShift),
    operating_margin: base.operating_margin.map((m) => m + s.marginShift),
    tax_rate: s.tax,
    wacc: s.wacc,
    terminal_growth: s.terminalGrowth,
    mid_year: s.midYear,
  };
}

function colorScale(values, value) {
  const lo = Math.min(...values.flat());
  const hi = Math.max(...values.flat());
  const t = hi === lo ? 0.5 : (value - lo) / (hi - lo);
  return `color-mix(in srgb, var(--accent) ${Math.round(12 + t * 46)}%, var(--tone))`;
}

function heatmap(title, rowLabels, colLabels, values, formatCell, baseCell) {
  const table = h("table", { class: "heat" });
  table.append(h("caption", { class: "sr-only" }, title), h("thead", {}, h("tr", {}, h("th", {}), colLabels.map((c) => h("th", { scope: "col" }, c)))));
  const body = h("tbody");
  values.forEach((row, i) => {
    body.append(
      h(
        "tr",
        {},
        h("th", { scope: "row" }, rowLabels[i]),
        row.map((v, j) => h("td", { class: baseCell && baseCell[0] === i && baseCell[1] === j ? "base" : "", style: `background:${colorScale(values, v)}` }, formatCell(v))),
      ),
    );
  });
  table.append(body);
  return h("div", { class: "table-wrap", style: "margin-top: 0.5rem" }, table);
}

function renderValue() {
  const rootNode = $("#value-root");
  rootNode.replaceChildren();
  state.dcf = state.dcf || { growthShift: 0, marginShift: 0, tax: defaults.tax_rate, wacc: defaults.wacc, terminalGrowth: defaults.terminal_growth, midYear: false };
  const s = state.dcf;
  const out = h("div", { class: "stack" });

  const slider = (id, label, min, max, step, key, fmt) => {
    const output = h("output", { for: id }, fmt(s[key]));
    const input = h("input", { type: "range", id, min, max, step, value: s[key] });
    input.addEventListener("input", () => {
      s[key] = Number(input.value);
      output.textContent = fmt(s[key]);
      update();
    });
    return h("div", { class: "slider" }, h("label", { for: id }, h("span", {}, label), output), input);
  };
  const pctSigned = (v) => (v >= 0 ? "+" : "") + minus((v * 100).toFixed(1)) + " pp";
  const controls = h(
    "div",
    { class: "panel rise in" },
    h("h3", {}, "Assumptions"),
    h("p", { class: "small" }, "Drag to change an assumption; everything below recalculates. Shifts apply to every forecast year."),
    h(
      "div",
      { class: "controls", style: "margin-top: 1rem" },
      slider("wacc", "WACC", 0.04, 0.11, 0.0005, "wacc", (v) => pct(v, 2)),
      slider("tg", "Terminal growth", 0, 0.035, 0.0025, "terminalGrowth", (v) => pct(v, 2)),
      slider("gs", "Revenue growth shift", -0.03, 0.03, 0.0025, "growthShift", pctSigned),
      slider("ms", "Operating margin shift", -0.06, 0.06, 0.005, "marginShift", pctSigned),
      slider("tx", "Tax rate", 0.08, 0.26, 0.005, "tax", (v) => pct(v, 1)),
    ),
    h(
      "div",
      { style: "display:flex;flex-wrap:wrap;gap:0.75rem;margin-top:1.25rem" },
      h("button", { type: "button", class: "btn btn-quiet", onclick: () => { state.dcf = null; renderValue(); } }, "Reset to defaults"),
      h("label", { class: "choice", style: "display:inline-block" }, (() => { const c = h("input", { type: "checkbox", id: "mid" }); c.checked = s.midYear; c.addEventListener("change", () => { s.midYear = c.checked; update(); }); return [c, h("span", {}, "Mid-year discounting")]; })()),
    ),
  );
  const results = h("div", { class: "stack" });
  out.append(controls, results);
  rootNode.append(out);

  function update() {
    results.replaceChildren();
    const inputs = dcfInputs();
    let ev;
    let rows;
    try {
      rows = E.project(inputs);
      ev = E.enterpriseValue(inputs, rows);
    } catch (error) {
      results.append(h("div", { class: "state", role: "alert" }, `This combination is not valid: ${error.message}. Lower the terminal growth or raise the WACC.`));
      return;
    }
    const bridge = E.equityBridge(dataset, "Novartis", 2025, ev.enterprise_value, { nciMethod: state.bridge.nciMethod, includePension: state.bridge.includePension, includeEquityMethod: state.bridge.includeEquityMethod, includeOtherFinancial: state.bridge.includeOtherFinancial });
    const perShare = bridge.equity_value / inputs.shares_outstanding;
    const price = Number(state.price);
    const kpis = h(
      "div",
      { class: "panel panel-ink rise in" },
      h("h3", {}, "Result"),
      h(
        "dl",
        { class: "kpis", style: "margin-top: 1rem" },
        h("div", {}, h("dt", {}, "Enterprise value (USD m)"), h("dd", {}, num(ev.enterprise_value))),
        h("div", {}, h("dt", {}, "Equity value (USD m)"), h("dd", {}, num(bridge.equity_value))),
        h("div", {}, h("dt", {}, "Per share (USD)"), h("dd", {}, num(perShare, 2))),
        h("div", {}, h("dt", {}, "Terminal value share of EV"), h("dd", {}, pct(ev.terminal_share_of_value, 0))),
      ),
      h("p", { class: "small", style: "margin-top: 1rem" }, `Assumption-driven range, not a forecast. WACC ${pct(inputs.wacc, 2)}, terminal growth ${pct(inputs.terminal_growth, 2)}. Enter a price to compare; none is shipped.`),
    );
    const priceInput = h("input", { type: "number", min: "0", step: "any", inputmode: "decimal", id: "price", value: state.price });
    const compare = h("div", { class: "kpis", style: "margin-top: 1rem" });
    const renderCompareLine = () => {
      compare.replaceChildren();
      const p = Number(state.price);
      compare.append(h("div", {}, h("dt", {}, "DCF value vs your price"), h("dd", {}, p > 0 ? pct(perShare / p - 1) : "enter a price")));
    };
    priceInput.addEventListener("input", () => { state.price = priceInput.value; renderCompareLine(); });
    renderCompareLine();
    kpis.append(h("label", { class: "numfield", style: "margin-top: 1rem; max-width: 280px" }, h("span", { style: "color: var(--on-ink-2)" }, "Market price per share, USD (optional)"), priceInput), compare);
    results.append(kpis);

    // bridge
    const bridgeBox = h(
      "div",
      { class: "panel rise in" },
      h("h3", {}, "Enterprise value to equity value"),
      h("p", { class: "small" }, "Every line is a balance-sheet item from the FY2025 20-F. Toggle items to see their effect. The bridge is not complete: litigation and tax provisions, off-balance-sheet commitments and pension surpluses are not included."),
      h(
        "div",
        { class: "segment", style: "margin-top: 1rem", role: "group", "aria-label": "Bridge options" },
        ...[["includePension", "Pensions"], ["includeEquityMethod", "Associates"], ["includeOtherFinancial", "Other financial assets"]].map(([key, label]) =>
          h("button", { type: "button", "aria-pressed": String(state.bridge[key]), onclick: () => { state.bridge[key] = !state.bridge[key]; update(); } }, label),
        ),
      ),
      h(
        "div",
        { class: "table-wrap" },
        h(
          "table",
          {},
          h("caption", {}, "Bridge, USD millions"),
          h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Item"), h("th", { scope: "col", class: "num" }, "USD m"), h("th", { scope: "col", class: "left" }, "Source"))),
          h("tbody", {}, [...bridge.items.map((i) => h("tr", {}, h("th", { scope: "row" }, i.label), h("td", { class: "num" }, num(i.amount)), h("td", { class: "left small" }, i.source))), h("tr", {}, h("th", { scope: "row" }, "Equity value"), h("td", { class: "num" }, h("strong", {}, num(bridge.equity_value))), h("td", { class: "num small" }, ""))]),
        ),
      ),
      sourceList(["debt_current", "debt_noncurrent", "lease_current", "lease_noncurrent", "cash", "short_term_investments", "equity_method_investments", "other_financial_assets", "pension_liability", "nci_book", "shares_outstanding_cover"], [2025]).cloneNode(true),
    );
    results.append(bridgeBox);

    // projection
    const proj = h(
      "figure",
      { class: "panel rise in" },
      h("h3", {}, "Free cash flow to the firm"),
      h("p", { class: "small" }, "Explicit forecast years, USD millions"),
      (() => {
        const rowsChart = [{ company: "Novartis", values: Object.fromEntries(rows.map((r) => [r.year, r.fcff])) }];
        const width = 720;
        const height = 260;
        const left = 64;
        const bottom = 210;
        const max = Math.max(...rows.map((r) => r.fcff));
        const svg = chartFrame(width, height, `Free cash flow to the firm by forecast year: ${rows.map((r) => `year ${r.year} ${num(r.fcff)}`).join(", ")}`);
        const y = (v) => bottom - (v / max) * (bottom - 16);
        for (let i = 0; i <= 3; i += 1) {
          svg.append(svgEl("line", { x1: left, x2: width - 8, y1: y((max * i) / 3), y2: y((max * i) / 3), class: "grid-line" }));
          svg.append(svgEl("text", { x: left - 8, y: y((max * i) / 3) + 5, "text-anchor": "end" }, num((max * i) / 3)));
        }
        const bw = (width - left - 24) / rows.length;
        rows.forEach((r, i) => {
          svg.append(svgEl("rect", { x: left + i * bw + 14, y: y(r.fcff), width: bw - 28, height: bottom - y(r.fcff), rx: 6, class: "s1" }));
          svg.append(svgEl("text", { x: left + i * bw + bw / 2, y: bottom + 24, "text-anchor": "middle" }, `FY${2025 + r.year}`));
        });
        void rowsChart;
        return svg;
      })(),
      dataTable("Projection, USD millions", ["Line", ...rows.map((r) => `FY${2025 + r.year}`)], [
        ["Revenue", ...rows.map((r) => num(r.revenue))],
        ["Operating income", ...rows.map((r) => num(r.ebit))],
        ["NOPAT", ...rows.map((r) => num(r.nopat))],
        ["D&A", ...rows.map((r) => num(r.da))],
        ["Capex", ...rows.map((r) => num(r.capex))],
        ["Increase in working capital", ...rows.map((r) => num(r.delta_nwc))],
        ["Free cash flow to the firm", ...rows.map((r) => num(r.fcff))],
      ]),
    );
    results.append(proj);

    // sensitivity
    const waccs = [-0.01, -0.005, 0, 0.005, 0.01].map((d) => inputs.wacc + d);
    const growths = [0.01, 0.015, 0.02, 0.025, 0.03];
    const gridEv = E.sensitivityGrid(inputs, waccs, growths);
    const adjustment = bridge.equity_value - ev.enterprise_value;
    const perShareGrid = gridEv.map((row) => row.map((v) => (v + adjustment) / inputs.shares_outstanding));
    const baseG = growths.findIndex((g) => Math.abs(g - inputs.terminal_growth) < 1e-9);
    const sens1 = heatmap("Value per share by WACC and terminal growth", waccs.map((w) => pct(w, 2)), growths.map((g) => pct(g, 1)), perShareGrid, (v) => num(v, 0), [2, baseG >= 0 ? baseG : -1]);
    const marginShifts = [-0.04, -0.02, 0, 0.02, 0.04];
    const growthShifts = [-0.02, -0.01, 0, 0.01, 0.02];
    const grid2 = marginShifts.map((ms) =>
      growthShifts.map((gs) => {
        const variant = { ...inputs, operating_margin: defaults.operating_margin.map((m) => m + s.marginShift + ms), growth: defaults.growth.map((g) => g + s.growthShift + gs) };
        return (E.enterpriseValue(variant).enterprise_value + adjustment) / inputs.shares_outstanding;
      }),
    );
    const sens2 = heatmap("Value per share by operating margin and revenue growth", marginShifts.map((m) => (m >= 0 ? "+" : "") + minus((m * 100).toFixed(0)) + " pp"), growthShifts.map((g) => (g >= 0 ? "+" : "") + minus((g * 100).toFixed(0)) + " pp"), grid2, (v) => num(v, 0), [2, 2]);
    results.append(
      h(
        "div",
        { class: "grid-2" },
        h("div", { class: "panel rise in" }, h("h3", {}, "WACC by terminal growth"), h("p", { class: "small" }, "Value per share, USD. Rows: WACC around your setting. Columns: terminal growth."), sens1),
        h("div", { class: "panel rise in" }, h("h3", {}, "Margin by growth"), h("p", { class: "small" }, "Value per share, USD. Rows: operating margin shift. Columns: revenue growth shift. Shading shows relative size only."), sens2),
      ),
    );

    // assumptions with provenance
    const tag = (kind) => h("span", { class: "tag" }, kind);
    const provenance = [
      ["Base revenue", num(defaults.base_revenue), "FY2025 net sales", tag("observed")],
      ["Working capital / revenue", pct(defaults.nwc_pct_revenue, 1), "FY2025 inventories + trade receivables - trade payables", tag("observed")],
      ["D&A / revenue", pct(defaults.da_pct_revenue, 2), "FY2025 depreciation and amortisation from the notes; impairments excluded", tag("observed")],
      ["Capex / revenue", pct(defaults.capex_pct_revenue, 2), "FY2025 purchases of PP&E and intangible assets", tag("observed")],
      ["Pre-tax cost of debt", pct(defaults.extra.pre_tax_cost_of_debt, 2), "FY2025 interest expense / average gross debt", tag("observed")],
      ["Risk-free rate", pct(defaults.risk_free_rate.value, 2), defaults.risk_free_rate.description, tag("market")],
      ["Equity risk premium", pct(defaults.equity_risk_premium.value, 2), defaults.equity_risk_premium.description, tag("market")],
      ["Beta", defaults.beta.toFixed(2), "Author's assumption for a large pharmaceutical company; range 0.5 to 1.0 is plausible", tag("assumption")],
      ["Debt weight", pct(defaults.debt_weight, 0), "Author's assumption (no market price to derive it)", tag("assumption")],
      ["Growth path", defaults.growth.map((g) => pct(g, 1)).join(", "), "Author's assumption, fading toward the terminal rate", tag("assumption")],
      ["Operating margin path", defaults.operating_margin.map((m) => pct(m, 1)).join(", "), "Author's assumption: gentle fade from the FY2025 reported margin of " + pct(E.metrics(dataset, "Novartis", 2025).operating_margin, 1), tag("assumption")],
      ["Tax rate", pct(defaults.tax_rate, 0), "Author's assumption; FY2025 effective rate was " + pct(E.metrics(dataset, "Novartis", 2025).effective_tax_rate, 1), tag("assumption")],
      ["Terminal growth", pct(defaults.terminal_growth, 1), "Author's assumption, below the risk-free rate", tag("assumption")],
    ];
    results.append(
      h(
        "div",
        { class: "panel rise in" },
        h("h3", {}, "Where each input comes from"),
        h(
          "div",
          { class: "table-wrap" },
          h(
            "table",
            {},
            h("caption", {}, "Default inputs and their provenance"),
            h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Input"), h("th", { scope: "col", class: "num" }, "Default"), h("th", { scope: "col", class: "left" }, "Basis"), h("th", { scope: "col", class: "left" }, "Kind"))),
            h("tbody", {}, provenance.map(([a, b, c, d]) => h("tr", {}, h("th", { scope: "row" }, a), h("td", { class: "num" }, b), h("td", { class: "left", style: "white-space: normal; min-width: 260px" }, c), h("td", { class: "left" }, d)))),
          ),
        ),
      ),
    );
    void price;
  }
  update();
}

/* ---- sources and validation ---- */
function renderSources() {
  const rootNode = $("#sources-root");
  rootNode.replaceChildren();
  const filings = dataset.payload.filings.slice().sort((a, b) => a.company.localeCompare(b.company) || b.fiscal_year - a.fiscal_year);
  rootNode.append(
    h(
      "div",
      { class: "panel rise in" },
      h("h3", {}, "Filings used"),
      h(
        "div",
        { class: "table-wrap" },
        h(
          "table",
          {},
          h("caption", {}, "Form 20-F filings on SEC EDGAR"),
          h("thead", {}, h("tr", {}, ["Company", "Fiscal year", "Filed", "Accession"].map((c) => h("th", { scope: "col" }, c)))),
          h("tbody", {}, filings.map((f) => h("tr", {}, h("th", { scope: "row" }, f.company), h("td", {}, `FY${f.fiscal_year}`), h("td", {}, f.filed), h("td", {}, h("a", { href: f.filing_index, rel: "noreferrer", style: "color: var(--accent)" }, f.accession))))),
        ),
      ),
      h("p", { class: "small", style: "margin-top: 1rem" }, "The FY2025 filings supply fiscal years 2023 to 2025 for income and cash flow statements. Balance sheets for 2023 come from the FY2024 filings where the FY2025 filing shows only two years."),
    ),
  );
  const search = h("input", { type: "search", class: "search", placeholder: "Filter: company, field, label", "aria-label": "Filter the dataset" });
  const body = h("tbody");
  const facts = dataset.payload.facts.slice();
  const draw = () => {
    const q = search.value.trim().toLowerCase();
    body.replaceChildren();
    facts
      .filter((f) => !q || `${f.company} ${f.field} ${f.line_label} ${f.note}`.toLowerCase().includes(q))
      .slice(0, 400)
      .forEach((f) =>
        body.append(h("tr", {}, h("th", { scope: "row" }, f.company), h("td", {}, f.fiscal_year), h("td", {}, f.field.replace(/_/g, " ")), h("td", { class: "num" }, num(f.value, f.field.includes("shares") ? 1 : 0)), h("td", {}, f.currency), h("td", { class: "left", style: "white-space: normal; min-width: 220px" }, f.line_label), h("td", {}, h("a", { href: f.source_url, rel: "noreferrer", style: "color: var(--accent)" }, f.source_page)))),
      );
  };
  search.addEventListener("input", draw);
  draw();
  rootNode.append(
    h(
      "div",
      { class: "panel rise in" },
      h("h3", {}, `The dataset (${facts.length} facts)`),
      h("p", { class: "small" }, "Millions of the reporting currency, as filed. Shares in millions. The first 400 matches are shown."),
      search,
      h("div", { class: "scroll table-wrap" }, h("table", {}, h("caption", { class: "sr-only" }, "All facts"), h("thead", {}, h("tr", {}, ["Company", "FY", "Field", "Value", "Cur.", "Line label", "Source"].map((c) => h("th", { scope: "col" }, c)))), body)),
    ),
  );
}

function renderValidation() {
  const rootNode = $("#validation-root");
  rootNode.replaceChildren();
  const v = validation;
  const stat = (value, label) => h("div", {}, h("dt", {}, label), h("dd", {}, value));
  rootNode.append(
    h(
      "div",
      { class: "panel panel-ink rise in" },
      h("h3", {}, "Results of the checks"),
      h(
        "dl",
        { class: "kpis", style: "margin-top: 1rem" },
        stat(`${v.reconciliation.matched} of ${v.reconciliation.compared}`, "figures equal a second extraction path"),
        stat(`${v.identities.passed} of ${v.identities.total}`, "balance sheet identities hold"),
        stat(String(v.facts), "facts traced to a filing page"),
        stat(`${v.parity.vectors}`, "JavaScript engine vectors equal Python"),
        stat(`${v.workbook.cells_compared}`, "workbook cells recalculated and compared"),
      ),
    ),
    h(
      "div",
      { class: "grid-2" },
      h("div", { class: "panel rise in" }, h("h3", {}, "Checked"), h("div", { class: "note-list", style: "margin-top: 0.75rem" }, v.checked.map((t) => h("p", {}, t)))),
      h("div", { class: "panel panel-tone rise in" }, h("h3", {}, "Not checked"), h("div", { class: "note-list", style: "margin-top: 0.75rem" }, v.not_checked.map((t) => h("p", {}, t)))),
    ),
  );
}

/* ---- boot ---- */
$("#cur-eur").addEventListener("click", () => setView("eur"));
$("#cur-native").addEventListener("click", () => setView("native"));
function setView(view) {
  state.view = view;
  $("#cur-eur").setAttribute("aria-pressed", String(view === "eur"));
  $("#cur-native").setAttribute("aria-pressed", String(view === "native"));
  renderCompare();
}

async function load(name) {
  const response = await fetch(`data/${name}`);
  if (!response.ok) throw new Error(`${name}: ${response.status}`);
  return response.json();
}

Promise.all([load("dataset.json"), load("defaults.json"), load("validation.json")])
  .then(([payload, def, val]) => {
    dataset = E.makeDataset(payload);
    defaults = def;
    validation = val;
    renderCompare();
    renderValue();
    renderSources();
    renderValidation();
  })
  .catch((error) => {
    for (const id of ["#compare-root", "#value-root", "#sources-root", "#validation-root"]) {
      $(id).replaceChildren(h("div", { class: "state", role: "alert" }, `The data could not be loaded (${error.message}). Reload the page, or download the Excel model, which contains the same data.`));
    }
  });
