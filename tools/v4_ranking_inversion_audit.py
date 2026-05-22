# -*- coding: utf-8 -*-
"""Audit whether replay ranking bands are flat or inverted."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from v4_benchmark_hardening import DRAW_SIZE, MAX_NUMBER, load_replay_records, score_rows, utc_now

VERSION = "V4.4-ranking-inversion-audit"
SEGMENTED = {
    "rank_1_6": (1, 6),
    "rank_7_10": (7, 10),
    "rank_11_20": (11, 20),
    "rank_21_40": (21, 40),
    "rank_41_56": (41, 56),
}
CUMULATIVE = {
    "top6": (1, 6),
    "top10": (1, 10),
    "top20": (1, 20),
    "top40": (1, 40),
    "all56": (1, 56),
}


def _empty() -> dict[str, Any]:
    return {
        "predicted_count": 0,
        "observed_hits": 0,
        "hit_rate": 0.0,
        "lift_vs_random": 0.0,
        "lift_vs_rank_41_56": 0.0,
        "lift_vs_all": 0.0,
        "inversion_flag": False,
    }


def _fill(rows: list[dict[str, Any]], bands: dict[str, tuple[int, int]]) -> dict[str, dict[str, Any]]:
    output = {name: _empty() for name in bands}
    for record_rows in rows:
        for rank, row in enumerate(record_rows, start=1):
            for name, (low, high) in bands.items():
                if low <= rank <= high:
                    output[name]["predicted_count"] += 1
                    output[name]["observed_hits"] += 1 if row["appeared"] else 0
    return output


def _finalize(bands: dict[str, dict[str, Any]], rest_rate: float, all_rate: float) -> dict[str, dict[str, Any]]:
    random_rate = DRAW_SIZE / MAX_NUMBER
    for row in bands.values():
        predicted = row["predicted_count"]
        hit_rate = row["observed_hits"] / predicted if predicted else 0.0
        row["hit_rate"] = round(hit_rate, 6)
        row["lift_vs_random"] = round(hit_rate - random_rate, 6)
        row["lift_vs_rank_41_56"] = round(hit_rate - rest_rate, 6)
        row["lift_vs_all"] = round(hit_rate - all_rate, 6)
    return bands


def _mode(segmented: dict[str, dict[str, Any]], cumulative: dict[str, dict[str, Any]]) -> tuple[str, dict[str, bool]]:
    top10 = cumulative["top10"]["hit_rate"]
    rest = segmented["rank_41_56"]["hit_rate"]
    mid = segmented["rank_21_40"]["hit_rate"]
    random_rate = DRAW_SIZE / MAX_NUMBER
    tests = {
        "top10_underperforms_rest": top10 < rest,
        "rank_21_40_beats_top10": mid > top10,
        "mid_bucket_beats_high_bucket": max(segmented["rank_11_20"]["hit_rate"], mid) > max(segmented["rank_1_6"]["hit_rate"], segmented["rank_7_10"]["hit_rate"]),
        "score_monotonicity_broken": not (
            segmented["rank_1_6"]["hit_rate"]
            >= segmented["rank_7_10"]["hit_rate"]
            >= segmented["rank_11_20"]["hit_rate"]
            >= segmented["rank_21_40"]["hit_rate"]
        ),
    }
    if tests["top10_underperforms_rest"] or tests["rank_21_40_beats_top10"]:
        return "inverted", tests
    if abs(top10 - random_rate) <= 0.02 and abs(rest - random_rate) <= 0.02:
        return "flat", tests
    if cumulative["top6"]["hit_rate"] > random_rate and cumulative["top10"]["hit_rate"] <= random_rate:
        return "weak_top_only", tests
    return "unknown" if not top10 else "flat", tests


def build_ranking_inversion(replay_memory: str = "v4_replay_memory.json") -> dict[str, Any]:
    records, input_state = load_replay_records(replay_memory)
    rows = [score_rows(record) for record in records]
    segmented = _fill(rows, SEGMENTED)
    cumulative = _fill(rows, CUMULATIVE)
    rest_rate = (
        segmented["rank_41_56"]["observed_hits"] / segmented["rank_41_56"]["predicted_count"]
        if segmented["rank_41_56"]["predicted_count"]
        else DRAW_SIZE / MAX_NUMBER
    )
    all_rate = cumulative["all56"]["observed_hits"] / cumulative["all56"]["predicted_count"] if cumulative["all56"]["predicted_count"] else DRAW_SIZE / MAX_NUMBER
    segmented = _finalize(segmented, rest_rate, all_rate)
    cumulative = _finalize(cumulative, rest_rate, all_rate)
    mode, tests = _mode(segmented, cumulative)
    for row in segmented.values():
        row["inversion_flag"] = row["lift_vs_rank_41_56"] < 0
    for row in cumulative.values():
        row["inversion_flag"] = row["lift_vs_rank_41_56"] < 0
    return {
        "version": VERSION,
        "generated_at": utc_now(),
        "input_source": replay_memory,
        "input_state": input_state,
        "records_count": len(records),
        "segmented_bands": segmented,
        "cumulative_bands": cumulative,
        "inversion_tests": tests,
        "ranking_failure_mode": mode if len(records) >= 10 else "unknown",
        "recommendation": "diagnostic_only",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit replay ranking inversion.")
    parser.add_argument("--replay-memory", default="v4_replay_memory.json")
    parser.add_argument("--calibration", default="v4_calibration_diagnostics.json")
    parser.add_argument("--output", default="v4_ranking_inversion_audit.json")
    args = parser.parse_args()
    report = build_ranking_inversion(args.replay_memory)
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {args.output}; mode={report['ranking_failure_mode']}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
