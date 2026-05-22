# -*- coding: utf-8 -*-
"""Windowed replay failure diagnostics.

Read-only diagnostic: segments replay records and compares cruncher signal
against simple baselines without updating memory, priors, or resultados.json.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from v4_benchmark_hardening import (
    DRAW_SIZE,
    MAX_NUMBER,
    avg,
    best_hits,
    load_replay_records,
    parse_int,
    random_expected_hits,
    score_rows,
    target_numbers,
    topk_hit_rate,
    topk_hits,
    utc_now,
)

VERSION = "V4.4-replay-window-diagnostics"


def _draw(record: dict[str, Any]) -> int:
    return parse_int(record.get("target_draw")) or 0


def _progressive_baselines(records: list[dict[str, Any]], k: int = 10) -> dict[str, Any]:
    counts: Counter[int] = Counter()
    previous: list[int] | None = None
    frequency_hits: list[float] = []
    recency_hits: list[float] = []
    for record in records:
        target = set(target_numbers(record))
        if counts:
            ranked = [number for number, _ in counts.most_common(MAX_NUMBER)]
            ranked.extend(number for number in range(1, MAX_NUMBER + 1) if number not in counts)
            frequency_hits.append(float(len(set(ranked[:k]) & target)))
        if previous:
            recency_hits.append(float(len(set(previous[:DRAW_SIZE]) & target)))
        counts.update(target)
        previous = target_numbers(record)
    return {
        "frequency_baseline_hits": avg(frequency_hits) if frequency_hits else None,
        "recency_baseline_hits": avg(recency_hits) if recency_hits else None,
    }


def _ranking_quality(records: list[dict[str, Any]]) -> str:
    if len(records) < 10:
        return "unknown"
    top10_hits = sum(topk_hits(record, 10) for record in records)
    top10_predicted = sum(min(10, len(score_rows(record))) for record in records)
    rest_hits = 0
    rest_predicted = 0
    for record in records:
        rows = score_rows(record)
        rest = rows[40:]
        rest_hits += sum(1 for row in rest if row["appeared"])
        rest_predicted += len(rest)
    top10_rate = top10_hits / top10_predicted if top10_predicted else 0.0
    rest_rate = rest_hits / rest_predicted if rest_predicted else DRAW_SIZE / MAX_NUMBER
    random_rate = DRAW_SIZE / MAX_NUMBER
    if top10_rate <= random_rate or top10_rate <= rest_rate:
        return "weak"
    if top10_rate - max(random_rate, rest_rate) >= 0.04:
        return "moderate"
    return "weak"


def _window(window_id: str, records: list[dict[str, Any]]) -> dict[str, Any]:
    baselines = _progressive_baselines(records)
    cruncher_hits = avg([float(topk_hits(record, 10)) for record in records])
    random_hits = random_expected_hits(10)
    freq = baselines["frequency_baseline_hits"]
    recency = baselines["recency_baseline_hits"]
    worst = sorted(
        (
            {
                "target_draw": _draw(record),
                "top10_hits": topk_hits(record, 10),
                "top20_hits": topk_hits(record, 20),
                "target_numbers": target_numbers(record),
            }
            for record in records
        ),
        key=lambda row: (row["top20_hits"], row["top10_hits"], row["target_draw"]),
    )[:5]
    low_confidence = len(records) < 10
    quality = _ranking_quality(records)
    if low_confidence:
        interpretation = "window_low_confidence"
    elif quality == "weak":
        interpretation = "ranking weak or below simple baseline in this window"
    else:
        interpretation = "localized signal candidate; still diagnostic_only"
    return {
        "window_id": window_id,
        "draw_start": _draw(records[0]) if records else None,
        "draw_end": _draw(records[-1]) if records else None,
        "records_count": len(records),
        "window_low_confidence": low_confidence,
        "cruncher_top6_hit_rate": topk_hit_rate(records, 6),
        "cruncher_top10_hit_rate": topk_hit_rate(records, 10),
        "cruncher_top20_hit_rate": topk_hit_rate(records, 20),
        "cruncher_avg_top10_hits": cruncher_hits,
        "random_expected_hits": random_hits,
        "frequency_baseline_hits": freq,
        "recency_baseline_hits": recency,
        "cruncher_minus_random": round(cruncher_hits - random_hits, 6) if records else 0.0,
        "cruncher_minus_frequency": round(cruncher_hits - freq, 6) if freq is not None else None,
        "cruncher_minus_recency": round(cruncher_hits - recency, 6) if recency is not None else None,
        "ranking_signal_quality_window": quality,
        "best_hits_top10_avg": avg([float(best_hits(record, 10)) for record in records]),
        "worst_targets": worst,
        "interpretation": interpretation,
    }


def _chunk_windows(records: list[dict[str, Any]], size: int) -> list[dict[str, Any]]:
    windows = []
    for start in range(0, len(records), size):
        chunk = records[start : start + size]
        if not chunk:
            continue
        windows.append(_window(f"draws_{_draw(chunk[0])}_{_draw(chunk[-1])}", chunk))
    return windows


def build_window_diagnostics(replay_memory: str = "v4_replay_memory.json") -> dict[str, Any]:
    records, input_state = load_replay_records(replay_memory)
    windows = _chunk_windows(records, 15)
    windows.extend(_chunk_windows(records, 20))
    if records:
        windows.append(_window(f"draws_{_draw(records[0])}_{_draw(records[-1])}", records))
    if len(records) < 30:
        summary = {
            "consistent_failure": False,
            "localized_signal": False,
            "best_window": None,
            "worst_window": None,
            "recommendation": "diagnostic_only",
            "reason": "insufficient_data",
        }
    else:
        scored = [row for row in windows if row["records_count"] >= 10]
        best = max(scored, key=lambda row: row.get("cruncher_minus_random") or -999, default=None)
        worst = min(scored, key=lambda row: row.get("cruncher_minus_random") or 999, default=None)
        failures = [row for row in scored if row["ranking_signal_quality_window"] == "weak"]
        summary = {
            "consistent_failure": len(failures) == len(scored) if scored else False,
            "localized_signal": any(row["ranking_signal_quality_window"] != "weak" for row in scored),
            "best_window": best["window_id"] if best else None,
            "worst_window": worst["window_id"] if worst else None,
            "recommendation": "diagnostic_only",
        }
    return {
        "version": VERSION,
        "generated_at": utc_now(),
        "input_source": replay_memory,
        "input_state": input_state,
        "records_count": len(records),
        "windows": windows,
        "summary": summary,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build replay window diagnostics.")
    parser.add_argument("--replay-memory", default="v4_replay_memory.json")
    parser.add_argument("--output", default="v4_replay_window_diagnostics.json")
    args = parser.parse_args()
    report = build_window_diagnostics(args.replay_memory)
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {args.output}; records={report['records_count']}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
