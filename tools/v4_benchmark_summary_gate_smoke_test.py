# -*- coding: utf-8 -*-
"""Smoke tests for benchmark summary gate."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from v4_benchmark_summary_gate import build_summary


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write(root / "hardening.json", {"records_count": 30, "cruncher_minus_random": -0.1, "cruncher_minus_frequency": None, "cruncher_minus_recency": None})
        _write(root / "calibration.json", {"ranking_signal_quality": "weak"})
        _write(root / "diversified.json", {"coverage_gain": 0})
        _write(root / "stability.json", {"stability": "unstable"})
        _write(root / "qualification.json", {"can_influence_future_prior": False})
        report = build_summary(
            root / "hardening.json",
            root / "calibration.json",
            root / "diversified.json",
            root / "stability.json",
            root / "qualification.json",
        )
        assert report["recommendation"] == "diagnostic_only"
        assert report["can_unlock_replay_prior"] is False
        assert report["eligible_for_future_experiment"] is False
    print("v4_benchmark_summary_gate_smoke_test OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
