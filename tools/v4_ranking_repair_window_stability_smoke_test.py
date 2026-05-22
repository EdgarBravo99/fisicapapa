# -*- coding: utf-8 -*-
"""Smoke tests for ranking repair window stability."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from v4_ranking_repair_window_stability import build_window_stability


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        experiment = {
            "best_variant": {"name": "repair"},
            "variants": {
                "original_cruncher": {"record_results": [{"target_draw": draw, "top10_hits": 1, "top20_hits": 2} for draw in range(1, 61)]},
                "frequency_only": {"record_results": [{"target_draw": draw, "top10_hits": 2, "top20_hits": 3} for draw in range(2, 61)]},
                "repair": {"record_results": [{"target_draw": draw, "top10_hits": 2 if draw <= 15 else 1, "top20_hits": 3} for draw in range(1, 61)]},
            },
        }
        (root / "experiment.json").write_text(json.dumps(experiment), encoding="utf-8")
        (root / "memory.json").write_text(json.dumps({"records": []}), encoding="utf-8")
        report = build_window_stability(root / "experiment.json", root / "memory.json")
        assert report["summary"]["windows_improved_count"] == 1
        assert report["summary"]["stable_across_windows"] is False
        assert report["summary"]["recommendation"] == "diagnostic_only"
    print("v4_ranking_repair_window_stability_smoke_test OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
