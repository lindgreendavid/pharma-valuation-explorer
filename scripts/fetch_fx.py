"""Fetch ECB euro reference rates (units of foreign currency per 1 EUR) for USD, GBP and DKK.

Annual averages (series EXR.A) convert flows such as revenue; year-end rates (the last daily
observation of each December, series EXR.D) convert balances such as debt. Source: European Central Bank.
"""

from __future__ import annotations

import csv
import hashlib
import io
import subprocess
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parents[1]
OUT = ROOT / "data" / "ecb-fx-rates.csv"
CURRENCIES = ("USD", "GBP", "DKK")
API = "https://data-api.ecb.europa.eu/service/data/EXR"


def get(url: str) -> str:
    result = subprocess.run(["curl", "-sS", "-m", "90", "-H", "Accept: text/csv", url], capture_output=True, check=True)
    return result.stdout.decode("utf-8-sig")


def main() -> int:
    rows: list[dict[str, str]] = []
    for currency in CURRENCIES:
        annual = get(f"{API}/A.{currency}.EUR.SP00.A?startPeriod=2022&endPeriod=2025&format=csvdata")
        for record in csv.DictReader(io.StringIO(annual)):
            rows.append(
                {
                    "currency": currency,
                    "kind": "annual_average",
                    "period": record["TIME_PERIOD"],
                    "rate": record["OBS_VALUE"],
                    "series_key": record["KEY"],
                }
            )
        daily = get(f"{API}/D.{currency}.EUR.SP00.A?startPeriod=2022-12-15&endPeriod=2025-12-31&format=csvdata")
        last_by_year: dict[int, dict[str, str]] = {}
        for record in csv.DictReader(io.StringIO(daily)):
            year = date.fromisoformat(record["TIME_PERIOD"]).year
            if year not in last_by_year or record["TIME_PERIOD"] > last_by_year[year]["TIME_PERIOD"]:
                last_by_year[year] = record
        for _year, record in sorted(last_by_year.items()):
            rows.append(
                {
                    "currency": currency,
                    "kind": "year_end",
                    "period": record["TIME_PERIOD"],
                    "rate": record["OBS_VALUE"],
                    "series_key": record["KEY"],
                }
            )
    with OUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["currency", "kind", "period", "rate", "series_key"])
        writer.writeheader()
        writer.writerows(rows)
    print(hashlib.sha256(OUT.read_bytes()).hexdigest(), len(rows), "rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
