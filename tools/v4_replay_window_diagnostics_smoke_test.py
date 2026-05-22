# -*- coding: utf-8 -*-
"""Smoke tests for replay window diagnostics."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from v4_replay_window_diagnostics import build_window_diagnostics


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        memory = Path(tmp) / "memory.json"
        memory.write_text(json.dumps({"records": []}), encoding="utf-8")
        report = build_window_diagnostics(str(memory))
        assert report["records_count"] == 0
        assert report["summary"]["reason"] == "insufficient_data"
        assert report["summary"]["recommendation"] == "diagnostic_only"
    print("v4_replay_window_diagnostics_smoke_test OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
