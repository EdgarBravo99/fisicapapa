# -*- coding: utf-8 -*-
"""Smoke tests for post-ranking rolling validation."""

from __future__ import annotations

import hashlib
from pathlib import Path

from v4_post_ranking_rolling_validation import build_rolling_validation


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    replay_path = Path("v4_replay_memory.json")
    before = _sha256(replay_path) if replay_path.exists() else None
    report = build_rolling_validation(str(replay_path), initial_train_size=30, test_window_size=5, step_size=5)
    after = _sha256(replay_path) if replay_path.exists() else None
    assert before == after, "v4_replay_memory.json was modified"
    assert report["summary"]["recommendation"] == "diagnostic_only"
    assert report["initial_train_size"] == 30
    assert report["test_window_size"] == 5
    for fold in report["folds"]:
        assert int(fold["train_records"]) >= 30
        assert int(fold["test_records"]) <= 5
        assert fold["test_start"] > fold["train_end"]
    print("post-ranking rolling smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
