# -*- coding: utf-8 -*-
"""Construct temporal pair-lag signals for V4.4."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from v4_history_common import MAX_NUMBER, PRODUCTION_STATUS, utc_now, write_json


ENGINE_VERSION = "v4.4-pair-lag"


def numbers_from_row(row: list[int]) -> list[int]:
    return [index + 1 for index, value in enumerate(row) if int(value) == 1]


def build_pair_lag(matrix_path: str, lag_window: int = 3) -> dict:
    data = json.loads(Path(matrix_path).read_text(encoding="utf-8"))
    rows = [numbers_from_row(row) for row in data["matrix"]]
    opportunities: Counter[tuple[int, int]] = Counter()
    matches: Counter[tuple[int, int]] = Counter()
    max_index = len(rows) - lag_window
    for index in range(max_index):
        triggers = rows[index]
        future = set(number for row in rows[index + 1 : index + 1 + lag_window] for number in row)
        for trigger in triggers:
            for candidate in range(1, MAX_NUMBER + 1):
                if candidate == trigger:
                    continue
                key = (trigger, candidate)
                opportunities[key] += 1
                if candidate in future:
                    matches[key] += 1
    signals = []
    for key, total in opportunities.items():
        hit_count = matches[key]
        score = hit_count / total if total else 0.0
        if hit_count >= 5 and score >= 0.15:
            signals.append(
                {
                    "trigger": key[0],
                    "candidate": key[1],
                    "historical_matches": hit_count,
                    "total_opportunities": total,
                    "pair_lag_score": round(score, 6),
                }
            )
    signals.sort(key=lambda row: (-row["pair_lag_score"], -row["historical_matches"], row["trigger"], row["candidate"]))
    latest_numbers = set(rows[-1]) if rows else set()
    active = []
    for row in signals:
        if row["trigger"] in latest_numbers and row["candidate"] not in active:
            active.append(row["candidate"])
    return {
        "generated_at": utc_now(),
        "engine_version": ENGINE_VERSION,
        "production_status": PRODUCTION_STATUS,
        "latest_draw": data["latest_draw"],
        "lag_window": lag_window,
        "signals": signals[:500],
        "active_candidates": active[:40],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build V4.4 pair-lag signals.")
    parser.add_argument("--matrix", default="v4_history_matrix.json")
    parser.add_argument("--lag-window", type=int, default=3)
    parser.add_argument("--output", default="v4_pair_lag_signals.json")
    args = parser.parse_args()
    report = build_pair_lag(args.matrix, args.lag_window)
    write_json(args.output, report)
    print(f"Wrote {args.output}; signals={len(report['signals'])} active={len(report['active_candidates'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
