# -*- coding: utf-8 -*-
"""Smoke tests for draw failure report."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from v4_draw_failure_report import build_draw_failure_report


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        memory = Path(tmp) / "memory.json"
        memory.write_text(json.dumps({"records": []}), encoding="utf-8")
        report = build_draw_failure_report(str(memory))
        assert report["records_count"] == 0
        assert report["summary"]["targets_with_zero_top10_hits"] == 0
        assert report["recommendation"] == "diagnostic_only"
    print("v4_draw_failure_report_smoke_test OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
