# -*- coding: utf-8 -*-
"""Smoke tests for controlled post-ranking summary gate."""

from __future__ import annotations

from v4_post_ranking_controlled_comparison import build_controlled_comparison
from v4_post_ranking_controlled_layer import build_controlled_layer
from v4_post_ranking_controlled_summary_gate import build_controlled_summary


def main() -> int:
    layer = build_controlled_layer()
    comparison = build_controlled_comparison(layer_report=layer)
    report = build_controlled_summary(layer_report=layer, comparison_report=comparison)
    assert report["controlled_layer_status"] in {"controlled_layer_ready", "controlled_layer_blocked", "insufficient_data"}
    assert isinstance(report["usable_in_app"], bool)
    assert report["production_ready"] is False
    assert report["prior_should_remain_blocked"] is True
    forbidden = " ".join(report["must_not_do"]).lower()
    assert "replace resultados.json" in forbidden
    assert "activate replay prior" in forbidden
    assert "probability" in forbidden
    print("controlled summary gate smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
