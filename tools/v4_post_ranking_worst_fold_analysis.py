# -*- coding: utf-8 -*-
"""Explain the weakest folds for post-ranking diagnostics."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from v4_benchmark_hardening import target_numbers, utc_now
from v4_post_ranking_validation_common import (
    candidate_rank,
    draw_id,
    frequency_rank,
    load_sorted_replay_records,
)
from v4_ranking_repair_experiment import _hits, _original_rank

VERSION = "V4.4-post-ranking-worst-fold-analysis"


def _load(path: str | Path) -> dict[str, Any] | None:
    file_path = Path(path)
    if not file_path.exists():
        return None
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _all_folds(rolling: dict[str, Any], smoothing: dict[str, Any], confidence: dict[str, Any]) -> list[dict[str, Any]]:
    best_policy_name = (confidence.get("best_policy") or {}).get("name")
    if best_policy_name:
        folds = confidence.get("best_policy_folds")
        if isinstance(folds, list) and folds:
            return [row for row in folds if isinstance(row, dict)]
    best_variant = (smoothing.get("best_smoothing_variant") or {}).get("name")
    if best_variant:
        variant = (smoothing.get("variants") or {}).get(best_variant, {})
        folds = variant.get("rolling_folds")
        if isinstance(folds, list) and folds:
            return [row for row in folds if isinstance(row, dict)]
    folds = rolling.get("folds")
    return [row for row in folds if isinstance(row, dict)] if isinstance(folds, list) else []


def _reason(row: dict[str, Any]) -> str:
    original = float(row.get("original_top10_avg_hits") or 0.0)
    repaired = float(row.get("repaired_top10_avg_hits") or row.get("policy_top10_avg_hits") or 0.0)
    frequency = float(row.get("frequency_top10_avg_hits") or 0.0)
    train_records = int(row.get("train_records") or 0)
    if train_records < 30:
        return "insufficient_history"
    if frequency > repaired and frequency > original:
        return "frequency_spike"
    if original >= repaired and repaired <= 1.0:
        return "top6_quality_drop"
    if frequency <= 1.0 and repaired <= 1.0 and original <= 1.0:
        return "flat_signal"
    if repaired < frequency and original < frequency:
        return "overreactive_frequency"
    return "unknown"


def _target_rows(records: list[dict[str, Any]], fold: dict[str, Any], variant: str) -> list[dict[str, Any]]:
    start = int(fold.get("test_start") or fold.get("test_draw_start") or 0)
    end = int(fold.get("test_end") or fold.get("test_draw_end") or 0)
    rows = []
    for record in records:
        draw = draw_id(record)
        if not (start <= draw <= end):
            continue
        prior = [row for row in records if draw_id(row) < draw]
        target = set(target_numbers(record))
        original = _original_rank(record)
        frequency = frequency_rank(prior, variant)
        repaired = candidate_rank(record, prior, variant)
        rows.append(
            {
                "target_draw": draw,
                "target_numbers": sorted(target),
                "original_top10_hits": _hits(original, target, 10),
                "repaired_top10_hits": _hits(repaired, target, 10),
                "frequency_top10_hits": _hits(frequency, target, 10),
                "missed_by_repair": sorted(target - set(repaired[:10])),
                "repair_top10": repaired[:10],
            }
        )
    return rows


def build_worst_fold_analysis(
    replay_memory: str = "v4_replay_memory.json",
    rolling_path: str = "v4_post_ranking_rolling_validation.json",
    smoothing_path: str = "v4_post_ranking_smoothing_stress_test.json",
    confidence_path: str = "v4_post_ranking_confidence_gate_experiment.json",
) -> dict[str, Any]:
    records, input_state = load_sorted_replay_records(replay_memory)
    rolling = _load(rolling_path) or {}
    smoothing = _load(smoothing_path) or {}
    confidence = _load(confidence_path) or {}
    folds = _all_folds(rolling, smoothing, confidence)
    variant = str((confidence.get("smoothing_variant_used") or (smoothing.get("best_smoothing_variant") or {}).get("name") or "frequency_raw"))
    for row in folds:
        row["reason_hypothesis"] = _reason(row)
    by_frequency = min(folds, key=lambda row: float(row.get("policy_minus_frequency") if row.get("policy_minus_frequency") is not None else row.get("repaired_minus_frequency") or 999), default={})
    by_random = min(folds, key=lambda row: float(row.get("policy_minus_random") if row.get("policy_minus_random") is not None else row.get("repaired_minus_random") or 999), default={})
    by_original = min(folds, key=lambda row: float(row.get("policy_minus_original") if row.get("policy_minus_original") is not None else row.get("repaired_minus_original") or 999), default={})
    worst_folds = []
    for label, row in (("worst_fold_by_frequency_delta", by_frequency), ("worst_fold_by_random_delta", by_random), ("worst_fold_by_original_delta", by_original)):
        if row:
            worst_folds.append({**row, "worst_type": label, "target_level_misses": _target_rows(records, row, variant)})
    patterns = Counter(row.get("reason_hypothesis") or "unknown" for row in folds)
    return {
        "version": VERSION,
        "generated_at": utc_now(),
        "mode": "diagnostic_only",
        "input_source": replay_memory,
        "input_state": input_state,
        "smoothing_variant": variant,
        "worst_fold_by_frequency_delta": by_frequency,
        "worst_fold_by_random_delta": by_random,
        "worst_fold_by_original_delta": by_original,
        "folds_where_original_wins": [row for row in folds if float(row.get("policy_minus_original") if row.get("policy_minus_original") is not None else row.get("repaired_minus_original") or 0.0) < 0],
        "folds_where_frequency_wins": [row for row in folds if float(row.get("policy_minus_frequency") if row.get("policy_minus_frequency") is not None else row.get("repaired_minus_frequency") or 0.0) < 0],
        "folds_where_repair_wins": [row for row in folds if str(row.get("split_status") or row.get("fold_status")) == "pass"],
        "worst_folds": worst_folds,
        "failure_patterns": {
            "frequency_spike_count": patterns.get("frequency_spike", 0),
            "top6_quality_drop_count": patterns.get("top6_quality_drop", 0),
            "overreactive_frequency_count": patterns.get("overreactive_frequency", 0),
            "insufficient_history_count": patterns.get("insufficient_history", 0),
            "flat_signal_count": patterns.get("flat_signal", 0),
            "unknown_count": patterns.get("unknown", 0),
        },
        "summary": {
            "main_failure_pattern": patterns.most_common(1)[0][0] if patterns else "unknown",
            "recommendation": "diagnostic_only",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze worst post-ranking folds.")
    parser.add_argument("--replay-memory", default="v4_replay_memory.json")
    parser.add_argument("--rolling", default="v4_post_ranking_rolling_validation.json")
    parser.add_argument("--smoothing", default="v4_post_ranking_smoothing_stress_test.json")
    parser.add_argument("--confidence", default="v4_post_ranking_confidence_gate_experiment.json")
    parser.add_argument("--output", default="v4_post_ranking_worst_fold_analysis.json")
    args = parser.parse_args()
    report = build_worst_fold_analysis(args.replay_memory, args.rolling, args.smoothing, args.confidence)
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {args.output}; pattern={report['summary']['main_failure_pattern']}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
