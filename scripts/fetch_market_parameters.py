"""Fetch the two public market parameters used as DCF defaults, with their sources.

- Risk-free rate: US Treasury 10-year constant-maturity yield on 2025-12-31 (FRED series DGS10).
- Equity risk premium: Aswath Damodaran's implied ERP (trailing 12 months), month start 2026-01-01.

Share prices are deliberately not fetched: no public price source with a clear reuse licence was available
programmatically (Stooq blocks automated access and Yahoo's terms restrict redistribution). Prices are user inputs.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import subprocess
import warnings
from datetime import date
from pathlib import Path

import openpyxl

ROOT = Path(__file__).parents[1]
OUT = ROOT / "data" / "market-parameters.json"
RAW = ROOT / "data" / "raw"
VALUATION_DATE = "2025-12-31"


def curl(url: str, target: Path | None = None) -> bytes:
    args = ["curl", "-sS", "-m", "90", "-A", "Mozilla/5.0 (research; lindgreendavid@gmail.com)", url]
    data = subprocess.run(args, capture_output=True, check=True).stdout
    if target:
        target.write_bytes(data)
    return data


def main() -> int:
    fred_url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10&cosd=2025-12-24&coed=2026-01-05"
    rows = list(csv.DictReader(io.StringIO(curl(fred_url).decode("utf-8"))))
    risk_free = next(float(r["DGS10"]) for r in rows if r["observation_date"] == VALUATION_DATE) / 100.0
    erp_url = "https://pages.stern.nyu.edu/~adamodar/pc/implprem/ERPbymonth.xlsx"
    target = RAW / "damodaran-ERPbymonth.xlsx"
    data = curl(erp_url, target)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        sheet = openpyxl.load_workbook(target, data_only=True)["Historical ERP"]
    header = [c.value for c in sheet[1]]
    erp = None
    for row in sheet.iter_rows(values_only=True):
        if row[0] is not None and hasattr(row[0], "year") and row[0].date() == date(2026, 1, 1):
            erp = float(dict(zip(header, row, strict=False))["ERP (T12m)"])
    assert erp is not None
    OUT.write_text(
        json.dumps(
            {
                "valuation_date": VALUATION_DATE,
                "risk_free_rate": {
                    "value": risk_free,
                    "source": fred_url,
                    "description": "US Treasury 10-year constant maturity yield on 2025-12-31 (FRED DGS10)",
                },
                "equity_risk_premium": {
                    "value": erp,
                    "source": erp_url,
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "description": "Damodaran implied equity risk premium, trailing 12 month cash yield, month starting 2026-01-01",
                },
                "price_note": "No share prices are included. Enter a price to compare the DCF with the market.",
            },
            indent=1,
        )
        + "\n",
        encoding="utf-8",
    )
    print(risk_free, erp)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
