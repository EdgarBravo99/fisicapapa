# -*- coding: utf-8 -*-
"""Smoke tests for benchmark stability diagnostics."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from v4_benchmark_stability import build_stability


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        hardening = Path(tmp) / "hardening.json"
        hardening.write_text(json.dumps({"records_count": 2, "record_edges": [{"cruncher_minus_random": 1}, {"cruncher_minus_random": -1}]}), encoding="utf-8")
        report = build_stability(hardening, "missing.json", iterations=100, seed=1)
        assert report["records_count"] == 2
        assert report["stability"] == "insufficient_data"
        assert report["recommendation"] == "diagnostic_only"
    print("v4_benchmark_stability_smoke_test OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
