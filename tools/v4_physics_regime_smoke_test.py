# -*- coding: utf-8 -*-
"""Focused smoke tests for the V4.4 physics regime audit."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.v4_physics_regime_audit import build_analysis  # noqa: E402


def run_smoke() -> dict[str, bool]:
    source = ROOT / "sphere_weight_history.json"
    data = json.loads(source.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "sphere_weight_history.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        report = build_analysis(path)
    latest = report.get("latest_event") or {}
    timing = report.get("regime_timing") or {}
    metrics = report.get("latest_metrics") or {}
    return {
        "reads_56_weights": metrics.get("weights_count") == 56,
        "detects_4215_suspected": report.get("latest_draw") == 4215 and latest.get("suspected") is True,
        "not_confirmed": latest.get("status") == "hypothesis_not_confirmed",
        "periodicity_false": timing.get("can_estimate_periodicity") is False,
        "diagnostic_only": report.get("recommendation") == "diagnostic_only",
    }


def main() -> int:
    checks = run_smoke()
    for name, ok in checks.items():
        print(f"{name}: {'OK' if ok else 'FAIL'}")
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
