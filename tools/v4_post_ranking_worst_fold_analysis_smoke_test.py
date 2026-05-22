# -*- coding: utf-8 -*-
"""Smoke tests for post-ranking worst-fold analysis."""

from __future__ import annotations

from v4_post_ranking_confidence_gate_experiment import build_confidence_gate_experiment
from v4_post_ranking_smoothing_stress_test import build_smoothing_stress_test
from v4_post_ranking_worst_fold_analysis import build_worst_fold_analysis


def main() -> int:
    smoothing = build_smoothing_stress_test()
    confidence = build_confidence_gate_experiment()
    assert smoothing["best_smoothing_variant"]["name"]
    assert confidence["best_policy"]["name"]
    report = build_worst_fold_analysis()
    assert report["mode"] == "diagnostic_only"
    assert isinstance(report["worst_folds"], list)
    assert report["summary"]["recommendation"] == "diagnostic_only"
    print("post-ranking worst-fold smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
