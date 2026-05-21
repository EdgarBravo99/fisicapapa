# -*- coding: utf-8 -*-
"""Focused smoke tests for diagnostic decision slate."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.v4_decision_slate import build_slate  # noqa: E402


def _write(path: Path, data: dict) -> str:
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


def run_smoke() -> dict[str, bool]:
    top = [{"numbers": [1, 2, 3, 4, 5, 6], "score_percent": 90}]
    diversified = [{"numbers": [1, 2, 3, 4, 5, 6], "rank_original": 1, "rank_diversified": 1, "original_score": 90, "selection_reason": "top_rank_anchor"}]
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        resultados = _write(root / "resultados.json", {"top_combinations": top})
        diversity = _write(root / "diversity.json", {"diversity_gain": 0.0, "diversified_combinations": diversified})
        candidate = _write(root / "candidate.json", {"can_improve_diversity_with_existing_data": False, "best_available_pool": "top_combinations", "pools_detected": {"top_combinations": {"status": "too_narrow"}}})
        benchmark = _write(root / "benchmark.json", {"benchmark_summary": {"signal_quality": "weak"}})
        physics = _write(root / "physics.json", {"latest_event": {"suspected": True, "status": "hypothesis_not_confirmed"}})
        qualification = _write(root / "qualification.json", {"can_influence_future_prior": False, "eligible_for_future_experiment": False})
        report = build_slate(
            resultados_path=resultados,
            diversity_path=diversity,
            candidate_pool_path=candidate,
            benchmark_path=benchmark,
            physics_path=physics,
            qualification_path=qualification,
        )
    balanced = report["review_sets"]["balanced_review_set"]
    return {
        "mode_diagnostic": report["mode"] == "diagnostic_only",
        "uses_diversified_if_available": balanced[0]["source"] == "diversified",
        "warns_low_diversity": "low_diversity_warning" in balanced[0]["warnings"],
        "does_not_invent_combo": balanced[0]["numbers"] == [1, 2, 3, 4, 5, 6],
    }


def main() -> int:
    checks = run_smoke()
    for name, ok in checks.items():
        print(f"{name}: {'OK' if ok else 'FAIL'}")
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
