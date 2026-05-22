# -*- coding: utf-8 -*-
"""Final diagnostic decision gate for the post-ranking candidate hypothesis."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from v4_benchmark_hardening import utc_now
from v4_post_ranking_validation_common import CANDIDATE_VARIANT

VERSION = "V4.4-post-ranking-full-validation-summary"
DECISION_VERSION = "V4.4-post-ranking-candidate-decision-record"


def _load(path: str | Path) -> dict[str, Any] | None:
    file_path = Path(path)
    if not file_path.exists():
        return None
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _edge(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _decision(
    rolling_pass_rate: float,
    edge_original: float | None,
    edge_frequency: float | None,
    edge_random: float | None,
    worst_frequency: float | None,
    overfit_risk: str,
    best_policy: str | None,
) -> tuple[str, bool, str, str]:
    if (
        rolling_pass_rate >= 0.5
        and edge_original is not None
        and edge_random is not None
        and edge_frequency is not None
        and edge_original > 0
        and edge_random > 0
        and edge_frequency >= -0.05
        and (worst_frequency is None or worst_frequency > -0.75)
        and overfit_risk != "high"
        and best_policy
    ):
        return (
            "ready_for_controlled_layer",
            True,
            "PR #30 controlled implementation",
            "Policy clears diagnostic gates, but production remains blocked until controlled implementation and future validation.",
        )
    if edge_original is not None and edge_random is not None and edge_original > 0 and edge_random > 0:
        return (
            "keep_candidate",
            False,
            "continue validation before implementation",
            "Candidate improves original/random but is not stable enough against frequency or overfit gates.",
        )
    return (
        "reject",
        False,
        "stop and revisit signal generation",
        "Candidate does not provide enough stable edge to justify implementation work.",
    )


def build_full_summary(
    smoothing_path: str = "v4_post_ranking_smoothing_stress_test.json",
    confidence_path: str = "v4_post_ranking_confidence_gate_experiment.json",
    worst_path: str = "v4_post_ranking_worst_fold_analysis.json",
    holdout_path: str = "v4_post_ranking_holdout_summary.json",
    repair_path: str = "v4_ranking_repair_summary.json",
    benchmark_path: str = "v4_benchmark_summary.json",
    signal_path: str = "v4_signal_decomposition_summary.json",
) -> dict[str, Any]:
    smoothing = _load(smoothing_path) or {}
    confidence = _load(confidence_path) or {}
    worst = _load(worst_path) or {}
    holdout = _load(holdout_path) or {}
    repair = _load(repair_path) or {}
    benchmark = _load(benchmark_path) or {}
    signal = _load(signal_path) or {}
    best_smoothing = (smoothing.get("best_smoothing_variant") or {}).get("name")
    best_policy = (confidence.get("best_policy") or {}).get("name")
    policy_row = (confidence.get("policies") or {}).get(best_policy or "", {})
    smoothing_row = (smoothing.get("variants") or {}).get(best_smoothing or "", {})
    rolling_pass_rate = _edge(policy_row.get("rolling_pass_rate"))
    if rolling_pass_rate is None:
        rolling_pass_rate = _edge((smoothing.get("summary") or {}).get("best_rolling_pass_rate")) or 0.0
    holdout_pass_rate = _edge(holdout.get("holdout_pass_rate")) or _edge((holdout.get("summary") or {}).get("holdout_pass_rate")) or _edge(smoothing_row.get("holdout_pass_rate")) or 0.0
    edge_original = _edge(policy_row.get("avg_edge_vs_original")) or _edge(smoothing_row.get("avg_edge_vs_original"))
    edge_frequency = _edge(policy_row.get("avg_edge_vs_frequency")) or _edge(smoothing_row.get("avg_edge_vs_frequency"))
    edge_random = _edge(policy_row.get("avg_edge_vs_random")) or _edge(smoothing_row.get("avg_edge_vs_random"))
    worst_frequency = _edge(policy_row.get("worst_fold_delta_vs_frequency")) or _edge(smoothing_row.get("worst_fold_delta_vs_frequency"))
    worst_random = _edge(policy_row.get("worst_fold_delta_vs_random")) or _edge(smoothing_row.get("worst_fold_delta_vs_random"))
    overfit_risk = "high"
    if str(policy_row.get("policy_status")) == "pass" and rolling_pass_rate >= 0.5 and edge_frequency is not None and edge_frequency >= 0:
        overfit_risk = "medium" if worst_frequency is not None and worst_frequency < -0.35 else "low"
    elif str(policy_row.get("policy_status")) == "partial":
        overfit_risk = "medium"
    candidate_status, future_candidate, next_pr, reason = _decision(
        rolling_pass_rate,
        edge_original,
        edge_frequency,
        edge_random,
        worst_frequency,
        overfit_risk,
        str(best_policy) if best_policy else None,
    )
    if signal.get("prior_should_remain_blocked") is True:
        reason = f"{reason} Signal decomposition still blocks prior."
    if benchmark.get("recommendation") == "diagnostic_only":
        reason = f"{reason} Benchmark remains diagnostic_only."
    return {
        "version": VERSION,
        "generated_at": utc_now(),
        "mode": "diagnostic_only",
        "input_files": {
            "smoothing": smoothing_path,
            "confidence_gate": confidence_path,
            "worst_fold": worst_path,
            "holdout_summary": holdout_path,
            "ranking_repair_summary": repair_path,
            "benchmark_summary": benchmark_path,
            "signal_decomposition": signal_path,
        },
        "candidate_status": candidate_status,
        "candidate_variant": CANDIDATE_VARIANT,
        "best_smoothing_variant": best_smoothing,
        "best_policy": best_policy,
        "rolling_pass_rate": rolling_pass_rate,
        "holdout_pass_rate": holdout_pass_rate,
        "avg_edge_vs_original": edge_original,
        "avg_edge_vs_frequency": edge_frequency,
        "avg_edge_vs_random": edge_random,
        "worst_fold_delta_vs_frequency": worst_frequency,
        "worst_fold_delta_vs_random": worst_random,
        "main_failure_pattern": (worst.get("summary") or {}).get("main_failure_pattern"),
        "overfit_risk": overfit_risk,
        "future_controlled_layer_candidate": future_candidate,
        "production_ready": False,
        "prior_should_remain_blocked": True,
        "recommendation": "diagnostic_only",
        "recommended_next_pr": next_pr,
        "reason": reason,
        "required_next_evidence": [
            "future unseen validation",
            "controlled implementation only if explicitly approved",
            "no score mutation or replay prior activation",
            "continued comparison against frequency and random without future leakage",
        ],
    }


def decision_record_from_summary(summary: dict[str, Any]) -> dict[str, Any]:
    decision = summary.get("candidate_status") or "keep_candidate"
    return {
        "version": DECISION_VERSION,
        "generated_at": utc_now(),
        "candidate": CANDIDATE_VARIANT,
        "decision": decision,
        "why": [
            summary.get("reason") or "diagnostic decision generated from full validation pack",
            f"best_smoothing_variant={summary.get('best_smoothing_variant')}",
            f"best_policy={summary.get('best_policy')}",
            f"rolling_pass_rate={summary.get('rolling_pass_rate')}",
            f"overfit_risk={summary.get('overfit_risk')}",
        ],
        "why_not_production": [
            "production_ready is false",
            "prior_should_remain_blocked is true",
            "future unseen validation still required",
        ],
        "allowed_next_steps": [
            summary.get("recommended_next_pr") or "continue diagnostic validation",
            "review worst-fold failure patterns",
            "keep candidate separate from official scoring",
        ],
        "forbidden_next_steps": [
            "do not enable replay prior",
            "do not modify Monte Carlo",
            "do not modify official scores",
            "do not replace resultados.json",
        ],
        "recommendation": "diagnostic_only",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build post-ranking full validation summary.")
    parser.add_argument("--smoothing", default="v4_post_ranking_smoothing_stress_test.json")
    parser.add_argument("--confidence", default="v4_post_ranking_confidence_gate_experiment.json")
    parser.add_argument("--worst-fold", default="v4_post_ranking_worst_fold_analysis.json")
    parser.add_argument("--holdout", default="v4_post_ranking_holdout_summary.json")
    parser.add_argument("--repair-summary", default="v4_ranking_repair_summary.json")
    parser.add_argument("--benchmark", default="v4_benchmark_summary.json")
    parser.add_argument("--signal", default="v4_signal_decomposition_summary.json")
    parser.add_argument("--output", default="v4_post_ranking_full_validation_summary.json")
    parser.add_argument("--decision-record", default="v4_post_ranking_candidate_decision_record.json")
    args = parser.parse_args()
    report = build_full_summary(args.smoothing, args.confidence, args.worst_fold, args.holdout, args.repair_summary, args.benchmark, args.signal)
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    Path(args.decision_record).write_text(json.dumps(decision_record_from_summary(report), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {args.output}; status={report['candidate_status']}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
