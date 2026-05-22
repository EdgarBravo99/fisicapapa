# -*- coding: utf-8 -*-
"""Diagnostic confidence-gate and fallback policy experiments."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from v4_benchmark_hardening import utc_now
from v4_post_ranking_validation_common import avg, evaluate_test_records, load_sorted_replay_records, rolling_folds

VERSION = "V4.4-post-ranking-confidence-gate-experiment"
POLICIES = (
    "always_repair",
    "repair_or_original",
    "repair_or_frequency",
    "repair_only_if_confident_else_original",
    "repair_only_if_confident_else_frequency",
    "repair_only_if_confident_else_best_baseline",
)


def _load(path: str | Path) -> dict[str, Any] | None:
    file_path = Path(path)
    if not file_path.exists():
        return None
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _best_smoothing(path: str | Path) -> str:
    report = _load(path) or {}
    return str((report.get("best_smoothing_variant") or {}).get("name") or "frequency_raw")


def _gate_configs() -> list[tuple[str, dict[str, Any]]]:
    configs: list[tuple[str, dict[str, Any]]] = []
    for value in (15, 30, 45):
        configs.append((f"min_history_{value}", {"min_history_records": value, "min_frequency_stability": "low"}))
    for value in (0, 1, 2):
        configs.append((f"min_overlap_{value}", {"min_history_records": 30, "min_top6_frequency_overlap": value, "min_frequency_stability": "low"}))
    for value in (4, 5, 6):
        configs.append((f"max_overlap_{value}", {"min_history_records": 30, "max_top6_frequency_overlap": value, "min_frequency_stability": "low"}))
    for value in ("low", "medium", "high"):
        configs.append((f"stability_{value}", {"min_history_records": 30, "min_frequency_stability": value}))
    configs.append(("recent_edge_gt_0", {"min_history_records": 30, "min_frequency_stability": "low", "min_recent_edge_proxy": 0.000001}))
    configs.append(("recent_edge_gte_neg_0_1", {"min_history_records": 30, "min_frequency_stability": "low", "min_recent_edge_proxy": -0.1}))
    return configs


def _pass_rate(rows: list[dict[str, Any]]) -> float:
    return round(sum(1 for row in rows if row.get("split_status") == "pass") / len(rows), 6) if rows else 0.0


def _policy_status(rolling_pass_rate: float, edge_original: float | None, edge_frequency: float | None, edge_random: float | None, worst_frequency: float | None) -> str:
    if edge_original is None or edge_frequency is None or edge_random is None:
        return "fail"
    if rolling_pass_rate >= 0.5 and edge_original > 0 and edge_random > 0 and edge_frequency >= 0 and (worst_frequency is None or worst_frequency >= -0.75):
        return "pass"
    if edge_original > 0 and edge_random > 0 and edge_frequency >= -0.1:
        return "partial"
    return "fail"


def _summarize_policy(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total_records = sum(int(row.get("records_evaluated") or 0) for row in rows)
    activations = sum(int(row.get("activations_count") or 0) for row in rows)
    fallbacks = sum(int(row.get("fallback_count") or 0) for row in rows)
    edge_original = avg([float(row["policy_minus_original"]) for row in rows if row.get("policy_minus_original") is not None])
    edge_frequency = avg([float(row["policy_minus_frequency"]) for row in rows if row.get("policy_minus_frequency") is not None])
    edge_random = avg([float(row["policy_minus_random"]) for row in rows if row.get("policy_minus_random") is not None])
    worst_frequency = min((float(row["policy_minus_frequency"]) for row in rows if row.get("policy_minus_frequency") is not None), default=None)
    worst_random = min((float(row["policy_minus_random"]) for row in rows if row.get("policy_minus_random") is not None), default=None)
    rolling_pass_rate = _pass_rate(rows)
    return {
        "activations_count": activations,
        "activation_rate": round(activations / total_records, 6) if total_records else 0.0,
        "fallback_count": fallbacks,
        "rolling_pass_rate": rolling_pass_rate,
        "folds_failed": sum(1 for row in rows if row.get("split_status") == "fail"),
        "avg_edge_vs_original": edge_original,
        "avg_edge_vs_frequency": edge_frequency,
        "avg_edge_vs_random": edge_random,
        "worst_fold_delta_vs_frequency": round(worst_frequency, 6) if worst_frequency is not None else None,
        "worst_fold_delta_vs_random": round(worst_random, 6) if worst_random is not None else None,
        "stability_score": rolling_pass_rate,
        "policy_status": _policy_status(rolling_pass_rate, edge_original, edge_frequency, edge_random, worst_frequency),
    }


def _compact_fold(row: dict[str, Any]) -> dict[str, Any]:
    keep = (
        "split_id",
        "variant",
        "policy",
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
        "activations_count",
        "fallback_count",
    )
    return {key: row.get(key) for key in keep}


def _best_policy(policies: dict[str, dict[str, Any]]) -> dict[str, str | None]:
    if not policies:
        return {"name": None, "reason": "no policies evaluated"}
    status_score = {"pass": 2, "partial": 1, "fail": 0}

    def score(item: tuple[str, dict[str, Any]]) -> tuple[int, float, float, float, float]:
        _, row = item
        return (
            status_score.get(str(row.get("policy_status")), 0),
            float(row.get("rolling_pass_rate") or 0.0),
            float(row.get("avg_edge_vs_frequency") or -999.0),
            float(row.get("avg_edge_vs_random") or -999.0),
            float(row.get("worst_fold_delta_vs_frequency") or -999.0),
        )

    name, row = max(policies.items(), key=score)
    return {"name": name, "reason": f"best diagnostic policy by status/pass-rate/edge; status={row.get('policy_status')}"}


def build_confidence_gate_experiment(
    replay_memory: str = "v4_replay_memory.json",
    smoothing_path: str = "v4_post_ranking_smoothing_stress_test.json",
) -> dict[str, Any]:
    records, input_state = load_sorted_replay_records(replay_memory)
    variant = _best_smoothing(smoothing_path)
    folds = rolling_folds(records)
    policies: dict[str, dict[str, Any]] = {}
    for config_name, config in _gate_configs():
        for policy in POLICIES:
            policy_name = f"{policy}__{config_name}"
            rows = [
                evaluate_test_records(fold_id, train, test, variant, min_test_records=5, policy=policy, gate_config=config)
                for fold_id, train, test in folds
            ]
            policies[policy_name] = {
                "smoothing_variant": variant,
                "gate_config": config,
                **_summarize_policy(rows),
                "_folds_for_selection": [_compact_fold(row) for row in rows],
            }
    best = _best_policy(policies)
    best_row = policies.get(str(best.get("name")), {})
    raw = policies.get("always_repair__min_history_30", {})
    best_policy_folds = best_row.pop("_folds_for_selection", []) if best_row else []
    for row in policies.values():
        row.pop("_folds_for_selection", None)
    return {
        "version": VERSION,
        "generated_at": utc_now(),
        "mode": "diagnostic_only",
        "input_source": replay_memory,
        "input_state": input_state,
        "smoothing_variant_used": variant,
        "policies": policies,
        "best_policy": best,
        "best_policy_folds": best_policy_folds,
        "summary": {
            "confidence_gate_reduces_overfit": bool(
                best_row
                and float(best_row.get("rolling_pass_rate") or 0.0) >= float(raw.get("rolling_pass_rate") or 0.0)
                and str(best_row.get("policy_status")) in {"pass", "partial"}
            ),
            "best_rolling_pass_rate": best_row.get("rolling_pass_rate"),
            "recommendation": "diagnostic_only",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run post-ranking confidence gate experiment.")
    parser.add_argument("--replay-memory", default="v4_replay_memory.json")
    parser.add_argument("--smoothing", default="v4_post_ranking_smoothing_stress_test.json")
    parser.add_argument("--output", default="v4_post_ranking_confidence_gate_experiment.json")
    args = parser.parse_args()
    report = build_confidence_gate_experiment(args.replay_memory, args.smoothing)
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {args.output}; best={report['best_policy']['name']}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
