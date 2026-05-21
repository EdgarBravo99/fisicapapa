# -*- coding: utf-8 -*-
"""Focused smoke tests for local audit state."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.v4_audit_state import build_audit  # noqa: E402


def run_smoke() -> dict[str, bool]:
    report = build_audit()
    return {
        "has_git_branch": bool(report["git"]["branch"]),
        "critical_files_reported": "resultados.json" in report["critical_files"],
        "replay_section_exists": "can_influence_future_prior" in report["replay"],
        "physics_section_exists": "weight_records_count" in report["physics"],
        "recommendation_valid": report["recommendation"] in {"ok", "review_warnings"},
    }


def main() -> int:
    checks = run_smoke()
    for name, ok in checks.items():
        print(f"{name}: {'OK' if ok else 'FAIL'}")
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
