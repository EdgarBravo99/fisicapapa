# -*- coding: utf-8 -*-
"""Conservative summary gate for diagnostic ranking repair experiments."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from v4_benchmark_hardening import utc_now

VERSION = "V4.4-ranking-repair-summary-gate"


def _load(path: str | Path) -> dict[str, Any] | None:
    file_path = Path(path)
    if not file_path.exists():
        return None
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def build_summary(
    experiment_path: str = "v4_ranking_repair_experiment.json",
    stability_path: str = "v4_ranking_repair_window_stability.json",
    combination_path: str = "v4_combination_repair_experiment.json",
    signal_path: str = "v4_signal_decomposition_summary.json",
    benchmark_path: str = "v4_benchmark_summary.json",
) -> dict[str, Any]:
    experiment = _load(experiment_path) or {}
    stability = _load(stability_path) or {}
    combination = _load(combination_path) or {}
    signal = _load(signal_path) or {}
    benchmark = _load(benchmark_path) or {}
    best = experiment.get("best_variant", {}).get("name")
    variants = experiment.get("variants", {})
    best_row = variants.get(best, {}) if best else {}
    improves = bool((experiment.get("summary") or {}).get("ranking_repair_improves_original"))
    beats_frequency = bool(best_row.get("beats_frequency") or (experiment.get("summary") or {}).get("ranking_repair_beats_frequency"))
    beats_random = bool(best_row.get("beats_random") or (experiment.get("summary") or {}).get("ranking_repair_beats_random"))
    stable = bool((stability.get("summary") or {}).get("stable_across_windows"))
    combination_available = bool(combination.get("combination_repair_available"))
    future_candidate = improves and stable and beats_random and (beats_frequency or (best_row.get("top10_avg_hits") is not None and best_row.get("top10_avg_hits", 0) >= (variants.get("frequency_only", {}).get("top10_avg_hits") or 999) - 0.25))
    reasons = []
    if not improves:
        reasons.append("Repair does not improve original ranking.")
    if not beats_frequency:
        reasons.append("Repair does not beat progressive frequency.")
    if not beats_random:
        reasons.append("Repair does not beat random expectation.")
    if not stable:
        reasons.append("Repair is not stable across windows.")
    if signal.get("prior_should_remain_blocked") is True:
        reasons.append("Signal decomposition still blocks prior.")
    if (benchmark.get("benchmark_signal_quality") or "weak") == "weak":
        reasons.append("Benchmark signal remains weak.")
    if not reasons:
        reasons.append("Repair is a future candidate only; this PR remains diagnostic_only.")
    return {
        "version": VERSION,
        "generated_at": utc_now(),
        "input_files": {
            "ranking_repair_experiment": experiment_path,
            "ranking_repair_window_stability": stability_path,
            "combination_repair_experiment": combination_path,
            "signal_decomposition": signal_path,
            "benchmark_summary": benchmark_path,
        },
        "recommendation": "diagnostic_only",
        "best_repair_variant": best,
        "repair_improves_original": improves,
        "repair_beats_frequency": beats_frequency,
        "repair_beats_random": beats_random,
        "repair_stable_across_windows": stable,
        "combination_repair_available": combination_available,
        "future_post_ranking_layer_candidate": future_candidate,
        "prior_should_remain_blocked": True,
        "reason": " ".join(reasons),
        "recommended_next_action": "investigate_signal_features_or_reranking_inputs",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build ranking repair summary gate.")
    parser.add_argument("--experiment", default="v4_ranking_repair_experiment.json")
    parser.add_argument("--stability", default="v4_ranking_repair_window_stability.json")
    parser.add_argument("--combination", default="v4_combination_repair_experiment.json")
    parser.add_argument("--signal", default="v4_signal_decomposition_summary.json")
    parser.add_argument("--benchmark", default="v4_benchmark_summary.json")
    parser.add_argument("--output", default="v4_ranking_repair_summary.json")
    args = parser.parse_args()
    report = build_summary(args.experiment, args.stability, args.combination, args.signal, args.benchmark)
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {args.output}; best={report['best_repair_variant']}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
