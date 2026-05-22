# -*- coding: utf-8 -*-
"""Conservative gate for post-ranking holdout validation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from v4_benchmark_hardening import utc_now
from v4_post_ranking_holdout_experiment import CANDIDATE_VARIANT

VERSION = "V4.4-post-ranking-holdout-summary"


def _load(path: str | Path) -> dict[str, Any] | None:
    file_path = Path(path)
    if not file_path.exists():
        return None
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _rate(passed: int, total: int) -> float:
    return round(passed / total, 6) if total else 0.0


def _quality_rank(value: str | None) -> int:
    return {"unknown": 0, "weak": 1, "moderate": 2, "strong": 3}.get(str(value or "unknown"), 0)


def _avg(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 6) if values else None


def _overfit_risk(holdout_quality: str, rolling_quality: str, edge_original: float | None, edge_frequency: float | None, edge_random: float | None) -> str:
    if _quality_rank(holdout_quality) < 2 or _quality_rank(rolling_quality) < 2:
        return "high"
    if edge_original is None or edge_random is None or edge_frequency is None:
        return "high"
    if edge_original <= 0 or edge_random <= 0:
        return "high"
    if edge_frequency < 0:
        return "medium"
    return "low"


def build_holdout_summary(
    holdout_path: str = "v4_post_ranking_holdout_experiment.json",
    rolling_path: str = "v4_post_ranking_rolling_validation.json",
    repair_summary_path: str = "v4_ranking_repair_summary.json",
    signal_path: str = "v4_signal_decomposition_summary.json",
    benchmark_path: str = "v4_benchmark_summary.json",
) -> dict[str, Any]:
    holdout = _load(holdout_path) or {}
    rolling = _load(rolling_path) or {}
    repair = _load(repair_summary_path) or {}
    signal = _load(signal_path) or {}
    benchmark = _load(benchmark_path) or {}

    holdout_summary = holdout.get("summary") if isinstance(holdout.get("summary"), dict) else {}
    rolling_summary = rolling.get("summary") if isinstance(rolling.get("summary"), dict) else {}
    holdout_quality = str(holdout_summary.get("holdout_signal_quality") or "unknown")
    rolling_quality = str(rolling_summary.get("rolling_signal_quality") or "unknown")
    holdout_total = int(holdout_summary.get("splits_total") or 0)
    rolling_total = int(rolling_summary.get("folds_total") or 0)
    holdout_pass_rate = _rate(int(holdout_summary.get("splits_passed") or 0), holdout_total)
    rolling_pass_rate = _rate(int(rolling_summary.get("folds_passed") or 0), rolling_total)
    avg_edge_vs_original = _avg(
        [
            float(value)
            for value in (holdout_summary.get("avg_edge_vs_original"), rolling_summary.get("avg_repaired_minus_original"))
            if value is not None
        ]
    )
    avg_edge_vs_frequency = _avg(
        [
            float(value)
            for value in (holdout_summary.get("avg_edge_vs_frequency"), rolling_summary.get("avg_repaired_minus_frequency"))
            if value is not None
        ]
    )
    avg_edge_vs_random = _avg(
        [
            float(value)
            for value in (holdout_summary.get("avg_edge_vs_random"), rolling_summary.get("avg_repaired_minus_random"))
            if value is not None
        ]
    )
    overfit_risk = _overfit_risk(holdout_quality, rolling_quality, avg_edge_vs_original, avg_edge_vs_frequency, avg_edge_vs_random)
    future_candidate = (
        _quality_rank(holdout_quality) >= 2
        and _quality_rank(rolling_quality) >= 2
        and avg_edge_vs_original is not None
        and avg_edge_vs_random is not None
        and avg_edge_vs_frequency is not None
        and avg_edge_vs_original > 0
        and avg_edge_vs_random > 0
        and avg_edge_vs_frequency >= 0
        and overfit_risk != "high"
    )
    reasons = []
    if not future_candidate:
        reasons.append("Candidate is not ready for a future experimental layer under holdout gates.")
    if overfit_risk == "high":
        reasons.append("Overfit risk remains high or signal quality is below moderate.")
    if signal.get("prior_should_remain_blocked") is True:
        reasons.append("Signal decomposition still blocks prior.")
    if benchmark.get("recommendation") == "diagnostic_only":
        reasons.append("Benchmark summary remains diagnostic_only.")
    if not reasons:
        reasons.append("Candidate may deserve a future controlled experiment, but production remains blocked.")
    return {
        "version": VERSION,
        "generated_at": utc_now(),
        "input_files": {
            "holdout_experiment": holdout_path,
            "rolling_validation": rolling_path,
            "ranking_repair_summary": repair_summary_path,
            "signal_decomposition_summary": signal_path,
            "benchmark_summary": benchmark_path,
        },
        "candidate_variant": holdout.get("candidate_variant") or repair.get("best_repair_variant") or CANDIDATE_VARIANT,
        "recommendation": "diagnostic_only",
        "holdout_signal_quality": holdout_quality,
        "rolling_signal_quality": rolling_quality,
        "holdout_pass_rate": holdout_pass_rate,
        "rolling_pass_rate": rolling_pass_rate,
        "avg_edge_vs_original": avg_edge_vs_original,
        "avg_edge_vs_frequency": avg_edge_vs_frequency,
        "avg_edge_vs_random": avg_edge_vs_random,
        "overfit_risk": overfit_risk,
        "future_experimental_layer_candidate": future_candidate,
        "production_ready": False,
        "prior_should_remain_blocked": True,
        "reason": " ".join(reasons),
        "required_next_evidence": [
            "validate on future unseen draws",
            "run controlled post-ranking layer simulation",
            "compare against frequency and random without using future",
            "keep the candidate layer separate from official scores until future validation passes",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build post-ranking holdout summary gate.")
    parser.add_argument("--holdout", default="v4_post_ranking_holdout_experiment.json")
    parser.add_argument("--rolling", default="v4_post_ranking_rolling_validation.json")
    parser.add_argument("--repair-summary", default="v4_ranking_repair_summary.json")
    parser.add_argument("--signal", default="v4_signal_decomposition_summary.json")
    parser.add_argument("--benchmark", default="v4_benchmark_summary.json")
    parser.add_argument("--output", default="v4_post_ranking_holdout_summary.json")
    args = parser.parse_args()
    report = build_holdout_summary(args.holdout, args.rolling, args.repair_summary, args.signal, args.benchmark)
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {args.output}; future_candidate={report['future_experimental_layer_candidate']}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
