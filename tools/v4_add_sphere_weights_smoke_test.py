# -*- coding: utf-8 -*-
"""Focused smoke tests for adding sphere weights."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.v4_add_sphere_weights import add_record  # noqa: E402


def _weights(offset: float = 0.0) -> dict[str, float]:
    return {str(number): round(4.5 + offset + number / 1000, 3) for number in range(1, 57)}


def run_smoke() -> dict[str, bool]:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "sphere_weight_history.json"
        path.write_text(json.dumps({"records": []}), encoding="utf-8")
        add_record(path, 4216, "revancha", [1, 2, 3, 4, 5, 6], _weights(), "observed_weight_record")
        duplicate_blocked = False
        try:
            add_record(path, 4216, "revancha", [1, 2, 3, 4, 5, 6], _weights(0.1), "observed_weight_record")
        except ValueError:
            duplicate_blocked = True
        add_record(path, 4216, "revancha", [1, 2, 3, 4, 5, 6], _weights(0.1), "observed_weight_record", force=True)
        data = json.loads(path.read_text(encoding="utf-8"))
    record = data["records"][0]
    return {
        "adds_one_record": len(data["records"]) == 1,
        "duplicate_blocked": duplicate_blocked,
        "force_replaces": record["weights_grams"]["1"] == _weights(0.1)["1"],
        "default_status_preserved": record["status"] == "observed_weight_record",
    }


def main() -> int:
    checks = run_smoke()
    for name, ok in checks.items():
        print(f"{name}: {'OK' if ok else 'FAIL'}")
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
