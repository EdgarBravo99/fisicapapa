# -*- coding: utf-8 -*-
"""Smoke tests for benchmark hardening diagnostics."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from v4_benchmark_hardening import build_hardening


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        missing = Path(tmp) / "missing.json"
        report = build_hardening(missing)
        assert report["records_count"] == 0
        assert report["recommendation"] == "diagnostic_only"
        assert report["frequency_baseline_hits"]["available"] is False
        short = Path(tmp) / "memory.json"
        short.write_text(json.dumps({"records": []}), encoding="utf-8")
        short_report = build_hardening(short)
        assert short_report["records_count"] == 0
    print("v4_benchmark_hardening_smoke_test OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
