# -*- coding: utf-8 -*-
"""Rolling validation for the diagnostic post-ranking candidate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from v4_benchmark_hardening import load_replay_records, utc_now
from v4_post_ranking_holdout_experiment import _avg, _draw, _quality, evaluate_progressive_split

VERSION = "V4.4-post-ranking-rolling-validation"


def _fold_status(row: dict[str, Any]) -> str:
    return str(row.get("fold_status") or row.get("split_status") or "fail")


def build_rolling_validation(
    replay_memory: str = "v4_replay_memory.json",
    initial_train_size: int = 30,
    test_window_size: int = 5,
    step_size: int = 5,
) -> dict[str, Any]:
    records, input_state = load_replay_records(replay_memory)
    records = sorted(records, key=_draw)
    folds: list[dict[str, Any]] = []
    fold_number = 1
    for test_start in range(initial_train_size, len(records), step_size):
        test = records[test_start : test_start + test_window_size]
        if not test:
            continue
        train = records[:test_start]
        fold = evaluate_progressive_split(
            f"fold_{fold_number}_train_{_draw(train[0]) if train else 'none'}_{_draw(train[-1]) if train else 'none'}_test_{_draw(test[0])}_{_draw(test[-1])}",
            train,
            test,
            min_test_records=test_window_size,
        )
        fold["fold_id"] = fold.pop("split_id")
        fold["train_start"] = fold.pop("train_draw_start")
        fold["train_end"] = fold.pop("train_draw_end")
        fold["test_start"] = fold.pop("test_draw_start")
        fold["test_end"] = fold.pop("test_draw_end")
        fold["fold_status"] = fold.pop("split_status")
        fold["fold_passed"] = fold.pop("split_passed")
        folds.append(fold)
        fold_number += 1

    passed = sum(1 for row in folds if _fold_status(row) == "pass")
    partial = sum(1 for row in folds if _fold_status(row) == "partial")
    failed = sum(1 for row in folds if _fold_status(row) == "fail")
    avg_original = _avg([float(row["repaired_minus_original"]) for row in folds if row.get("repaired_minus_original") is not None])
    avg_frequency = _avg([float(row["repaired_minus_frequency"]) for row in folds if row.get("repaired_minus_frequency") is not None])
    avg_random = _avg([float(row["repaired_minus_random"]) for row in folds if row.get("repaired_minus_random") is not None])
    return {
        "version": VERSION,
        "generated_at": utc_now(),
        "mode": "diagnostic_only",
        "input_source": replay_memory,
        "input_state": input_state,
        "initial_train_size": initial_train_size,
        "test_window_size": test_window_size,
        "step_size": step_size,
        "records_count": len(records),
        "folds": folds,
        "summary": {
            "folds_total": len(folds),
            "folds_passed": passed,
            "folds_partial": partial,
            "folds_failed": failed,
            "avg_repaired_minus_original": avg_original,
            "avg_repaired_minus_frequency": avg_frequency,
            "avg_repaired_minus_random": avg_random,
            "rolling_signal_quality": _quality(passed, partial, len(folds), avg_original, avg_random, avg_frequency),
            "recommendation": "diagnostic_only",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run post-ranking rolling validation.")
    parser.add_argument("--replay-memory", default="v4_replay_memory.json")
    parser.add_argument("--output", default="v4_post_ranking_rolling_validation.json")
    parser.add_argument("--initial-train-size", type=int, default=30)
    parser.add_argument("--test-window-size", type=int, default=5)
    parser.add_argument("--step-size", type=int, default=5)
    args = parser.parse_args()
    report = build_rolling_validation(args.replay_memory, args.initial_train_size, args.test_window_size, args.step_size)
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {args.output}; quality={report['summary']['rolling_signal_quality']}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
