# -*- coding: utf-8 -*-
"""Smoke tests for controlled post-ranking comparison."""

from __future__ import annotations

from v4_post_ranking_controlled_comparison import build_controlled_comparison
from v4_post_ranking_controlled_layer import build_controlled_layer


def main() -> int:
    layer = build_controlled_layer()
    report = build_controlled_comparison(layer_report=layer)
    assert report["mode"] == "controlled_experiment"
    assert isinstance(report["controlled_layer_available"], bool)
    assert report["recommended_usage"] == "review_only"
    assert report["validation_status"]["production_ready"] is False
    assert report["validation_status"]["prior_should_remain_blocked"] is True
    assert set(report["overlap"]).issuperset({"top6", "top10", "top20"})
    if report["controlled_layer_available"]:
        assert report["top6_preservation_ok"] is True
    print("controlled comparison smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
