# -*- coding: utf-8 -*-
"""Smoke tests for post-ranking holdout experiment."""

from __future__ import annotations

import hashlib
from pathlib import Path

from v4_post_ranking_holdout_experiment import CANDIDATE_VARIANT, build_holdout_experiment


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    replay_path = Path("v4_replay_memory.json")
    before = _sha256(replay_path) if replay_path.exists() else None
    report = build_holdout_experiment(str(replay_path))
    after = _sha256(replay_path) if replay_path.exists() else None
    assert before == after, "v4_replay_memory.json was modified"
    assert report["mode"] == "diagnostic_only"
    assert report["candidate_variant"] == CANDIDATE_VARIANT
    split_ids = {row["split_id"] for row in report["splits"]}
    assert "train_4155_4199_test_4200_4214" in split_ids
    assert "rolling_15_step" in split_ids
    assert "leave_one_window_out" in split_ids
    for split in report["splits"]:
        if split.get("split_status") == "pass":
            assert int(split.get("records_evaluated") or 0) >= 10
    print("post-ranking holdout smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
