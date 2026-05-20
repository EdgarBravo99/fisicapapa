#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Smoke checks for V4.3.1 memory guardrails."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from v4_feedback_memory import (  # noqa: E402
    apply_memory_prior_to_score_vector,
    compute_memory_prior,
    default_feedback_memory,
    memory_strength_from_records,
    rebuild_aggregate,
)
from tools.v4_history_analyzer import analyze_history  # noqa: E402


def _record(index: int, source: str = "git_history") -> dict:
    return {
        "prediction_draw": str(4200 + index),
        "target_draw": str(4201 + index),
        "game_mode": "revancha",
        "snapshot_source": source,
        "source_commit_sha": f"commit-{index}",
        "top_combinations": [{"numbers": [1, 2, 3, 4, 5, 6], "hits": index % 3}],
        "number_score_errors": {
            "16": {"predicted_score": 90, "appeared": False, "error": 90},
            "22": {"predicted_score": 10, "appeared": True, "error": -90},
        },
    }


def run_smoke() -> dict:
    results = {}
    for count in (0, 1, 2, 3, 5, 8, 10):
        memory = default_feedback_memory()
        memory["records"] = [_record(i) for i in range(count)]
        rebuild_aggregate(memory)
        prior = compute_memory_prior(memory, {"evidence_insufficient": count < 3})
        results[str(count)] = {
            "eligible": prior["eligible"],
            "mode": prior["mode"],
            "strength": memory_strength_from_records(count),
        }
    memory = default_feedback_memory()
    memory["records"] = [_record(i) for i in range(3)]
    rebuild_aggregate(memory)
    prior = compute_memory_prior(memory, {"evidence_insufficient": False})
    adjusted, audit = apply_memory_prior_to_score_vector([0.5] * 56, prior)
    max_delta = max(abs(row["delta"]) for row in audit) if audit else 0
    results["max_delta_ok"] = max_delta <= 0.02500001
    results["mock_blocked"] = not compute_memory_prior({"records": [_record(i, "mock") for i in range(3)]}, {"evidence_insufficient": False})["eligible"]
    with tempfile.TemporaryDirectory() as tmp:
        temp_path = Path(tmp) / "empty.json"
        temp_path.write_text("", encoding="utf-8")
        results["empty_snapshot_fixture"] = temp_path.exists()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        archive = root / "resultados_archive"
        archive.mkdir()
        csv_path = root / "historial.csv"
        csv_path.write_text(
            "sorteo,n1,n2,n3,n4,n5,n6\n"
            "4215,1,8,16,22,33,44\n"
            "4216,2,9,17,23,34,45\n",
            encoding="utf-8",
        )
        seed = [
            {"number": number, "score": 85 if number in {16, 22, 33} else 35, "main_driver": ["physical", "transformer", "xgboost", "fourier", "graph"][number % 5]}
            for number in range(1, 57)
        ]
        for index in range(3):
            snapshot = {
                "prediction_draw": "4214",
                "game_mode": "revancha",
                "model_version": "V4.2-oos-feedback-loop",
                "score_kind": "v4_2_deep_stacking_meta_score",
                "csv_path": str(csv_path),
                "snapshot_metadata": {"source": "git_history", "commit_sha": f"sha-{index}", "short_sha": f"sha-{index}"},
                "top_combinations": [
                    {"numbers": [16, 19, 25, 29, 45, 50], "score_percent": 88},
                    {"numbers": [1, 8, 16, 22, 33, 44], "score_percent": 45},
                ],
                "generator_pool": [
                    {"numbers": [16, 19, 25, 29, 45, 50], "score_percent": 88},
                    {"numbers": [16, 19, 25, 29, 45, 50], "score_percent": 84},
                    {"numbers": [1, 8, 16, 22, 33, 44], "score_percent": 45},
                ],
                "number_scores": {"16": 90, "22": 20, "50": 95, "1": 25},
                "manual_suggestion_seed": seed,
                "walk_forward": {"avg_hits": 2.4, "avg_hits_top10": 2.2},
            }
            (archive / f"resultados_git_4214_sha-{index}.json").write_text(json.dumps(snapshot), encoding="utf-8")
        analysis_path = root / "analysis.json"
        analysis = analyze_history(archive, csv_path=csv_path, output_path=analysis_path)
        mistakes = analysis["mistakes_summary"]
        required = [
            "bad_score_buckets",
            "top_combo_failure_patterns",
            "expert_miscalibration",
            "monte_carlo_diversity_issues",
            "walk_forward_gap",
        ]
        results["history_analysis_non_empty"] = all(bool(mistakes.get(key)) for key in required)
        stale_prior = compute_memory_prior(memory, None)
        results["stale_analysis_failure_forces_diagnostic"] = (
            stale_prior["mode"] == "diagnostic_only" and not stale_prior["eligible"]
        )
    return results


def main() -> int:
    result = run_smoke()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    expected = (
        not result["0"]["eligible"]
        and not result["1"]["eligible"]
        and not result["2"]["eligible"]
        and result["3"]["eligible"]
        and result["max_delta_ok"]
        and result["mock_blocked"]
        and result["history_analysis_non_empty"]
        and result["stale_analysis_failure_forces_diagnostic"]
    )
    return 0 if expected else 1


if __name__ == "__main__":
    raise SystemExit(main())
