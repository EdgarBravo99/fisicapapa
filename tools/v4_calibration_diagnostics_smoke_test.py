# -*- coding: utf-8 -*-
"""Smoke tests for calibration diagnostics."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from v4_calibration_diagnostics import build_calibration


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        memory = Path(tmp) / "memory.json"
        memory.write_text(json.dumps({"records": []}), encoding="utf-8")
        report = build_calibration(memory)
        assert report["ranking_signal_quality"] == "unknown"
        assert "top6" in report["rank_band_performance"]
        assert "p90_p100" in report["score_bucket_performance"]
        assert report["recommendation"] == "diagnostic_only"
    print("v4_calibration_diagnostics_smoke_test OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
