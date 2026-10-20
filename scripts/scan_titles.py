"""List the titles of every R page of a filing (exploration aid; reads the first 6 kB of each page)."""

from __future__ import annotations

import html
import re
import subprocess
import sys
import time

USER_AGENT = "David Lindgreen lindgreendavid@gmail.com portfolio research"


def main() -> int:
    cik, folder, last = sys.argv[1], sys.argv[2], int(sys.argv[3])
    for number in range(1, last + 1):
        url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{folder}/R{number}.htm"
        raw = subprocess.run(
            ["curl", "-sS", "-m", "60", "-r", "0-9000", "-H", f"User-Agent: {USER_AGENT}", url],
            capture_output=True,
        ).stdout.decode("utf-8", errors="ignore")
        match = re.search(r'<th class="tl"[^>]*>.*?<div[^>]*>(.*?)</div>', raw, re.S)
        title = html.unescape(re.sub(r"<[^>]+>", "", match.group(1))).strip() if match else "?"
        print(number, title[:110])
        time.sleep(0.25)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
