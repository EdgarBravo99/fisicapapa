# -*- coding: utf-8 -*-
"""Detect partially activated historical block-completion groups for V4.4."""

from __future__ import annotations

import argparse
import itertools
import json
from collections import Counter
from pathlib import Path

from v4_history_common import PRODUCTION_STATUS, utc_now, write_json


ENGINE_VERSION = "v4.4-block-completion"


def numbers_from_row(row: list[int]) -> list[int]:
    return [index + 1 for index, value in enumerate(row) if int(value) == 1]


def build_groups(matrix_path: str) -> dict:
    data = json.loads(Path(matrix_path).read_text(encoding="utf-8"))
    rows = [numbers_from_row(row) for row in data["matrix"]]
    counts: Counter[tuple[int, ...]] = Counter()
    for index in range(0, max(len(rows) - 2, 0)):
        window = rows[index : index + 3]
        union = sorted(set(number for row in window for number in row))
        if len(union) > 12:
            local_counts = Counter(number for row in window for number in row)
            union = [number for number, _ in local_counts.most_common(12)]
            union.sort()
        for size in (4, 5):
            for combo in itertools.combinations(union, size):
                counts[tuple(combo)] += 1
    recent_seen = set(number for row in rows[-5:] for number in row)
    groups = []
    candidate_counter: Counter[int] = Counter()
    for combo, count in counts.most_common(160):
        if count < 8:
            continue
        combo_set = set(combo)
        seen = sorted(combo_set & recent_seen)
        missing = sorted(combo_set - recent_seen)
        ratio = len(seen) / len(combo)
        if 0.40 <= ratio <= 0.85 and missing:
            score = round((count / max(len(rows), 1)) * ratio * (1 - abs(0.62 - ratio)), 6)
            row = {
                "numbers": list(combo),
                "historical_co_appearances": count,
                "recent_seen": seen,
                "missing": missing,
                "activation_ratio": round(ratio, 6),
                "block_completion_score": score,
            }
            groups.append(row)
            for number in missing:
                candidate_counter[number] += 1
    candidates = [
        {"number": number, "group_count": count}
        for number, count in candidate_counter.most_common(40)
    ]
    return {
        "generated_at": utc_now(),
        "engine_version": ENGINE_VERSION,
        "production_status": PRODUCTION_STATUS,
        "latest_draw": data["latest_draw"],
        "groups": groups[:80],
        "candidates": candidates,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build V4.4 block completion signals.")
    parser.add_argument("--matrix", default="v4_history_matrix.json")
    parser.add_argument("--output", default="v4_block_completion_signals.json")
    args = parser.parse_args()
    report = build_groups(args.matrix)
    write_json(args.output, report)
    print(f"Wrote {args.output}; groups={len(report['groups'])} candidates={len(report['candidates'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
