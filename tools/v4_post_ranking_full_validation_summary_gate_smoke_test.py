# -*- coding: utf-8 -*-
"""Smoke tests for post-ranking full validation summary gate."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from v4_post_ranking_full_validation_summary_gate import build_full_summary, decision_record_from_summary


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        smoothing = root / "smoothing.json"
        confidence = root / "confidence.json"
        worst = root / "worst.json"
        holdout = root / "holdout.json"
        repair = root / "repair.json"
        benchmark = root / "benchmark.json"
        signal = root / "signal.json"
        _write(smoothing, {"best_smoothing_variant": {"name": "frequency_window_15"}, "variants": {"frequency_window_15": {"rolling_pass_rate": 0.5}}})
        _write(confidence, {"best_policy": {"name": "always_repair__min_history_15"}, "policies": {"always_repair__min_history_15": {"rolling_pass_rate": 0.5, "avg_edge_vs_original": 0.2, "avg_edge_vs_frequency": 0.0, "avg_edge_vs_random": 0.1, "worst_fold_delta_vs_frequency": -0.2, "policy_status": "pass"}}})
        _write(worst, {"summary": {"main_failure_pattern": "unknown"}})
        _write(holdout, {"holdout_pass_rate": 1.0})
        _write(repair, {})
        _write(benchmark, {"recommendation": "diagnostic_only"})
        _write(signal, {"prior_should_remain_blocked": True})
        report = build_full_summary(str(smoothing), str(confidence), str(worst), str(holdout), str(repair), str(benchmark), str(signal))
        assert report["candidate_status"] in {"reject", "keep_candidate", "ready_for_controlled_layer"}
        assert report["production_ready"] is False
        assert report["prior_should_remain_blocked"] is True
        assert report["recommendation"] == "diagnostic_only"
        decision = decision_record_from_summary(report)
        assert decision["recommendation"] == "diagnostic_only"
        assert "do not enable replay prior" in decision["forbidden_next_steps"]
    print("post-ranking full summary smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
