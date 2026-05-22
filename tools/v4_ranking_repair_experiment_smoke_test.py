# -*- coding: utf-8 -*-
"""Smoke tests for ranking repair experiment."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from v4_ranking_repair_experiment import build_ranking_repair_experiment


def _record(draw: int, target: list[int]) -> dict:
    return {
        "record_type": "historical_replay",
        "target_draw": draw,
        "target_numbers": target,
        "leakage_passed": True,
        "number_score_errors": {
            str(number): {"predicted_score": 100 - number, "appeared": number in target}
            for number in range(1, 57)
        },
    }


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        memory = Path(tmp) / "memory.json"
        before = {"records": [_record(1, [1, 2, 3, 4, 5, 6]), _record(2, [7, 8, 9, 10, 11, 12])]}
        memory.write_text(json.dumps(before), encoding="utf-8")
        report = build_ranking_repair_experiment(str(memory))
        after = json.loads(memory.read_text(encoding="utf-8"))
        assert before == after
        assert "original_cruncher" in report["variants"]
        assert "frequency_only" in report["variants"]
        assert report["mode"] == "diagnostic_only"
        assert report["summary"]["recommendation"] == "diagnostic_only"
    print("v4_ranking_repair_experiment_smoke_test OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
