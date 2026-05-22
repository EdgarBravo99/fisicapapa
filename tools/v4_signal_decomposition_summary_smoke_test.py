# -*- coding: utf-8 -*-
"""Smoke tests for signal decomposition summary."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from v4_signal_decomposition_summary import build_signal_summary


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write(root / "windows.json", {"summary": {"consistent_failure": True}, "records_count": 60})
        _write(root / "ranking.json", {"ranking_failure_mode": "flat"})
        _write(root / "frequency.json", {"frequency_minus_cruncher": 0.5})
        _write(root / "draws.json", {"summary": {"high_or_extreme_failures": 3}})
        _write(root / "benchmark.json", {"benchmark_signal_quality": "weak"})
        report = build_signal_summary(root / "windows.json", root / "ranking.json", root / "frequency.json", root / "draws.json", root / "benchmark.json")
        assert report["prior_should_remain_blocked"] is True
        assert report["recommendation"] == "diagnostic_only"
        assert report["failure_scope"] == "global"
        assert report["frequency_dominance"] is True
    print("v4_signal_decomposition_summary_smoke_test OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
