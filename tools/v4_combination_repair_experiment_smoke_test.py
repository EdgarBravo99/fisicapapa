# -*- coding: utf-8 -*-
"""Smoke tests for combination repair experiment."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from v4_combination_repair_experiment import build_combination_repair


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        memory = Path(tmp) / "memory.json"
        memory.write_text(json.dumps({"records": []}), encoding="utf-8")
        report = build_combination_repair(str(memory))
        assert report["combination_repair_available"] is False
        assert report["summary"]["recommendation"] == "diagnostic_only"
        assert report["summary"]["records_without_pool"] == 0
    print("v4_combination_repair_experiment_smoke_test OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
