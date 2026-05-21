# -*- coding: utf-8 -*-
"""Smoke tests for diversified vs original diagnostics."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from v4_diversified_vs_original_eval import build_eval


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        slate = {
            "review_sets": {
                "pure_rank_top": [{"numbers": [1, 2, 3, 4, 5, 6], "score_reference": 90}],
                "diversified_top": [{"numbers": [1, 2, 3, 7, 8, 9], "original_score": 85}],
                "balanced_review_set": [{"numbers": [1, 2, 3, 7, 8, 9], "score_reference": 85}],
            }
        }
        diversity = {"diversified_combinations": [{"numbers": [1, 2, 3, 7, 8, 9], "original_score": 85}]}
        memory = {"records": []}
        (root / "slate.json").write_text(json.dumps(slate), encoding="utf-8")
        (root / "diversity.json").write_text(json.dumps(diversity), encoding="utf-8")
        (root / "memory.json").write_text(json.dumps(memory), encoding="utf-8")
        report = build_eval(root / "diversity.json", root / "slate.json", root / "memory.json")
        assert report["original"]["unique_numbers_covered"] == 6
        assert report["diversified"]["unique_numbers_covered"] == 6
        assert report["hit_evaluation_available"] is False
        assert report["recommendation"] == "diagnostic_only"
    print("v4_diversified_vs_original_eval_smoke_test OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
