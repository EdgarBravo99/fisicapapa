# -*- coding: utf-8 -*-
"""Explain how progressive frequency baseline compares with cruncher top10."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from v4_benchmark_hardening import MAX_NUMBER, load_replay_records, parse_int, score_rows, target_numbers, topk_hits, utc_now

VERSION = "V4.4-frequency-dominance-audit"


def _draw(record: dict[str, Any]) -> int:
    return parse_int(record.get("target_draw")) or 0


def _top10(record: dict[str, Any]) -> list[int]:
    return [row["number"] for row in score_rows(record)[:10]]


def build_frequency_dominance(replay_memory: str = "v4_replay_memory.json") -> dict[str, Any]:
    records, input_state = load_replay_records(replay_memory)
    counts: Counter[int] = Counter()
    cruncher_rank_counts: Counter[int] = Counter()
    frequency_like_counts: Counter[int] = Counter()
    overweights: Counter[int] = Counter()
    underweights: Counter[int] = Counter()
    breakdown: list[dict[str, Any]] = []
    overlaps: list[int] = []
    frequency_hits_total = 0
    cruncher_hits_total = 0
    wins = losses = ties = 0
    for record in records:
        target = set(target_numbers(record))
        cruncher = _top10(record)
        for number in cruncher:
            cruncher_rank_counts[number] += 1
        if not counts:
            counts.update(target)
            continue
        ranked = [number for number, _ in counts.most_common(MAX_NUMBER)]
        ranked.extend(number for number in range(1, MAX_NUMBER + 1) if number not in counts)
        frequency = ranked[:10]
        for number in frequency:
            frequency_like_counts[number] += 1
        cruncher_hits = topk_hits(record, 10)
        frequency_hits = len(set(frequency) & target)
        overlap = len(set(cruncher) & set(frequency))
        overlaps.append(overlap)
        frequency_hits_total += frequency_hits
        cruncher_hits_total += cruncher_hits
        if frequency_hits > cruncher_hits:
            wins += 1
        elif cruncher_hits > frequency_hits:
            losses += 1
        else:
            ties += 1
        for number in cruncher:
            if number not in target and number not in frequency:
                overweights[number] += 1
        for number in frequency:
            if number in target and number not in cruncher:
                underweights[number] += 1
        breakdown.append(
            {
                "target_draw": _draw(record),
                "frequency_top10": frequency,
                "cruncher_top10": cruncher,
                "frequency_hits": frequency_hits,
                "cruncher_hits": cruncher_hits,
                "overlap_top10": overlap,
                "winner": "frequency" if frequency_hits > cruncher_hits else "cruncher" if cruncher_hits > frequency_hits else "tie",
            }
        )
        counts.update(target)
    evaluated = len(breakdown)
    avg_overlap = round(sum(overlaps) / evaluated, 6) if evaluated else 0.0
    frequency_avg = round(frequency_hits_total / evaluated, 6) if evaluated else 0.0
    cruncher_avg = round(cruncher_hits_total / evaluated, 6) if evaluated else 0.0
    interpretation = "frequency baseline uses only previous replay targets; diagnostic_only"
    if evaluated and frequency_avg > cruncher_avg:
        interpretation = "frequency baseline beats cruncher top10 on progressive replay targets"
    return {
        "version": VERSION,
        "generated_at": utc_now(),
        "input_source": replay_memory,
        "input_state": input_state,
        "records_count": len(records),
        "records_evaluated": evaluated,
        "frequency_avg_hits": frequency_avg,
        "cruncher_avg_hits": cruncher_avg,
        "frequency_minus_cruncher": round(frequency_avg - cruncher_avg, 6) if evaluated else None,
        "overlap_summary": {
            "avg_overlap_top10": avg_overlap,
            "low_overlap_targets": [row for row in breakdown if row["overlap_top10"] <= 2][:10],
        },
        "top_frequency_numbers": [{"number": number, "count": count} for number, count in frequency_like_counts.most_common(10)],
        "top_cruncher_overweighted_numbers": [{"number": number, "count": count} for number, count in overweights.most_common(10)],
        "top_cruncher_underweighted_numbers": [{"number": number, "count": count} for number, count in underweights.most_common(10)],
        "numbers_frequency_likes": [{"number": number, "count": count} for number, count in frequency_like_counts.most_common(20)],
        "numbers_cruncher_overweights": [{"number": number, "count": count} for number, count in overweights.most_common(20)],
        "numbers_cruncher_underweights": [{"number": number, "count": count} for number, count in underweights.most_common(20)],
        "targets_where_frequency_wins": wins,
        "targets_where_cruncher_wins": losses,
        "targets_tied": ties,
        "target_breakdown": breakdown,
        "interpretation": interpretation,
        "recommendation": "diagnostic_only",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit frequency baseline dominance.")
    parser.add_argument("--replay-memory", default="v4_replay_memory.json")
    parser.add_argument("--output", default="v4_frequency_dominance_audit.json")
    args = parser.parse_args()
    report = build_frequency_dominance(args.replay_memory)
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {args.output}; frequency_minus_cruncher={report['frequency_minus_cruncher']}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
