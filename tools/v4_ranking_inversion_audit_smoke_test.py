# -*- coding: utf-8 -*-
"""Smoke tests for ranking inversion audit."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from v4_ranking_inversion_audit import build_ranking_inversion


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        memory = Path(tmp) / "memory.json"
        memory.write_text(json.dumps({"records": []}), encoding="utf-8")
        report = build_ranking_inversion(str(memory))
        assert report["ranking_failure_mode"] == "unknown"
        assert "top10_underperforms_rest" in report["inversion_tests"]
        assert report["recommendation"] == "diagnostic_only"
    print("v4_ranking_inversion_audit_smoke_test OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
