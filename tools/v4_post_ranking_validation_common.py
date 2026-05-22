# -*- coding: utf-8 -*-
"""Shared read-only helpers for post-ranking validation diagnostics."""

from __future__ import annotations

from collections import Counter
from typing import Any

from v4_benchmark_hardening import MAX_NUMBER, load_replay_records, parse_int, target_numbers
from v4_ranking_repair_experiment import RANDOM_TOP10_HITS, RANDOM_TOP20_HITS, _hits, _original_rank, _unique_ranked

CANDIDATE_VARIANT = "top6_preserved_plus_frequency_no_duplicates"
SMOOTHING_VARIANTS = (
    "frequency_raw",
    "frequency_laplace_1",
    "frequency_laplace_0_5",
    "frequency_decay_0_95",
    "frequency_decay_0_90",
    "frequency_window_15",
    "frequency_window_30",
    "frequency_window_45",
)


def avg(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 6) if values else None


def draw_id(record: dict[str, Any]) -> int:
    return parse_int(record.get("target_draw")) or 0


def load_sorted_replay_records(path: str = "v4_replay_memory.json") -> tuple[list[dict[str, Any]], dict[str, Any]]:
    records, state = load_replay_records(path)
    return sorted(records, key=draw_id), state


def frequency_rank(prior_records: list[dict[str, Any]], variant: str = "frequency_raw") -> list[int]:
    if variant == "frequency_laplace_1":
        scores = {number: 1.0 for number in range(1, MAX_NUMBER + 1)}
    elif variant == "frequency_laplace_0_5":
        scores = {number: 0.5 for number in range(1, MAX_NUMBER + 1)}
    else:
        scores = {number: 0.0 for number in range(1, MAX_NUMBER + 1)}

    records = prior_records
    if variant.startswith("frequency_window_"):
        try:
            window = int(variant.rsplit("_", 1)[1])
        except ValueError:
            window = len(prior_records)
        records = prior_records[-window:]

    if variant in {"frequency_decay_0_95", "frequency_decay_0_90"}:
        decay = 0.95 if variant.endswith("0_95") else 0.90
        total = len(records)
        for index, record in enumerate(records):
            weight = decay ** max(total - index - 1, 0)
            for number in target_numbers(record):
                scores[number] += weight
    else:
        counts: Counter[int] = Counter()
        for record in records:
            counts.update(target_numbers(record))
        for number, count in counts.items():
            scores[number] += float(count)

    return [number for number, _ in sorted(scores.items(), key=lambda item: (-item[1], item[0]))]


def candidate_rank(record: dict[str, Any], prior_records: list[dict[str, Any]], variant: str = "frequency_raw") -> list[int]:
    original = _original_rank(record)
    return _unique_ranked(original[:6] + frequency_rank(prior_records, variant))


def jaccard(left: list[int], right: list[int]) -> float:
    union = set(left) | set(right)
    return len(set(left) & set(right)) / len(union) if union else 0.0


def _status(edge_original: float | None, edge_frequency: float | None, edge_random: float | None, min_ok: bool = True) -> tuple[str, bool]:
    if not min_ok or edge_original is None or edge_frequency is None or edge_random is None:
        return "fail", False
    if edge_original > 0 and edge_random > 0 and edge_frequency >= 0:
        return "pass", True
    if edge_original > 0 and edge_random > 0 and edge_frequency >= -0.1:
        return "partial", False
    return "fail", False


def evaluate_test_records(
    split_id: str,
    train_records: list[dict[str, Any]],
    test_records: list[dict[str, Any]],
    variant: str = "frequency_raw",
    min_test_records: int = 1,
    policy: str = "always_repair",
    gate_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    prior = list(sorted(train_records, key=draw_id))
    original_top10: list[float] = []
    repaired_top10: list[float] = []
    frequency_top10: list[float] = []
    policy_top10: list[float] = []
    original_top20: list[float] = []
    repaired_top20: list[float] = []
    frequency_top20: list[float] = []
    policy_top20: list[float] = []
    activations = 0
    fallbacks = 0
    target_rows = []

    for record in sorted(test_records, key=draw_id):
        target = set(target_numbers(record))
        if not target or not prior:
            prior.append(record)
            continue
        original = _original_rank(record)
        frequency = frequency_rank(prior, variant)
        repaired = candidate_rank(record, prior, variant)
        active = is_confident(record, prior, variant, gate_config or {})
        chosen = choose_policy_rank(policy, active, original, frequency, repaired)
        activations += int(chosen == repaired)
        fallbacks += int(chosen != repaired)

        o10 = float(_hits(original, target, 10) or 0)
        r10 = float(_hits(repaired, target, 10) or 0)
        f10 = float(_hits(frequency, target, 10) or 0)
        p10 = float(_hits(chosen, target, 10) or 0)
        o20 = float(_hits(original, target, 20) or 0)
        r20 = float(_hits(repaired, target, 20) or 0)
        f20 = float(_hits(frequency, target, 20) or 0)
        p20 = float(_hits(chosen, target, 20) or 0)
        original_top10.append(o10)
        repaired_top10.append(r10)
        frequency_top10.append(f10)
        policy_top10.append(p10)
        original_top20.append(o20)
        repaired_top20.append(r20)
        frequency_top20.append(f20)
        policy_top20.append(p20)
        target_rows.append(
            {
                "target_draw": draw_id(record),
                "target_numbers": sorted(target),
                "original_top10_hits": int(o10),
                "repaired_top10_hits": int(r10),
                "frequency_top10_hits": int(f10),
                "policy_top10_hits": int(p10),
                "activation": chosen == repaired,
            }
        )
        prior.append(record)

    original10 = avg(original_top10)
    repaired10 = avg(repaired_top10)
    frequency10 = avg(frequency_top10)
    policy10 = avg(policy_top10)
    original20 = avg(original_top20)
    repaired20 = avg(repaired_top20)
    frequency20 = avg(frequency_top20)
    policy20 = avg(policy_top20)
    edge_original = round(policy10 - original10, 6) if policy10 is not None and original10 is not None else None
    edge_frequency = round(policy10 - frequency10, 6) if policy10 is not None and frequency10 is not None else None
    edge_random = round(policy10 - RANDOM_TOP10_HITS, 6) if policy10 is not None else None
    status, passed = _status(edge_original, edge_frequency, edge_random, len(policy_top10) >= min_test_records)
    draws = [draw_id(record) for record in test_records if draw_id(record)]
    return {
        "split_id": split_id,
        "variant": variant,
        "policy": policy,
        "train_records": len(train_records),
        "test_records": len(test_records),
        "records_evaluated": len(policy_top10),
        "test_start": min(draws) if draws else None,
        "test_end": max(draws) if draws else None,
        "original_top10_avg_hits": original10,
        "repaired_top10_avg_hits": repaired10,
        "frequency_top10_avg_hits": frequency10,
        "policy_top10_avg_hits": policy10,
        "random_top10_expected": RANDOM_TOP10_HITS,
        "original_top20_avg_hits": original20,
        "repaired_top20_avg_hits": repaired20,
        "frequency_top20_avg_hits": frequency20,
        "policy_top20_avg_hits": policy20,
        "random_top20_expected": RANDOM_TOP20_HITS,
        "repaired_minus_original": round(repaired10 - original10, 6) if repaired10 is not None and original10 is not None else None,
        "repaired_minus_frequency": round(repaired10 - frequency10, 6) if repaired10 is not None and frequency10 is not None else None,
        "repaired_minus_random": round(repaired10 - RANDOM_TOP10_HITS, 6) if repaired10 is not None else None,
        "policy_minus_original": edge_original,
        "policy_minus_frequency": edge_frequency,
        "policy_minus_random": edge_random,
        "split_status": status,
        "split_passed": passed,
        "activations_count": activations,
        "fallback_count": fallbacks,
        "target_rows": target_rows,
    }


def rolling_folds(records: list[dict[str, Any]], initial_train_size: int = 30, test_window_size: int = 5, step_size: int = 5) -> list[tuple[str, list[dict[str, Any]], list[dict[str, Any]]]]:
    output = []
    for start in range(initial_train_size, len(records), step_size):
        train = records[:start]
        test = records[start : start + test_window_size]
        if train and test:
            output.append((f"fold_{len(output) + 1}_test_{draw_id(test[0])}_{draw_id(test[-1])}", train, test))
    return output


def holdout_splits(records: list[dict[str, Any]]) -> list[tuple[str, list[dict[str, Any]], list[dict[str, Any]], int]]:
    def in_range(low: int, high: int) -> list[dict[str, Any]]:
        return [record for record in records if low <= draw_id(record) <= high]

    return [
        ("train_4155_4199_test_4200_4214", in_range(4155, 4199), in_range(4200, 4214), 10),
        ("train_4155_4184_test_4185_4214", in_range(4155, 4184), in_range(4185, 4214), 10),
        ("train_4155_4169_test_4170_4214", in_range(4155, 4169), in_range(4170, 4214), 10),
    ]


def is_confident(record: dict[str, Any], prior: list[dict[str, Any]], variant: str, config: dict[str, Any]) -> bool:
    min_history = int(config.get("min_history_records", 0))
    if len(prior) < min_history:
        return False
    original_top6 = set(_original_rank(record)[:6])
    freq_top10 = set(frequency_rank(prior, variant)[:10])
    overlap = len(original_top6 & freq_top10)
    if overlap < int(config.get("min_top6_frequency_overlap", 0)):
        return False
    if overlap > int(config.get("max_top6_frequency_overlap", 6)):
        return False
    stability = frequency_stability(prior, variant)
    min_stability = {"low": 0.2, "medium": 0.4, "high": 0.6}.get(str(config.get("min_frequency_stability", "low")), 0.2)
    if stability < min_stability:
        return False
    recent_threshold = config.get("min_recent_edge_proxy")
    if recent_threshold is not None and recent_edge_proxy(prior, variant) < float(recent_threshold):
        return False
    return True


def frequency_stability(prior: list[dict[str, Any]], variant: str) -> float:
    if len(prior) < 10:
        return 0.0
    previous = frequency_rank(prior[:-5], variant)[:10]
    current = frequency_rank(prior, variant)[:10]
    return jaccard(previous, current)


def recent_edge_proxy(prior: list[dict[str, Any]], variant: str, window: int = 5) -> float:
    if len(prior) <= window:
        return 0.0
    train = prior[:-window]
    test = prior[-window:]
    row = evaluate_test_records("recent_edge_proxy", train, test, variant, min_test_records=1)
    value = row.get("repaired_minus_frequency")
    return float(value) if value is not None else 0.0


def choose_policy_rank(policy: str, active: bool, original: list[int], frequency: list[int], repaired: list[int]) -> list[int]:
    if policy == "always_repair":
        return repaired
    if policy == "repair_or_original":
        return repaired if active else original
    if policy == "repair_or_frequency":
        return repaired if active else frequency
    if policy == "repair_only_if_confident_else_original":
        return repaired if active else original
    if policy == "repair_only_if_confident_else_frequency":
        return repaired if active else frequency
    if policy == "repair_only_if_confident_else_best_baseline":
        return repaired if active else frequency
    return repaired if active else original
