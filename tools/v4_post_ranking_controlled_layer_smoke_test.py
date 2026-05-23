# -*- coding: utf-8 -*-
"""Smoke tests for the controlled post-ranking layer."""

from __future__ import annotations

import hashlib
from pathlib import Path

from v4_post_ranking_controlled_layer import build_controlled_layer


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    results = Path("resultados.json")
    replay = Path("v4_replay_memory.json")
    before_results = _sha256(results)
    before_replay = _sha256(replay)
    report = build_controlled_layer(str(results), str(replay))
    assert _sha256(results) == before_results, "resultados.json was modified"
    assert _sha256(replay) == before_replay, "v4_replay_memory.json was modified"
    assert report["mode"] == "controlled_experiment"
    assert report["status"] in {"ready", "insufficient_data", "blocked"}
    assert report["production_ready"] is False
    assert report["prior_should_remain_blocked"] is True
    assert report["official_results_untouched"] is True
    assert report["frequency_context"] == "replay_memory_recent_window"
    assert report["frequency_window_size"] == 15
    assert report["frequency_is_truth_source"] is False
    if report["status"] == "ready":
        assert report["top6_preserved"] == report["original_top_numbers"][:6]
        assert report["controlled_top20_numbers"][:6] == report["top6_preserved"]
        assert report["diff_vs_original"]["preserved_top6"] is True
    print("controlled layer smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
