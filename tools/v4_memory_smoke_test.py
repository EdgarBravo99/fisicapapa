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
    )
    return 0 if expected else 1


if __name__ == "__main__":
    raise SystemExit(main())
