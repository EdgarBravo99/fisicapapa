# -*- coding: utf-8 -*-
"""Build the V4.4 binary historical matrix from canonical Revancha history."""

from __future__ import annotations

import argparse

from v4_history_common import MAX_NUMBER, PRODUCTION_STATUS, file_sha256, read_history_csv, utc_now, write_json


ENGINE_VERSION = "v4.4-history-matrix"


def build_matrix(csv_path: str) -> dict:
    draws = read_history_csv(csv_path)
    if not draws:
        raise SystemExit(f"No valid draws found in {csv_path}.")
    matrix = []
    draw_ids = []
    for draw in draws:
        row = [0] * MAX_NUMBER
        for number in draw["numbers"]:
            row[number - 1] = 1
        if sum(row) != 6:
            raise SystemExit(f"Matrix row for draw {draw['draw_id']} does not sum to 6.")
        matrix.append(row)
        draw_ids.append(draw["draw_id"])
    return {
        "generated_at": utc_now(),
        "engine_version": ENGINE_VERSION,
        "production_status": PRODUCTION_STATUS,
        "source_file": csv_path,
        "source_sha256": file_sha256(csv_path),
        "latest_draw": draw_ids[-1],
        "draws": draw_ids,
        "numbers": list(range(1, MAX_NUMBER + 1)),
        "matrix": matrix,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build V4.4 history matrix.")
    parser.add_argument("--csv", default="revancha.csv")
    parser.add_argument("--output", default="v4_history_matrix.json")
    args = parser.parse_args()
    report = build_matrix(args.csv)
    write_json(args.output, report)
    print(f"Wrote {args.output}; draws={len(report['draws'])} latest_draw={report['latest_draw']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
