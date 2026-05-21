# -*- coding: utf-8 -*-
"""Focused smoke tests for replay qualification gate."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.v4_replay_qualification_gate import build_gate  # noqa: E402


def _write(path: Path, data: dict) -> str:
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


def run_smoke() -> dict[str, bool]:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        replay = _write(root / "replay.json", {
            "records": [{} for _ in range(30)],
            "aggregate": {
                "records_count": 30,
                "leakage_passed_count": 30,
                "calibration_summary": {"prior_quality": "diagnostic_only", "ranking_signal_quality": "weak"},
            },
        })
        analysis = _write(root / "analysis.json", {"summary": {}})
        benchmark = _write(root / "benchmark.json", {"records_count": 30, "benchmark_summary": {"signal_quality": "weak", "recommendation": "diagnostic_only"}})
        diversity = _write(root / "diversity.json", {"diversity_gain": 0.2})
        candidate = _write(root / "candidate.json", {"can_improve_diversity_with_existing_data": True})
        physics = _write(root / "physics.json", {"latest_event": {"suspected": True}, "regime_timing": {"can_estimate_periodicity": False}})
        report = build_gate(
            replay_memory=replay,
            replay_analysis=analysis,
            benchmark=benchmark,
            diversity=diversity,
            candidate_pool=candidate,
            physics=physics,
        )
    return {
        "blocks_weak_benchmark": report["gates"]["benchmark_ok"] is False,
        "blocks_weak_ranking": report["gates"]["ranking_quality_ok"] is False,
        "blocks_physics_without_periodicity": report["gates"]["physics_regime_ok"] is False,
        "does_not_activate_prior": report["can_influence_future_prior"] is False and report["recommendation"] == "diagnostic_only",
    }


def main() -> int:
    checks = run_smoke()
    for name, ok in checks.items():
        print(f"{name}: {'OK' if ok else 'FAIL'}")
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
