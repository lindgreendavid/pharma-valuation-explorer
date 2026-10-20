"""Fetch the rendered primary financial statements of the selected 20-F filings from SEC EDGAR.

Each filing's XBRL "R" pages are the statements exactly as filed (company line items, company units).
Raw pages are saved under data/raw (not committed; their SHA-256 values are recorded) and parsed into
data/extracted/statements.json. Nothing is estimated or adjusted here.

SEC fair-access rules require a descriptive User-Agent and at most 10 requests per second.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import subprocess
import time
from pathlib import Path

USER_AGENT = "David Lindgreen lindgreendavid@gmail.com portfolio research"
ROOT = Path(__file__).parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "extracted" / "statements.json"

FILINGS = [
    # company, cik, fiscal year, accession, filing date
    ("Novo Nordisk", 353278, 2025, "0000353278-26-000012", "2026-02-04"),
    ("Novo Nordisk", 353278, 2024, "0001628280-25-003920", "2025-02-05"),
    ("Novartis", 1114448, 2025, "0001114448-26-000004", "2026-02-04"),
    ("Novartis", 1114448, 2024, "0001370368-25-000004", "2025-01-31"),
    ("GSK", 1131399, 2025, "0001131399-26-000004", "2026-03-06"),
    ("GSK", 1131399, 2024, "0001131399-25-000007", "2025-03-03"),
]
STATEMENT_PATTERNS = {
    "income_statement": re.compile(r"(income statement|statements? of (income|profit|operations))", re.I),
    "balance_sheet": re.compile(r"(balance sheet|statements? of financial position)", re.I),
    "cash_flow": re.compile(r"cash flow", re.I),
}
EXCLUDE = re.compile(r"(parenthetical|changes in equity|supplement|note|details|policies)", re.I)


def fetch(url: str) -> bytes:
    # curl is used because the Python TLS stack on this machine rejects some hosts.
    result = subprocess.run(
        ["curl", "-sS", "-m", "90", "-H", f"User-Agent: {USER_AGENT}", url],
        capture_output=True,
        check=True,
    )
    time.sleep(0.4)
    return result.stdout


def page_title(text: str) -> str:
    match = re.search(r'<th class="tl"[^>]*>.*?<div[^>]*>(.*?)</div>', text, re.S)
    return html.unescape(re.sub(r"<[^>]+>", "", match.group(1))).strip() if match else ""


def _text(cell: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", cell))).strip()


def parse_table(text: str) -> dict[str, object]:
    """Return column headers and statement rows (label, values) from an EDGAR R page.

    Only line-item rows are kept: a label cell (class pl) followed by value cells (nump/num/text).
    Footnote and definition cells are ignored.
    """

    headers: list[str] = []
    data: list[dict[str, object]] = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", text, re.S):
        header_cells = re.findall(r'<th class="th"[^>]*>(.*?)</th>', row, re.S)
        if header_cells and not data:
            labels = [_text(c) for c in header_cells]
            # the first header row carries the title and period length; keep the last one with dates or years
            if any(re.search(r"\d{4}", label) for label in labels):
                headers = [label for label in labels if re.search(r"\d{4}", label)] or headers
            continue
        label_match = re.search(r'<td class="pl[^"]*"[^>]*>(.*?)</td>', row, re.S)
        if not label_match:
            continue
        values = [
            _text(cell) for cls, cell in re.findall(r'<td class="(nump|num|text)[^"]*"[^>]*>(.*?)</td>', row, re.S)
        ]
        data.append({"label": _text(label_match.group(1)), "values": values})
    return {"headers": headers, "rows": data}


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    result: list[dict[str, object]] = []
    for company, cik, fiscal_year, accession, filed in FILINGS:
        folder = accession.replace("-", "")
        base = f"https://www.sec.gov/Archives/edgar/data/{cik}/{folder}"
        found: dict[str, dict[str, object]] = {}
        for number in range(2, 12):
            url = f"{base}/R{number}.htm"
            raw = fetch(url)
            text = raw.decode("utf-8", errors="ignore")
            title = page_title(text)
            for kind, pattern in STATEMENT_PATTERNS.items():
                if kind in found or not pattern.search(title) or EXCLUDE.search(title):
                    continue
                path = RAW / f"{company.lower().replace(' ', '-')}-{fiscal_year}-R{number}.htm"
                path.write_bytes(raw)
                parsed = parse_table(text)
                found[kind] = {
                    "title": title,
                    "page": f"R{number}.htm",
                    "url": url,
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    **parsed,
                }
            if len(found) == 3:
                break
        result.append(
            {
                "company": company,
                "cik": cik,
                "fiscal_year": fiscal_year,
                "accession": accession,
                "filed": filed,
                "filing_index": f"https://www.sec.gov/Archives/edgar/data/{cik}/{folder}/",
                "statements": found,
            }
        )
        print(company, fiscal_year, sorted(found))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
