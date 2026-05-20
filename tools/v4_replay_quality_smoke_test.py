# -*- coding: utf-8 -*-
"""Quality smoke tests for V4.3.3 replay prior aggregation."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from v4_replay_memory import (  # noqa: E402
    ENABLE_REPLAY_PRIOR,
    compute_replay_prior,
    default_replay_memory,
    normalize_replay_number_rows,
    rebuild_replay_aggregate,
)


def _number_rows(appeared_numbers: set[int], high_numbers: set[int] | None = None) -> dict[str, dict]:
    high_numbers = high_numbers or set(range(1, 11))
    rows = {}
    for number in range(1, 57):
        if number in high_numbers:
            score = 95 - number * 0.2
        elif 21 <= number <= 40:
            score = 50 - (number - 21) * 0.2
        else:
            score = 15 + (number % 5)
        appeared = number in appeared_numbers
        rows[str(number)] = {
            "predicted_score": round(score, 4),
            "appeared": appeared,
            "error": round(score - (100 if appeared else 0), 4),
        }
    return rows


def _record(index: int, appeared_numbers: set[int], record_type: str = "historical_replay") -> dict:
    return {
        "record_type": record_type,
        "leakage_passed": True,
        "game_mode": "revancha",
        "prediction_draw": str(4000 + index),
        "target_draw": str(4001 + index),
        "number_score_errors": _number_rows(appeared_numbers),
    }


def _memory(records: list[dict]) -> dict:
    memory = default_replay_memory()
    memory["records"] = records
    return memory


def run_smoke() -> dict[str, bool]:
    weak_records = [_record(index, {35, 36, 37, 41, 42, 43}) for index in range(30)]
    weak_memory = _memory(weak_records)
    weak_aggregate = rebuild_replay_aggregate(weak_memory)
    weak_prior = compute_replay_prior(weak_memory)

    legacy_records = weak_records + [_record(99, {1, 2, 3, 4, 5, 6}, record_type="legacy_hindsight_snapshot")]
    legacy_aggregate = rebuild_replay_aggregate(_memory(legacy_records))

    rows = normalize_replay_number_rows(_record(1, {56}))
    row_1 = next(row for row in rows if row["number"] == 1)
    row_56 = next(row for row in rows if row["number"] == 56)

    strong_records = [_record(index, {1, 2, 3, 4, 5, 6}) for index in range(30)]
    strong_memory = _memory(strong_records)
    strong_prior = compute_replay_prior(strong_memory)
    adjustments = strong_prior.get("adjustments") or {}

    return {
        "weak_signal_diagnostic_only": weak_aggregate["calibration_summary"]["prior_quality"] == "diagnostic_only" and not weak_prior["eligible"],
        "overestimated_not_all_misses": len(weak_aggregate["overestimated_numbers"]) < 20,
        "underestimated_low_rank_appeared": all(str(number) in weak_aggregate["underestimated_numbers"] for number in (41, 42, 43)),
        "weighted_evidence_exists": bool(weak_aggregate["overestimated_weighted"]) and bool(weak_aggregate["underestimated_weighted"]),
        "compute_prior_uses_weighted_evidence": bool(adjustments) and max(abs(float(value)) for value in adjustments.values()) <= 0.02,
        "enable_replay_prior_false": ENABLE_REPLAY_PRIOR is False,
        "replay_prior_not_applied": strong_prior["applied"] is False,
        "legacy_hindsight_ignored": legacy_aggregate["records_count"] == weak_aggregate["records_count"],
        "backward_compatible_rank": row_1["rank"] == 1 and row_1["percentile"] >= 0.99 and row_1["bucket"] == "p90_p100",
        "backward_compatible_low_rank": row_56["rank"] > 40 and row_56["bucket"] in {"p0_p20", "p20_p40"},
    }


if __name__ == "__main__":
    output = run_smoke()
    print(json.dumps(output, indent=2, ensure_ascii=False))
    failed = [key for key, value in output.items() if value is not True]
    if failed:
        raise SystemExit(f"Replay quality smoke failed: {failed}")
