# -*- coding: utf-8 -*-
"""Smoke tests for post-ranking holdout summary gate."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from v4_post_ranking_holdout_summary_gate import build_holdout_summary


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        holdout = root / "holdout.json"
        rolling = root / "rolling.json"
        repair = root / "repair.json"
        signal = root / "signal.json"
        benchmark = root / "benchmark.json"
        _write(
            holdout,
            {
                "candidate_variant": "top6_preserved_plus_frequency_no_duplicates",
                "summary": {
                    "splits_passed": 1,
                    "splits_total": 3,
                    "holdout_signal_quality": "weak",
                    "avg_edge_vs_original": 0.2,
                    "avg_edge_vs_frequency": -0.1,
                    "avg_edge_vs_random": 0.1,
                },
            },
        )
        _write(
            rolling,
            {
                "summary": {
                    "folds_passed": 1,
                    "folds_total": 6,
                    "rolling_signal_quality": "weak",
                    "avg_repaired_minus_original": 0.1,
                    "avg_repaired_minus_frequency": -0.1,
                    "avg_repaired_minus_random": 0.1,
                }
            },
        )
        _write(repair, {"best_repair_variant": "top6_preserved_plus_frequency_no_duplicates"})
        _write(signal, {"prior_should_remain_blocked": True})
        _write(benchmark, {"recommendation": "diagnostic_only"})
        report = build_holdout_summary(str(holdout), str(rolling), str(repair), str(signal), str(benchmark))
        assert report["recommendation"] == "diagnostic_only"
        assert report["production_ready"] is False
        assert report["prior_should_remain_blocked"] is True
        assert report["future_experimental_layer_candidate"] is False
        assert report["overfit_risk"] == "high"
    print("post-ranking holdout summary smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
