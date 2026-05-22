# -*- coding: utf-8 -*-
"""Smoke tests for post-ranking confidence gate experiment."""

from __future__ import annotations

import hashlib
from pathlib import Path

from v4_post_ranking_confidence_gate_experiment import POLICIES, build_confidence_gate_experiment


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    replay = Path("v4_replay_memory.json")
    before = _sha(replay) if replay.exists() else None
    report = build_confidence_gate_experiment(str(replay))
    after = _sha(replay) if replay.exists() else None
    assert before == after, "replay memory changed"
    names = set(report["policies"])
    for policy in POLICIES:
        assert any(name.startswith(policy) for name in names), f"missing {policy}"
    assert report["best_policy"]["name"] in report["policies"]
    assert report["summary"]["recommendation"] == "diagnostic_only"
    print("post-ranking confidence gate smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
