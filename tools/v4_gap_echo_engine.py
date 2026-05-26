# -*- coding: utf-8 -*-
"""Compute diagnostic V4.4 gap echo signals for numbers 1-56."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from v4_history_common import MAX_NUMBER, PRODUCTION_STATUS, safe_avg, safe_median, utc_now, write_json


ENGINE_VERSION = "v4.4-gap-echo"


def load_matrix(path: str) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("production_status") != PRODUCTION_STATUS:
        raise SystemExit(f"{path} is not a review_default matrix.")
    return data


def build_gap_echo(matrix_path: str) -> dict:
    data = load_matrix(matrix_path)
    draws = [int(draw) for draw in data["draws"]]
    matrix = data["matrix"]
    latest = int(data["latest_draw"])
    numbers: dict[str, dict] = {}
    active: list[int] = []
    for number in range(1, MAX_NUMBER + 1):
        seen = [draws[index] for index, row in enumerate(matrix) if int(row[number - 1]) == 1]
        gaps = [current - previous for previous, current in zip(seen, seen[1:])]
        current_gap = latest - seen[-1] if seen else latest - draws[0] + 1
        median_gap = safe_median([float(value) for value in gaps])
        avg_gap = safe_avg([float(value) for value in gaps])
        if median_gap <= 0:
            score = 0.0
        else:
            distance = abs(current_gap - median_gap)
            score = max(0.0, 1.0 - min(distance / max(median_gap, 1.0), 1.0))
        in_window = bool(median_gap and median_gap * 0.65 <= current_gap <= median_gap * 1.45)
        if in_window and score >= 0.45:
            active.append(number)
        numbers[str(number)] = {
            "appearances": len(seen),
            "historical_gaps": gaps,
            "avg_gap": avg_gap,
            "median_gap": median_gap,
            "min_gap": min(gaps) if gaps else 0,
            "max_gap": max(gaps) if gaps else 0,
            "current_gap": current_gap,
            "in_active_window": in_window,
            "gap_echo_score": round(score, 6),
        }
    return {
        "generated_at": utc_now(),
        "engine_version": ENGINE_VERSION,
        "production_status": PRODUCTION_STATUS,
        "latest_draw": latest,
        "numbers": numbers,
        "active_candidates": active,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build V4.4 gap echo signals.")
    parser.add_argument("--matrix", default="v4_history_matrix.json")
    parser.add_argument("--output", default="v4_gap_echo_output.json")
    args = parser.parse_args()
    report = build_gap_echo(args.matrix)
    write_json(args.output, report)
    print(f"Wrote {args.output}; active_candidates={len(report['active_candidates'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
