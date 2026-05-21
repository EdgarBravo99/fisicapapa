# -*- coding: utf-8 -*-
"""Focused smoke tests for candidate pool audit."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.v4_candidate_pool_audit import build_audit  # noqa: E402


def run_smoke() -> dict[str, bool]:
    data = {
        "top_combinations": [
            {"numbers": [1, 2, 3, 4, 5, 6]},
            {"numbers": [1, 2, 3, 4, 5, 7]},
            {"numbers": [1, 2, 3, 4, 5, 8]},
        ],
        "manual_suggestion_seed": [{"number": n} for n in range(1, 57)],
    }
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "resultados.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        report = build_audit(path)
    top = report["pools_detected"]["top_combinations"]
    manual = report["pools_detected"]["manual_suggestion_seed"]
    return {
        "detects_top_combinations": top["exists"] is True and top["valid_combinations"] == 3,
        "does_not_treat_numbers_as_combos": manual["valid_combinations"] == 0,
        "marks_narrow_or_small": top["status"] in {"too_small", "too_narrow"},
        "does_not_invent_pool": report["best_available_pool_size"] == 3,
    }


def main() -> int:
    checks = run_smoke()
    for name, ok in checks.items():
        print(f"{name}: {'OK' if ok else 'FAIL'}")
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
