# -*- coding: utf-8 -*-
"""Stress-test frequency smoothing variants for the post-ranking candidate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from v4_benchmark_hardening import utc_now
from v4_post_ranking_validation_common import (
    CANDIDATE_VARIANT,
    SMOOTHING_VARIANTS,
    avg,
    evaluate_test_records,
    holdout_splits,
    load_sorted_replay_records,
    rolling_folds,
)

VERSION = "V4.4-post-ranking-smoothing-stress-test"


def _pass_rate(rows: list[dict[str, Any]]) -> float:
    return round(sum(1 for row in rows if row.get("split_status") == "pass") / len(rows), 6) if rows else 0.0


def _risk(rows: list[dict[str, Any]], avg_frequency: float | None) -> str:
    worst_frequency = min((float(row["policy_minus_frequency"]) for row in rows if row.get("policy_minus_frequency") is not None), default=0.0)
    pass_rate = _pass_rate(rows)
    if pass_rate < 0.5 or avg_frequency is None or avg_frequency <= 0 or worst_frequency < -0.75:
        return "high"
    if pass_rate < 0.75 or worst_frequency < -0.35:
        return "medium"
    return "low"


def _summarize_variant(name: str, holdout_rows: list[dict[str, Any]], rolling_rows: list[dict[str, Any]], window_rows: list[dict[str, Any]]) -> dict[str, Any]:
    all_rows = rolling_rows or holdout_rows
    avg_original = avg([float(row["policy_minus_original"]) for row in all_rows if row.get("policy_minus_original") is not None])
    avg_frequency = avg([float(row["policy_minus_frequency"]) for row in all_rows if row.get("policy_minus_frequency") is not None])
    avg_random = avg([float(row["policy_minus_random"]) for row in all_rows if row.get("policy_minus_random") is not None])
    worst_frequency = min((float(row["policy_minus_frequency"]) for row in rolling_rows if row.get("policy_minus_frequency") is not None), default=None)
    worst_random = min((float(row["policy_minus_random"]) for row in rolling_rows if row.get("policy_minus_random") is not None), default=None)
    return {
        "holdout_pass_rate": _pass_rate(holdout_rows),
        "rolling_pass_rate": _pass_rate(rolling_rows),
        "window_15_pass_rate": _pass_rate(window_rows),
        "folds_failed": sum(1 for row in rolling_rows if row.get("split_status") == "fail"),
        "top10_avg_hits": avg([float(row["policy_top10_avg_hits"]) for row in all_rows if row.get("policy_top10_avg_hits") is not None]),
        "top20_avg_hits": avg([float(row["policy_top20_avg_hits"]) for row in all_rows if row.get("policy_top20_avg_hits") is not None]),
        "avg_edge_vs_original": avg_original,
        "avg_edge_vs_frequency": avg_frequency,
        "avg_edge_vs_random": avg_random,
        "worst_fold_delta_vs_frequency": round(worst_frequency, 6) if worst_frequency is not None else None,
        "worst_fold_delta_vs_random": round(worst_random, 6) if worst_random is not None else None,
        "overfit_risk_proxy": _risk(rolling_rows, avg_frequency),
        "holdout_splits": [_compact_row(row) for row in holdout_rows],
        "rolling_folds": [_compact_row(row) for row in rolling_rows],
        "windows_15": [_compact_row(row) for row in window_rows],
    }


def _compact_row(row: dict[str, Any]) -> dict[str, Any]:
    keep = (
        "split_id",
        "variant",
        "train_records",
        "test_records",
        "records_evaluated",
        "test_start",
        "test_end",
        "original_top10_avg_hits",
        "repaired_top10_avg_hits",
        "frequency_top10_avg_hits",
        "policy_top10_avg_hits",
        "policy_minus_original",
        "policy_minus_frequency",
        "policy_minus_random",
        "split_status",
    )
    return {key: row.get(key) for key in keep}


def _best_variant(variants: dict[str, dict[str, Any]]) -> dict[str, str | None]:
    if not variants:
        return {"name": None, "reason": "no smoothing variants evaluated"}
    def score(item: tuple[str, dict[str, Any]]) -> tuple[float, float, float, float]:
        _, row = item
        return (
            float(row.get("rolling_pass_rate") or 0.0),
            float(row.get("avg_edge_vs_frequency") or -999.0),
            float(row.get("avg_edge_vs_random") or -999.0),
            float(row.get("worst_fold_delta_vs_frequency") or -999.0),
        )

    name, row = max(variants.items(), key=score)
    return {
        "name": name,
        "reason": f"best rolling/frequency/random balance; rolling_pass_rate={row.get('rolling_pass_rate')}",
    }


def build_smoothing_stress_test(replay_memory: str = "v4_replay_memory.json") -> dict[str, Any]:
    records, input_state = load_sorted_replay_records(replay_memory)
    variants: dict[str, dict[str, Any]] = {}
    windows_15 = [(records[:index], records[index : index + 15]) for index in range(15, len(records), 15)]
    for variant in SMOOTHING_VARIANTS:
        holdout_rows = [
            evaluate_test_records(split_id, train, test, variant, min_test_records=min_records)
            for split_id, train, test, min_records in holdout_splits(records)
            if test
        ]
        rolling_rows = [
            evaluate_test_records(fold_id, train, test, variant, min_test_records=5)
            for fold_id, train, test in rolling_folds(records)
        ]
        window_rows = [
            evaluate_test_records(f"window_15_{test[0].get('target_draw')}_{test[-1].get('target_draw')}", train, test, variant, min_test_records=10)
            for train, test in windows_15
            if train and test
        ]
        variants[variant] = _summarize_variant(variant, holdout_rows, rolling_rows, window_rows)

    best = _best_variant(variants)
    raw_rate = float((variants.get("frequency_raw") or {}).get("rolling_pass_rate") or 0.0)
    best_rate = float((variants.get(str(best.get("name"))) or {}).get("rolling_pass_rate") or 0.0)
    return {
        "version": VERSION,
        "generated_at": utc_now(),
        "mode": "diagnostic_only",
        "input_source": replay_memory,
        "input_state": input_state,
        "records_count": len(records),
        "candidate_base": CANDIDATE_VARIANT,
        "variants": variants,
        "best_smoothing_variant": best,
        "summary": {
            "smoothing_improves_rolling": best_rate > raw_rate,
            "best_rolling_pass_rate": best_rate,
            "raw_rolling_pass_rate": raw_rate,
            "recommendation": "diagnostic_only",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run post-ranking frequency smoothing stress test.")
    parser.add_argument("--replay-memory", default="v4_replay_memory.json")
    parser.add_argument("--output", default="v4_post_ranking_smoothing_stress_test.json")
    args = parser.parse_args()
    report = build_smoothing_stress_test(args.replay_memory)
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {args.output}; best={report['best_smoothing_variant']['name']}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
