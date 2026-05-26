# -*- coding: utf-8 -*-
"""Download the raw Revancha history CSV from pakinja/pakin for V4.4."""

from __future__ import annotations

import argparse
import urllib.request
from pathlib import Path

from v4_history_common import PRODUCTION_STATUS, parse_int, sha256_text, utc_now, write_json


ENGINE_VERSION = "v4.4-scraper-pakin"
SOURCE_URL = "https://raw.githubusercontent.com/pakinja/pakin/master/Revancha.csv"


def fetch_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "fisicapapa-v44-scraper"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8-sig", errors="replace")


def latest_draw_from_text(raw: str) -> int:
    lines = [line for line in raw.splitlines() if line.strip()]
    if len(lines) < 2:
        return 0
    latest = 0
    for line in lines[1:]:
        first = line.split(",", 1)[0]
        draw = parse_int(first)
        if draw is not None:
            latest = max(latest, draw)
    return latest


def main() -> int:
    parser = argparse.ArgumentParser(description="Download Pakin Revancha CSV into v4_scraper_raw.csv.")
    parser.add_argument("--url", default=SOURCE_URL)
    parser.add_argument("--output", default="v4_scraper_raw.csv")
    parser.add_argument("--report", default="v4_scraper_report.json")
    args = parser.parse_args()

    raw = fetch_text(args.url)
    rows = [line for line in raw.splitlines() if line.strip()]
    if len(rows) <= 1:
        raise SystemExit("Pakin CSV download returned no data rows.")
    output = Path(args.output)
    output.write_text(raw if raw.endswith("\n") else raw + "\n", encoding="utf-8")
    report = {
        "generated_at": utc_now(),
        "engine_version": ENGINE_VERSION,
        "production_status": PRODUCTION_STATUS,
        "source_url": args.url,
        "rows_downloaded": max(len(rows) - 1, 0),
        "latest_draw": latest_draw_from_text(raw),
        "output_file": str(output),
        "source_sha256": sha256_text(raw),
    }
    write_json(args.report, report)
    print(f"Wrote {args.output}; rows={report['rows_downloaded']} latest_draw={report['latest_draw']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
