# -*- coding: utf-8 -*-
"""Reconstruct the canonical V4.4 Revancha CSV from the raw Pakin download."""

from __future__ import annotations

import argparse
import csv
import tempfile
from pathlib import Path
from typing import Any

from v4_history_common import (
    PRODUCTION_STATUS,
    canonical_row_values,
    file_sha256,
    sequence_gaps,
    sha256_text,
    utc_now,
    validate_draw,
    write_canonical_csv,
    write_json,
)


ENGINE_VERSION = "v4.4-csv-reconstructor"


def load_rows(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    raw_text = path.read_text(encoding="utf-8-sig", errors="replace")
    reader = csv.DictReader(raw_text.splitlines())
    rows: dict[int, dict[str, Any]] = {}
    invalid: list[dict[str, Any]] = []
    duplicates = 0
    for index, row in enumerate(reader, start=2):
        draw, numbers = canonical_row_values(row)
        reason = validate_draw(draw, numbers)
        if reason is not None:
            invalid.append({"line": index, "reason": reason, "row": row})
            continue
        if int(draw) in rows:
            duplicates += 1
        rows[int(draw)] = {"draw_id": int(draw), "numbers": sorted(numbers)}
    return [rows[key] for key in sorted(rows)], invalid, duplicates


def atomic_write_canonical(path: Path, rows: list[dict[str, Any]]) -> str:
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", delete=False, dir=path.parent, suffix=".tmp") as handle:
        temp_path = Path(handle.name)
    write_canonical_csv(temp_path, rows)
    text = temp_path.read_text(encoding="utf-8")
    temp_path.replace(path)
    return text


def main() -> int:
    parser = argparse.ArgumentParser(description="Reconstruct canonical revancha.csv from v4_scraper_raw.csv.")
    parser.add_argument("--input", default="v4_scraper_raw.csv")
    parser.add_argument("--output", default="revancha.csv")
    parser.add_argument("--report", default="v4_csv_reconstruction_report.json")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        raise SystemExit(f"Missing input file: {input_path}")
    rows, invalid, duplicates = load_rows(input_path)
    if not rows:
        raise SystemExit("No valid rows found in scraper raw CSV.")
    output_path = Path(args.output)
    csv_text = atomic_write_canonical(output_path, rows)
    draw_ids = [row["draw_id"] for row in rows]
    report = {
        "generated_at": utc_now(),
        "engine_version": ENGINE_VERSION,
        "production_status": PRODUCTION_STATUS,
        "input_file": str(input_path),
        "output_file": str(output_path),
        "rows_in": max(sum(1 for line in input_path.read_text(encoding="utf-8-sig", errors="replace").splitlines() if line.strip()) - 1, 0),
        "rows_out": len(rows),
        "latest_draw": rows[-1]["draw_id"],
        "duplicates_removed": duplicates,
        "invalid_rows": invalid[:100],
        "sequence_gaps": sequence_gaps(draw_ids),
        "source_sha256": file_sha256(input_path),
        "output_sha256": sha256_text(csv_text),
    }
    write_json(args.report, report)
    print(f"Wrote {args.output}; rows={len(rows)} latest_draw={report['latest_draw']} invalid={len(invalid)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
