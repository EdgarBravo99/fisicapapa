# -*- coding: utf-8 -*-
"""Smoke tests for post-ranking smoothing stress test."""

from __future__ import annotations

import hashlib
from pathlib import Path

from v4_post_ranking_smoothing_stress_test import build_smoothing_stress_test
from v4_post_ranking_validation_common import SMOOTHING_VARIANTS


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    replay = Path("v4_replay_memory.json")
    before = _sha(replay) if replay.exists() else None
    report = build_smoothing_stress_test(str(replay))
    after = _sha(replay) if replay.exists() else None
    assert before == after, "replay memory changed"
    assert set(SMOOTHING_VARIANTS).issubset(set(report["variants"]))
    assert report["best_smoothing_variant"]["name"] in report["variants"]
    assert report["summary"]["recommendation"] == "diagnostic_only"
    print("post-ranking smoothing smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
