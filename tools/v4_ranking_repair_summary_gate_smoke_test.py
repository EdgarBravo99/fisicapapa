# -*- coding: utf-8 -*-
"""Smoke tests for ranking repair summary gate."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from v4_ranking_repair_summary_gate import build_summary


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write(root / "experiment.json", {"best_variant": {"name": "repair"}, "summary": {"ranking_repair_improves_original": True}, "variants": {"repair": {"beats_random": True, "beats_frequency": True, "top10_avg_hits": 2}, "frequency_only": {"top10_avg_hits": 1.8}}})
        _write(root / "stability.json", {"summary": {"stable_across_windows": True}})
        _write(root / "combination.json", {"combination_repair_available": True})
        _write(root / "signal.json", {"prior_should_remain_blocked": True})
        _write(root / "benchmark.json", {"benchmark_signal_quality": "moderate"})
        report = build_summary(root / "experiment.json", root / "stability.json", root / "combination.json", root / "signal.json", root / "benchmark.json")
        assert report["future_post_ranking_layer_candidate"] is True
        assert report["prior_should_remain_blocked"] is True
        assert report["recommendation"] == "diagnostic_only"
    print("v4_ranking_repair_summary_gate_smoke_test OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
