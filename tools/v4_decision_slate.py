# -*- coding: utf-8 -*-
"""Build a diagnostic review slate from existing combinations only."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VERSION = "V4.4-decision-slate"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load(path: str | Path) -> dict[str, Any] | None:
    file_path = Path(path)
    if not file_path.exists():
        return None
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _numbers(row: dict[str, Any]) -> list[int]:
    raw = row.get("numbers") or []
    if not isinstance(raw, list):
        return []
    numbers = []
    for value in raw:
        try:
            number = int(float(str(value).strip()))
        except (TypeError, ValueError):
            continue
        if 1 <= number <= 56 and number not in numbers:
            numbers.append(number)
    return sorted(numbers) if len(numbers) == 6 else []


def _score(row: dict[str, Any]) -> float:
    for key in ("score_percent", "net_score", "score", "confidence"):
        try:
            value = float(row.get(key))
        except (TypeError, ValueError):
            continue
        return value * 100 if key == "net_score" and 0 <= value <= 1 else value
    return 0.0


def _pure_rank_top(resultados: dict[str, Any] | None, k: int) -> list[dict[str, Any]]:
    rows = (resultados or {}).get("top_combinations") or []
    if not isinstance(rows, list):
        return []
    output = []
    for index, row in enumerate(rows[:k]):
        if not isinstance(row, dict):
            continue
        numbers = _numbers(row)
        if not numbers:
            continue
        output.append(
            {
                "numbers": numbers,
                "source": "pure_rank",
                "rank_original": index + 1,
                "rank_diversified": None,
                "score_reference": round(_score(row), 6),
                "selection_reason": "pure_rank",
                "warnings": [],
            }
        )
    return output


def _diversified_top(diversity: dict[str, Any] | None) -> list[dict[str, Any]]:
    rows = (diversity or {}).get("diversified_combinations") or []
    if not isinstance(rows, list):
        return []
    output = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        numbers = _numbers(row)
        if not numbers:
            continue
        output.append(
            {
                "numbers": numbers,
                "source": "diversified",
                "rank_original": row.get("rank_original"),
                "rank_diversified": row.get("rank_diversified"),
                "score_reference": row.get("original_score") or 0.0,
                "selection_reason": row.get("selection_reason") or "mmr_selected",
                "warnings": [],
            }
        )
    return output


def _warnings(qualification: dict[str, Any] | None, diversity: dict[str, Any] | None, candidate_pool: dict[str, Any] | None, physics: dict[str, Any] | None) -> list[str]:
    warnings = []
    if not qualification or qualification.get("can_influence_future_prior") is not True:
        warnings.append("Replay no autorizado para prior.")
    if (physics or {}).get("latest_event", {}).get("suspected"):
        warnings.append("Evento fisico sospechoso no confirmado.")
    if float((diversity or {}).get("diversity_gain") or 0.0) <= 0:
        warnings.append("Top combinations altamente clonadas o sin mejora de diversidad.")
    if not (candidate_pool or {}).get("can_improve_diversity_with_existing_data"):
        warnings.append("No hay pool amplio suficiente para diversificar con evidencia actual.")
    return warnings


def build_slate(
    resultados_path: str = "resultados.json",
    diversity_path: str = "v4_diversity_output.json",
    candidate_pool_path: str = "v4_candidate_pool_audit.json",
    benchmark_path: str = "v4_baseline_benchmark.json",
    physics_path: str = "v4_physics_regime_analysis.json",
    qualification_path: str = "v4_replay_qualification.json",
    k: int = 10,
) -> dict[str, Any]:
    resultados = _load(resultados_path)
    diversity = _load(diversity_path)
    candidate_pool = _load(candidate_pool_path)
    benchmark = _load(benchmark_path)
    physics = _load(physics_path)
    qualification = _load(qualification_path)

    pure = _pure_rank_top(resultados, k)
    diversified = _diversified_top(diversity)
    diversity_gain = float((diversity or {}).get("diversity_gain") or 0.0)
    if diversified:
        balanced = diversified[:k]
        if diversity_gain <= 0:
            for row in balanced:
                row["warnings"] = [*row.get("warnings", []), "low_diversity_warning"]
                if row.get("selection_reason") == "mmr_selected":
                    row["selection_reason"] = "fallback_low_diversity"
    else:
        balanced = pure[:k]
        for row in balanced:
            row["warnings"] = [*row.get("warnings", []), "no_diversified_set_available"]

    return {
        "version": VERSION,
        "generated_at": _utc_now(),
        "mode": "diagnostic_only",
        "source_files": {
            "resultados": resultados_path,
            "diversity": diversity_path,
            "candidate_pool": candidate_pool_path,
            "benchmark": benchmark_path,
            "physics": physics_path,
            "replay_qualification": qualification_path,
        },
        "warnings": _warnings(qualification, diversity, candidate_pool, physics),
        "evidence_summary": {
            "replay_can_influence": bool((qualification or {}).get("can_influence_future_prior")),
            "eligible_for_future_experiment": bool((qualification or {}).get("eligible_for_future_experiment")),
            "benchmark_signal_quality": (benchmark or {}).get("benchmark_summary", {}).get("signal_quality") or "unknown",
            "diversity_gain": diversity_gain,
            "candidate_pool_status": (candidate_pool or {}).get("pools_detected", {}).get((candidate_pool or {}).get("best_available_pool"), {}).get("status") or "unknown",
            "best_available_pool": (candidate_pool or {}).get("best_available_pool") or "unknown",
            "physics_status": (physics or {}).get("latest_event", {}).get("status") or "unknown",
        },
        "review_sets": {
            "pure_rank_top": pure,
            "diversified_top": diversified,
            "balanced_review_set": balanced,
        },
        "language_guardrail": "Set de revision diagnostico. No es probabilidad de ganar.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build diagnostic decision slate.")
    parser.add_argument("--output", default="v4_decision_slate.json")
    parser.add_argument("--k", type=int, default=10)
    args = parser.parse_args()
    report = build_slate(k=max(1, args.k))
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {args.output}; balanced review set: {len(report['review_sets']['balanced_review_set'])}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
