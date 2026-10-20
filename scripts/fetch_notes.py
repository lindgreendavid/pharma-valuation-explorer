"""Fetch the few note pages and cover pages that the dataset needs beyond the primary statements.

Cover pages give the shares outstanding stated on the filing (dei:EntityCommonStockSharesOutstanding).
The Novartis note pages give depreciation and amortisation, which its cash flow statement does not
present separately. Pages are parsed with the same parser as the statements.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from fetch_statements import FILINGS, RAW, fetch, page_title, parse_table

ROOT = Path(__file__).parents[1]
OUT = ROOT / "data" / "extracted" / "notes.json"

# (company, fiscal year, R page, purpose)
PAGES = [
    *[(company, year, 1, "cover page") for company, _, year, _, _ in FILINGS],
    ("Novartis", 2025, 90, "property, plant and equipment: depreciation"),
    ("Novartis", 2025, 99, "intangible assets: amortisation"),
    ("Novartis", 2025, 134, "cash flow note: non-cash items"),
]


def main() -> int:
    by_key = {(c, y): (cik, acc) for c, cik, y, acc, _ in FILINGS}
    result = []
    for company, year, number, purpose in PAGES:
        cik, accession = by_key[(company, year)]
        url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession.replace('-', '')}/R{number}.htm"
        raw = fetch(url)
        text = raw.decode("utf-8", errors="ignore")
        (RAW / f"{company.lower().replace(' ', '-')}-{year}-R{number}.htm").write_bytes(raw)
        result.append(
            {
                "company": company,
                "fiscal_year": year,
                "page": f"R{number}.htm",
                "purpose": purpose,
                "url": url,
                "title": page_title(text),
                "sha256": hashlib.sha256(raw).hexdigest(),
                **parse_table(text),
            }
        )
        print(company, year, number, page_title(text)[:60])
    OUT.write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
