# -*- coding: utf-8 -*-
"""Controlled post-ranking layer for review-only V4.4 diagnostics."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from v4_benchmark_hardening import MAX_NUMBER, load_replay_records, parse_int, target_numbers


VERSION = "V4.4-controlled-post-ranking-layer"
CANDIDATE_VARIANT = "top6_preserved_plus_frequency_no_duplicates"
SMOOTHING_VARIANT = "frequency_window_15"
POLICY = "always_repair__min_history_15"
FREQUENCY_CONTEXT = "replay_memory_recent_window"
DEFAULT_WINDOW_SIZE = 15


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: str | Path) -> tuple[dict[str, Any] | None, str | None]:
    json_path = Path(path)
    if not json_path.exists():
        return None, f"missing file: {json_path}"
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return None, f"invalid json in {json_path}: {exc}"
    if not isinstance(data, dict):
        return None, f"expected object json in {json_path}"
    return data, None


def _valid_number(value: Any) -> int | None:
    number = parse_int(value)
    if number is None or not (1 <= number <= MAX_NUMBER):
        return None
    return number


def _unique(numbers: list[int]) -> list[int]:
    seen: set[int] = set()
    output: list[int] = []
    for number in numbers:
        if number not in seen and 1 <= number <= MAX_NUMBER:
            seen.add(number)
            output.append(number)
    return output


def derive_original_ranking(results: dict[str, Any]) -> tuple[list[int], str, list[str]]:
    """Derive the current official ranking without mutating official scores."""
    warnings: list[str] = []
    scores = results.get("number_scores")
    if isinstance(scores, dict):
        rows: list[tuple[int, float]] = []
        for raw_number, raw_score in scores.items():
            number = _valid_number(raw_number)
            if number is None:
                continue
            try:
                score = float(raw_score)
            except (TypeError, ValueError):
                continue
            rows.append((number, score))
        ranking = [number for number, _ in sorted(rows, key=lambda item: (-item[1], item[0]))]
        if len(ranking) >= 6:
            return ranking, "number_scores", warnings
        warnings.append("number_scores exists but did not provide at least six valid numbers.")

    seed = results.get("manual_suggestion_seed")
    if isinstance(seed, list):
        rows = []
        for row in seed:
            if not isinstance(row, dict):
                continue
            number = _valid_number(row.get("number"))
            if number is None:
                continue
            score = 0.0
            for key in ("score", "score_percent", "net_score", "confidence"):
                try:
                    score = float(row.get(key))
                    break
                except (TypeError, ValueError):
                    continue
            rows.append((number, score))
        ranking = _unique([number for number, _ in sorted(rows, key=lambda item: (-item[1], item[0]))])
        if len(ranking) >= 6:
            warnings.append("Original ranking derived from manual_suggestion_seed fallback.")
            return ranking, "manual_suggestion_seed", warnings

    for pool_name in ("top_combinations", "generator_pool"):
        pool = results.get(pool_name)
        if not isinstance(pool, list):
            continue
        weights: Counter[int] = Counter()
        for index, row in enumerate(pool):
            raw_numbers = row.get("numbers") if isinstance(row, dict) else row
            if not isinstance(raw_numbers, list):
                continue
            combo = _unique([number for value in raw_numbers if (number := _valid_number(value)) is not None])
            if len(combo) != 6:
                continue
            weight = max(len(pool) - index, 1)
            for number in combo:
                weights[number] += weight
        ranking = [number for number, _ in sorted(weights.items(), key=lambda item: (-item[1], item[0]))]
        if len(ranking) >= 6:
            warnings.append(f"Original ranking derived from {pool_name} fallback.")
            return ranking, pool_name, warnings

    return [], "unavailable", ["No reliable original ranking source found in resultados.json."]


def validation_allows_controlled_layer(summary: dict[str, Any] | None) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if not summary:
        return False, ["PR #29 full validation summary is missing or invalid."]
    required = {
        "candidate_status": summary.get("candidate_status") == "ready_for_controlled_layer",
        "production_ready": summary.get("production_ready") is False,
        "prior_should_remain_blocked": summary.get("prior_should_remain_blocked") is True,
        "future_controlled_layer_candidate": summary.get("future_controlled_layer_candidate") is True,
    }
    for key, passed in required.items():
        if not passed:
            reasons.append(f"PR #29 gate failed: {key}.")
    return not reasons, reasons


def recent_frequency_rank(records: list[dict[str, Any]], window_size: int = DEFAULT_WINDOW_SIZE) -> list[int]:
    recent = records[-window_size:]
    counts: Counter[int] = Counter()
    latest_seen: dict[int, int] = {}
    for index, record in enumerate(recent):
        for number in target_numbers(record):
            counts[number] += 1
            latest_seen[number] = index
    return [
        number
        for number, _ in sorted(
            counts.items(),
            key=lambda item: (-item[1], -latest_seen.get(item[0], -1), item[0]),
        )
    ]


def _controlled_rank(original: list[int], frequency: list[int]) -> list[int]:
    return _unique(original[:6] + [number for number in frequency if number not in set(original[:6])])


def _diff(original: list[int], controlled: list[int]) -> dict[str, Any]:
    original_top10 = set(original[:10])
    controlled_top10 = set(controlled[:10])
    original_top20 = set(original[:20])
    controlled_top20 = set(controlled[:20])
    return {
        "overlap_top10": len(original_top10 & controlled_top10),
        "overlap_top20": len(original_top20 & controlled_top20),
        "added_numbers_top20": sorted(controlled_top20 - original_top20),
        "removed_numbers_top20": sorted(original_top20 - controlled_top20),
        "preserved_top6": controlled[:6] == original[:6] if len(controlled) >= 6 else False,
    }


def build_controlled_layer(
    input_path: str | Path = "resultados.json",
    replay_memory_path: str | Path = "v4_replay_memory.json",
    validation_summary_path: str | Path = "v4_post_ranking_full_validation_summary.json",
    decision_record_path: str | Path = "v4_post_ranking_candidate_decision_record.json",
    window_size: int = DEFAULT_WINDOW_SIZE,
    top_n: int = 20,
) -> dict[str, Any]:
    warnings: list[str] = []
    risk_flags: list[str] = []
    results, results_error = load_json(input_path)
    validation_summary, validation_error = load_json(validation_summary_path)
    decision_record, decision_error = load_json(decision_record_path)
    if results_error:
        warnings.append(results_error)
    if validation_error:
        warnings.append(validation_error)
    if decision_error:
        warnings.append(decision_error)
    allowed, gate_reasons = validation_allows_controlled_layer(validation_summary)
    warnings.extend(gate_reasons)

    original_ranking: list[int] = []
    ranking_source = "unavailable"
    if results:
        original_ranking, ranking_source, ranking_warnings = derive_original_ranking(results)
        warnings.extend(ranking_warnings)
    if not original_ranking:
        warnings.append("Controlled layer blocked because official ranking could not be derived.")

    records, replay_state = load_replay_records(replay_memory_path)
    frequency_rank = recent_frequency_rank(records, window_size) if records else []
    if len(records) < window_size:
        warnings.append(f"Insufficient replay records for frequency_window_{window_size}.")
    if not frequency_rank:
        warnings.append("No observed numbers available from replay memory recent window.")

    controlled_rank = _controlled_rank(original_ranking, frequency_rank) if original_ranking else []
    if controlled_rank and len(controlled_rank) < top_n:
        warnings.append("Controlled ranking has fewer than requested top_n numbers because unseen numbers were not invented.")

    status = "ready"
    if not allowed or not original_ranking:
        status = "blocked"
    elif len(records) < window_size or len(controlled_rank) < min(top_n, 20):
        status = "insufficient_data"

    production_ready = False
    prior_should_remain_blocked = True
    candidate_variant = CANDIDATE_VARIANT
    smoothing_variant = SMOOTHING_VARIANT
    policy = POLICY
    if validation_summary:
        candidate_variant = str(validation_summary.get("candidate_variant") or candidate_variant)
        smoothing_variant = str(validation_summary.get("best_smoothing_variant") or smoothing_variant)
        policy = str(validation_summary.get("best_policy") or policy)
        if validation_summary.get("overfit_risk") in {"medium", "high"}:
            risk_flags.append(f"overfit_risk_{validation_summary.get('overfit_risk')}")
    if decision_record and decision_record.get("decision") != "ready_for_controlled_layer":
        risk_flags.append("decision_record_not_ready_for_controlled_layer")

    return {
        "version": VERSION,
        "generated_at": utc_now(),
        "mode": "controlled_experiment",
        "source_files": {
            "official_results": str(input_path),
            "replay_memory": str(replay_memory_path),
            "full_validation_summary": str(validation_summary_path),
            "candidate_decision_record": str(decision_record_path),
        },
        "candidate_variant": candidate_variant,
        "smoothing_variant": smoothing_variant,
        "policy": policy,
        "status": status,
        "production_ready": production_ready,
        "prior_should_remain_blocked": prior_should_remain_blocked,
        "official_results_untouched": True,
        "frequency_context": FREQUENCY_CONTEXT,
        "frequency_window_size": window_size,
        "frequency_is_truth_source": False,
        "ranking_source": ranking_source,
        "replay_records_available": len(records),
        "replay_input_state": replay_state,
        "original_top_numbers": original_ranking[:top_n],
        "top6_preserved": original_ranking[:6],
        "frequency_window_15_rank": frequency_rank,
        "controlled_top20_numbers": controlled_rank[:20],
        "controlled_top30_numbers": controlled_rank[:30],
        "controlled_top40_numbers": controlled_rank[:40],
        "diff_vs_original": _diff(original_ranking, controlled_rank) if original_ranking and controlled_rank else {
            "overlap_top10": 0,
            "overlap_top20": 0,
            "added_numbers_top20": [],
            "removed_numbers_top20": [],
            "preserved_top6": False,
        },
        "risk_flags": risk_flags,
        "warnings": warnings,
        "interpretation": "Controlled post-ranking view only. Review-only. Does not replace official V4.2 output. Not a probability of winning.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build controlled post-ranking layer output.")
    parser.add_argument("--input", default="resultados.json")
    parser.add_argument("--replay-memory", default="v4_replay_memory.json")
    parser.add_argument("--validation-summary", default="v4_post_ranking_full_validation_summary.json")
    parser.add_argument("--decision-record", default="v4_post_ranking_candidate_decision_record.json")
    parser.add_argument("--window-size", type=int, default=DEFAULT_WINDOW_SIZE)
    parser.add_argument("--top-n", type=int, default=20)
    parser.add_argument("--output", default="v4_post_ranking_controlled_layer_output.json")
    args = parser.parse_args()

    report = build_controlled_layer(
        input_path=args.input,
        replay_memory_path=args.replay_memory,
        validation_summary_path=args.validation_summary,
        decision_record_path=args.decision_record,
        window_size=args.window_size,
        top_n=args.top_n,
    )
    Path(args.output).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[controlled-layer] wrote {args.output} status={report.get('status')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
