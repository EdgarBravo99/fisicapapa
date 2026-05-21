# -*- coding: utf-8 -*-
"""Focused smoke tests for physics timeline."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.v4_physics_timeline import build_timeline  # noqa: E402


def _record(draw: int) -> dict:
    return {
        "draw_id": draw,
        "game_mode": "revancha",
        "winning_numbers": [1, 2, 3, 4, 5, 6],
        "weights_grams": {str(number): round(4.5 + number / 1000, 3) for number in range(1, 57)},
        "status": "observed_weight_record",
    }


def run_smoke() -> dict[str, bool]:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "sphere_weight_history.json"
        path.write_text(json.dumps({"records": [_record(4215)]}), encoding="utf-8")
        one = build_timeline(path)
        path.write_text(json.dumps({"records": [_record(4215), _record(4216)]}), encoding="utf-8")
        two = build_timeline(path)
    return {
        "one_record_periodicity_false": one["event_summary"]["can_estimate_periodicity"] is False,
        "one_record_no_shifts": len(one["shifts"]) == 0,
        "two_records_has_shift": len(two["shifts"]) == 1,
        "diagnostic_only": one["recommendation"] == "diagnostic_only",
    }


def main() -> int:
    checks = run_smoke()
    for name, ok in checks.items():
        print(f"{name}: {'OK' if ok else 'FAIL'}")
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
