# -*- coding: utf-8 -*-
"""Smoke tests for frequency dominance audit."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from v4_frequency_dominance_audit import build_frequency_dominance


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        memory = Path(tmp) / "memory.json"
        memory.write_text(json.dumps({"records": []}), encoding="utf-8")
        report = build_frequency_dominance(str(memory))
        assert report["records_evaluated"] == 0
        assert report["recommendation"] == "diagnostic_only"
        assert report["frequency_minus_cruncher"] is None
    print("v4_frequency_dominance_audit_smoke_test OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
