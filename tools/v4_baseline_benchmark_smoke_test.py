# -*- coding: utf-8 -*-
"""Focused smoke tests for the V4.4 baseline benchmark."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.v4_baseline_benchmark import build_benchmark  # noqa: E402


def _record(index: int) -> dict:
    target = {1, 2, 3, 4, 5, 6}
    return {
        "record_type": "historical_replay",
        "leakage_passed": True,
        "target_draw": str(4100 + index),
        "target_numbers": sorted(target),
        "number_score_errors": {
            str(number): {
                "predicted_score": 100 - number,
                "appeared": number in target,
            }
            for number in range(1, 57)
        },
    }


def run_smoke() -> dict[str, bool]:
    with tempfile.TemporaryDirectory() as tmp:
        missing = build_benchmark(Path(tmp) / "missing.json")
        memory_path = Path(tmp) / "v4_replay_memory.json"
        memory_path.write_text(json.dumps({"records": [_record(1), _record(2)]}), encoding="utf-8")
        small = build_benchmark(memory_path)
    return {
        "missing_memory_ok": missing["records_count"] == 0 and missing["benchmark_summary"]["signal_quality"] == "unknown",
        "small_memory_unknown": small["records_count"] == 2 and small["benchmark_summary"]["signal_quality"] == "unknown",
        "brier_disabled": small["experimental_brier"]["enabled"] is False,
        "diagnostic_only": small["benchmark_summary"]["recommendation"] == "diagnostic_only",
    }


def main() -> int:
    checks = run_smoke()
    for name, ok in checks.items():
        print(f"{name}: {'OK' if ok else 'FAIL'}")
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
