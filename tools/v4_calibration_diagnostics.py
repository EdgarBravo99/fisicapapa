# -*- coding: utf-8 -*-
"""Ranking and bucket calibration diagnostics for replay records."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from v4_benchmark_hardening import DRAW_SIZE, MAX_NUMBER, load_replay_records, score_rows, utc_now

VERSION = "V4.4-calibration-diagnostics"
RANK_BANDS = {
    "top6": (1, 6),
    "top10": (7, 10),
    "top20": (11, 20),
    "top40": (21, 40),
    "rest": (41, 56),
}
PERCENTILE_BUCKETS = {
    "p0_p20": (0.0, 0.20),
    "p20_p40": (0.20, 0.40),
    "p40_p60": (0.40, 0.60),
    "p60_p80": (0.60, 0.80),
    "p80_p90": (0.80, 0.90),
    "p90_p100": (0.90, 1.01),
}


def _empty_row(records_count: int) -> dict[str, Any]:
    return {
        "records_count": records_count,
        "appearances_expected": 0.0,
        "appearances_observed": 0,
        "predicted_count": 0,
        "hit_rate": 0.0,
        "lift_vs_random": 0.0,
        "lift_vs_rest": 0.0,
    }


def _finalize(row: dict[str, Any], rest_rate: float) -> dict[str, Any]:
    predicted = row["predicted_count"]
    hit_rate = row["appearances_observed"] / predicted if predicted else 0.0
    random_rate = DRAW_SIZE / MAX_NUMBER
    row["hit_rate"] = round(hit_rate, 6)
    row["appearances_expected"] = round(predicted * random_rate, 6)
    row["lift_vs_random"] = round(hit_rate - random_rate, 6)
    row["lift_vs_rest"] = round(hit_rate - rest_rate, 6)
    return row


def _rank_band(rank: int) -> str:
    for name, (low, high) in RANK_BANDS.items():
        if low <= rank <= high:
            return name
    return "rest"


def _percentile_bucket(percentile: float) -> str:
    for name, (low, high) in PERCENTILE_BUCKETS.items():
        if low <= percentile < high:
            return name
    return "p0_p20"


def build_calibration(replay_memory: str | Path = "v4_replay_memory.json") -> dict[str, Any]:
    records, input_state = load_replay_records(replay_memory)
    rank_rows = {name: _empty_row(len(records)) for name in RANK_BANDS}
    bucket_rows = {name: _empty_row(len(records)) for name in PERCENTILE_BUCKETS}
    for record in records:
        rows = score_rows(record)
        total = len(rows)
        for index, row in enumerate(rows, start=1):
            appeared = bool(row["appeared"])
            rank_band = _rank_band(index)
            percentile = 1.0 - ((index - 1) / max(total - 1, 1))
            bucket = _percentile_bucket(percentile)
            for target in (rank_rows[rank_band], bucket_rows[bucket]):
                target["predicted_count"] += 1
                target["appearances_observed"] += 1 if appeared else 0
    rest_rate = (
        rank_rows["rest"]["appearances_observed"] / rank_rows["rest"]["predicted_count"]
        if rank_rows["rest"]["predicted_count"]
        else DRAW_SIZE / MAX_NUMBER
    )
    rank_rows = {name: _finalize(row, rest_rate) for name, row in rank_rows.items()}
    bucket_rows = {name: _finalize(row, rest_rate) for name, row in bucket_rows.items()}
    top_signal = min(rank_rows["top6"]["lift_vs_random"], rank_rows["top10"]["lift_vs_random"], rank_rows["top20"]["lift_vs_random"])
    top_vs_rest = min(rank_rows["top6"]["lift_vs_rest"], rank_rows["top10"]["lift_vs_rest"], rank_rows["top20"]["lift_vs_rest"])
    high_bucket_rate = max(bucket_rows["p80_p90"]["hit_rate"], bucket_rows["p90_p100"]["hit_rate"])
    mid_bucket_rate = max(bucket_rows["p40_p60"]["hit_rate"], bucket_rows["p60_p80"]["hit_rate"])
    if len(records) < 30:
        quality = "unknown"
        reason = "Records insuficientes para calibracion estable."
    elif top_signal <= 0 or top_vs_rest <= 0 or high_bucket_rate <= mid_bucket_rate:
        quality = "weak"
        reason = "Top bands o buckets altos no superan random/rest de forma consistente."
    elif top_signal >= 0.04 and top_vs_rest >= 0.04:
        quality = "strong"
        reason = "Top bands superan random y rest con margen claro."
    else:
        quality = "moderate"
        reason = "Top bands superan random/rest, pero con margen pequeno."
    return {
        "version": VERSION,
        "generated_at": utc_now(),
        "input_source": str(replay_memory),
        "input_state": input_state,
        "records_count": len(records),
        "rank_band_performance": rank_rows,
        "score_bucket_performance": bucket_rows,
        "ranking_signal_quality": quality,
        "reason": reason,
        "recommendation": "diagnostic_only",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build ranking and bucket calibration diagnostics.")
    parser.add_argument("--replay-memory", default="v4_replay_memory.json")
    parser.add_argument("--output", default="v4_calibration_diagnostics.json")
    args = parser.parse_args()
    report = build_calibration(args.replay_memory)
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {args.output}; ranking_signal_quality={report['ranking_signal_quality']}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
