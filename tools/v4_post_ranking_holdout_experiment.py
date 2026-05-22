# -*- coding: utf-8 -*-
"""Temporal holdout validation for a diagnostic post-ranking candidate.

This script reads replay memory only. It never modifies replay memory,
resultados.json, official scores, or any prior.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from v4_benchmark_hardening import load_replay_records, parse_int, target_numbers, utc_now
from v4_ranking_repair_experiment import (
    RANDOM_TOP10_HITS,
    RANDOM_TOP20_HITS,
    _frequency_rank,
    _hits,
    _original_rank,
    _unique_ranked,
)

VERSION = "V4.4-post-ranking-holdout-experiment"
CANDIDATE_VARIANT = "top6_preserved_plus_frequency_no_duplicates"


def _avg(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 6) if values else None


def _draw(record: dict[str, Any]) -> int:
    return parse_int(record.get("target_draw")) or 0


def _records_in_range(records: list[dict[str, Any]], low: int | None, high: int | None) -> list[dict[str, Any]]:
    output = []
    for record in records:
        draw = _draw(record)
        if low is not None and draw < low:
            continue
        if high is not None and draw > high:
            continue
        output.append(record)
    return output


def _counts_from(records: list[dict[str, Any]]) -> Counter[int]:
    counts: Counter[int] = Counter()
    for record in records:
        counts.update(target_numbers(record))
    return counts


def _candidate_rank(record: dict[str, Any], counts: Counter[int]) -> list[int]:
    original = _original_rank(record)
    frequency = _frequency_rank(counts)
    return _unique_ranked(original[:6] + frequency)


def _split_status(
    repaired_minus_original: float | None,
    repaired_minus_frequency: float | None,
    repaired_minus_random: float | None,
    evaluated: int,
    min_test_records: int = 10,
) -> tuple[str, bool, str]:
    if evaluated < min_test_records:
        return "fail", False, f"test_records below {min_test_records}; confidence is too low."
    if repaired_minus_original is None or repaired_minus_frequency is None or repaired_minus_random is None:
        return "fail", False, "missing comparable metrics."
    if repaired_minus_original > 0 and repaired_minus_random > 0 and repaired_minus_frequency >= 0:
        return "pass", True, "candidate beats original, random, and progressive frequency in test."
    if repaired_minus_original > 0 and repaired_minus_random > 0 and repaired_minus_frequency >= -0.1:
        return "partial", False, "candidate beats original and random, but frequency edge is slightly negative."
    return "fail", False, "candidate does not clear original/random/frequency holdout gates."


def evaluate_progressive_split(
    split_id: str,
    train_records: list[dict[str, Any]],
    test_records: list[dict[str, Any]],
    min_test_records: int = 10,
) -> dict[str, Any]:
    counts = _counts_from(train_records)
    original_top10: list[float] = []
    repaired_top10: list[float] = []
    frequency_top10: list[float] = []
    original_top20: list[float] = []
    repaired_top20: list[float] = []
    frequency_top20: list[float] = []
    skipped = 0

    for record in sorted(test_records, key=_draw):
        target = set(target_numbers(record))
        if not target or not counts:
            skipped += 1
            counts.update(target)
            continue
        original = _original_rank(record)
        frequency = _frequency_rank(counts)
        repaired = _candidate_rank(record, counts)
        original_top10.append(float(_hits(original, target, 10) or 0))
        repaired_top10.append(float(_hits(repaired, target, 10) or 0))
        frequency_top10.append(float(_hits(frequency, target, 10) or 0))
        original_top20.append(float(_hits(original, target, 20) or 0))
        repaired_top20.append(float(_hits(repaired, target, 20) or 0))
        frequency_top20.append(float(_hits(frequency, target, 20) or 0))
        counts.update(target)

    original10 = _avg(original_top10)
    repaired10 = _avg(repaired_top10)
    frequency10 = _avg(frequency_top10)
    original20 = _avg(original_top20)
    repaired20 = _avg(repaired_top20)
    frequency20 = _avg(frequency_top20)
    repaired_minus_original = round(repaired10 - original10, 6) if repaired10 is not None and original10 is not None else None
    repaired_minus_frequency = round(repaired10 - frequency10, 6) if repaired10 is not None and frequency10 is not None else None
    repaired_minus_random = round(repaired10 - RANDOM_TOP10_HITS, 6) if repaired10 is not None else None
    status, passed, reason = _split_status(repaired_minus_original, repaired_minus_frequency, repaired_minus_random, len(repaired_top10), min_test_records)
    test_draws = [_draw(record) for record in test_records if _draw(record)]
    train_draws = [_draw(record) for record in train_records if _draw(record)]
    return {
        "split_id": split_id,
        "train_records": len(train_records),
        "test_records": len(test_records),
        "records_evaluated": len(repaired_top10),
        "records_skipped_no_prior": skipped,
        "train_draw_start": min(train_draws) if train_draws else None,
        "train_draw_end": max(train_draws) if train_draws else None,
        "test_draw_start": min(test_draws) if test_draws else None,
        "test_draw_end": max(test_draws) if test_draws else None,
        "original_top10_avg_hits": original10,
        "repaired_top10_avg_hits": repaired10,
        "frequency_top10_avg_hits": frequency10,
        "random_top10_expected": RANDOM_TOP10_HITS,
        "repaired_minus_original": repaired_minus_original,
        "repaired_minus_frequency": repaired_minus_frequency,
        "repaired_minus_random": repaired_minus_random,
        "repaired_top20_avg_hits": repaired20,
        "original_top20_avg_hits": original20,
        "frequency_top20_avg_hits": frequency20,
        "random_top20_expected": RANDOM_TOP20_HITS,
        "repaired_minus_original_top20": round(repaired20 - original20, 6) if repaired20 is not None and original20 is not None else None,
        "repaired_minus_frequency_top20": round(repaired20 - frequency20, 6) if repaired20 is not None and frequency20 is not None else None,
        "split_status": status,
        "split_passed": passed,
        "reason": reason,
    }


def _quality(pass_count: int, partial_count: int, total: int, avg_original: float | None, avg_random: float | None, avg_frequency: float | None) -> str:
    if not total:
        return "unknown"
    pass_rate = pass_count / total
    useful_edges = bool(
        avg_original is not None
        and avg_random is not None
        and avg_frequency is not None
        and avg_original > 0
        and avg_random > 0
        and avg_frequency >= 0
    )
    if pass_rate >= 0.75 and useful_edges:
        return "strong"
    if pass_rate >= 0.5 and avg_original is not None and avg_original > 0 and avg_random is not None and avg_random > 0:
        return "moderate"
    if pass_count or partial_count or (avg_original is not None and avg_original > 0):
        return "weak"
    return "unknown"


def _aggregate_split(split_id: str, splits: list[dict[str, Any]]) -> dict[str, Any]:
    train_records = sum(int(row.get("train_records") or 0) for row in splits)
    test_records = sum(int(row.get("test_records") or 0) for row in splits)
    evaluated = sum(int(row.get("records_evaluated") or 0) for row in splits)
    values = {
        key: _avg([float(row[key]) for row in splits if row.get(key) is not None])
        for key in (
            "original_top10_avg_hits",
            "repaired_top10_avg_hits",
            "frequency_top10_avg_hits",
            "repaired_minus_original",
            "repaired_minus_frequency",
            "repaired_minus_random",
            "repaired_top20_avg_hits",
            "original_top20_avg_hits",
            "frequency_top20_avg_hits",
            "repaired_minus_original_top20",
            "repaired_minus_frequency_top20",
        )
    }
    status, passed, reason = _split_status(
        values["repaired_minus_original"],
        values["repaired_minus_frequency"],
        values["repaired_minus_random"],
        evaluated,
    )
    test_starts = [row.get("test_draw_start") for row in splits if row.get("test_draw_start") is not None]
    test_ends = [row.get("test_draw_end") for row in splits if row.get("test_draw_end") is not None]
    return {
        "split_id": split_id,
        "train_records": train_records,
        "test_records": test_records,
        "records_evaluated": evaluated,
        "test_draw_start": min(test_starts) if test_starts else None,
        "test_draw_end": max(test_ends) if test_ends else None,
        **values,
        "random_top10_expected": RANDOM_TOP10_HITS,
        "random_top20_expected": RANDOM_TOP20_HITS,
        "split_status": status,
        "split_passed": passed,
        "reason": f"{reason} Aggregate of {len(splits)} chronological sub-splits.",
        "sub_splits": splits,
    }


def build_holdout_experiment(replay_memory: str = "v4_replay_memory.json") -> dict[str, Any]:
    records, input_state = load_replay_records(replay_memory)
    records = sorted(records, key=_draw)
    splits: list[dict[str, Any]] = []
    specs = [
        ("train_4155_4199_test_4200_4214", 4155, 4199, 4200, 4214),
        ("train_4155_4184_test_4185_4214", 4155, 4184, 4185, 4214),
        ("train_4155_4169_test_4170_4214", 4155, 4169, 4170, 4214),
    ]
    for split_id, train_low, train_high, test_low, test_high in specs:
        train = _records_in_range(records, train_low, train_high)
        test = _records_in_range(records, test_low, test_high)
        splits.append(evaluate_progressive_split(split_id, train, test))

    rolling_subsplits = []
    all_draws = [_draw(record) for record in records]
    if all_draws:
        ordered = records
        for start in range(15, len(ordered), 15):
            test = ordered[start : start + 15]
            if not test:
                continue
            train = ordered[:start]
            rolling_subsplits.append(evaluate_progressive_split(f"rolling_15_step_{_draw(test[0])}_{_draw(test[-1])}", train, test))
    splits.append(_aggregate_split("rolling_15_step", rolling_subsplits))

    loo_subsplits = []
    windows = [records[index : index + 15] for index in range(0, len(records), 15)]
    for index, test in enumerate(windows):
        train = [record for prior in windows[:index] for record in prior]
        if not train or not test:
            continue
        loo_subsplits.append(evaluate_progressive_split(f"leave_one_window_out_prior_only_{_draw(test[0])}_{_draw(test[-1])}", train, test))
    splits.append(_aggregate_split("leave_one_window_out", loo_subsplits))

    pass_count = sum(1 for row in splits if row.get("split_status") == "pass")
    partial_count = sum(1 for row in splits if row.get("split_status") == "partial")
    fail_count = sum(1 for row in splits if row.get("split_status") == "fail")
    avg_original = _avg([float(row["repaired_minus_original"]) for row in splits if row.get("repaired_minus_original") is not None])
    avg_frequency = _avg([float(row["repaired_minus_frequency"]) for row in splits if row.get("repaired_minus_frequency") is not None])
    avg_random = _avg([float(row["repaired_minus_random"]) for row in splits if row.get("repaired_minus_random") is not None])
    return {
        "version": VERSION,
        "generated_at": utc_now(),
        "mode": "diagnostic_only",
        "candidate_variant": CANDIDATE_VARIANT,
        "input_source": replay_memory,
        "input_state": input_state,
        "records_count": len(records),
        "splits": splits,
        "summary": {
            "splits_passed": pass_count,
            "splits_partial": partial_count,
            "splits_failed": fail_count,
            "splits_total": len(splits),
            "avg_edge_vs_original": avg_original,
            "avg_edge_vs_frequency": avg_frequency,
            "avg_edge_vs_random": avg_random,
            "holdout_signal_quality": _quality(pass_count, partial_count, len(splits), avg_original, avg_random, avg_frequency),
            "recommendation": "diagnostic_only",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run post-ranking holdout validation.")
    parser.add_argument("--replay-memory", default="v4_replay_memory.json")
    parser.add_argument("--output", default="v4_post_ranking_holdout_experiment.json")
    args = parser.parse_args()
    report = build_holdout_experiment(args.replay_memory)
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {args.output}; quality={report['summary']['holdout_signal_quality']}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
