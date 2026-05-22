# -*- coding: utf-8 -*-
"""Combine benchmark diagnostics into a conservative replay evidence gate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from v4_benchmark_hardening import utc_now

VERSION = "V4.4-benchmark-summary-gate"


def _load(path: str | Path) -> dict[str, Any] | None:
    file_path = Path(path)
    if not file_path.exists():
        return None
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _number(data: dict[str, Any] | None, key: str) -> float | None:
    if not isinstance(data, dict):
        return None
    try:
        value = data.get(key)
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _benchmark_quality(hardening: dict[str, Any] | None, stability: dict[str, Any] | None) -> tuple[str, str]:
    if not hardening:
        return "unknown", "No benchmark hardening report available."
    records = int(hardening.get("records_count") or 0)
    if records < 30:
        return "unknown", "Fewer than 30 replay records."
    random_edge = _number(hardening, "cruncher_minus_random")
    frequency_edge = _number(hardening, "cruncher_minus_frequency")
    recency_edge = _number(hardening, "cruncher_minus_recency")
    edges = [value for value in (random_edge, frequency_edge, recency_edge) if value is not None]
    if not edges:
        return "unknown", "No comparable baseline edges available."
    stable = (stability or {}).get("stability")
    if any(value <= 0 for value in edges):
        return "weak", "Cruncher does not beat every available baseline."
    if stable not in ("moderate", "stable"):
        return "weak", "Baseline edge is positive but not stable."
    if min(edges) >= 0.25 and stable == "stable":
        return "strong", "Cruncher beats available baselines with stable margin."
    return "moderate", "Cruncher beats available baselines, but evidence remains diagnostic."


def _diversification_value(eval_report: dict[str, Any] | None) -> str:
    if not eval_report:
        return "unknown"
    gain = _number(eval_report, "coverage_gain") or 0.0
    diff = _number(eval_report, "diversified_minus_original")
    if gain <= 0:
        return "low"
    if diff is None:
        return "useful_for_coverage_only"
    if diff > 0:
        return "useful_for_hits_and_coverage"
    return "useful_for_coverage_only"


def build_summary(
    hardening_path: str = "v4_benchmark_hardening.json",
    calibration_path: str = "v4_calibration_diagnostics.json",
    diversified_eval_path: str = "v4_diversified_vs_original_eval.json",
    stability_path: str = "v4_benchmark_stability.json",
    replay_qualification_path: str = "v4_replay_qualification.json",
) -> dict[str, Any]:
    hardening = _load(hardening_path)
    calibration = _load(calibration_path)
    diversified_eval = _load(diversified_eval_path)
    stability = _load(stability_path)
    qualification = _load(replay_qualification_path)
    benchmark_quality, benchmark_reason = _benchmark_quality(hardening, stability)
    ranking_quality = (calibration or {}).get("ranking_signal_quality") or "unknown"
    stability_value = (stability or {}).get("stability") or "unknown"
    random_edge = _number(hardening, "cruncher_minus_random")
    frequency_edge = _number(hardening, "cruncher_minus_frequency")
    recency_edge = _number(hardening, "cruncher_minus_recency")
    edge_values = [value for value in (random_edge, frequency_edge, recency_edge) if value is not None]
    future_eligible = (
        benchmark_quality in ("moderate", "strong")
        and ranking_quality in ("moderate", "strong")
        and stability_value in ("moderate", "stable")
        and bool(edge_values)
        and all(value > 0 for value in edge_values)
    )
    reasons = []
    if benchmark_quality in ("unknown", "weak"):
        reasons.append(benchmark_reason)
    if ranking_quality in ("unknown", "weak"):
        reasons.append("Ranking or bucket calibration is not strong enough.")
    if stability_value not in ("moderate", "stable"):
        reasons.append("Benchmark edge is not statistically stable enough.")
    if not reasons:
        reasons.append("Evidence could support a future experiment, but this PR remains diagnostic-only.")
    return {
        "version": VERSION,
        "generated_at": utc_now(),
        "input_files": {
            "benchmark_hardening": hardening_path,
            "calibration_diagnostics": calibration_path,
            "diversified_vs_original_eval": diversified_eval_path,
            "benchmark_stability": stability_path,
            "replay_qualification": replay_qualification_path,
        },
        "recommendation": "diagnostic_only",
        "benchmark_signal_quality": benchmark_quality,
        "ranking_signal_quality": ranking_quality,
        "stability": stability_value,
        "diversification_value": _diversification_value(diversified_eval),
        "cruncher_minus_random": random_edge,
        "cruncher_minus_frequency": frequency_edge,
        "cruncher_minus_recency": recency_edge,
        "replay_gate_currently_allows_prior": bool((qualification or {}).get("can_influence_future_prior")),
        "can_unlock_replay_prior": False,
        "eligible_for_future_experiment": future_eligible,
        "reason": " ".join(reasons),
        "required_next_evidence": [
            "cruncher beats random/frequency/recency with stable margin",
            "ranking_signal_quality >= moderate",
            "top buckets outperform rest",
            "diversified slate improves best-of-N without excessive score loss",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build benchmark summary gate.")
    parser.add_argument("--hardening", default="v4_benchmark_hardening.json")
    parser.add_argument("--calibration", default="v4_calibration_diagnostics.json")
    parser.add_argument("--diversified-eval", default="v4_diversified_vs_original_eval.json")
    parser.add_argument("--stability", default="v4_benchmark_stability.json")
    parser.add_argument("--replay-qualification", default="v4_replay_qualification.json")
    parser.add_argument("--output", default="v4_benchmark_summary.json")
    args = parser.parse_args()
    report = build_summary(args.hardening, args.calibration, args.diversified_eval, args.stability, args.replay_qualification)
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {args.output}; recommendation={report['recommendation']}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
