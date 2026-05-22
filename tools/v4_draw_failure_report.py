# -*- coding: utf-8 -*-
"""Draw-level replay failure report."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from v4_benchmark_hardening import MAX_NUMBER, random_expected_hits, load_replay_records, parse_int, score_rows, target_numbers, utc_now

VERSION = "V4.4-draw-failure-report"


def _draw(record: dict[str, Any], key: str) -> int | None:
    return parse_int(record.get(key))


def _severity(top10_hits: int, top20_hits: int) -> str:
    if top20_hits == 0:
        return "extreme"
    if top10_hits == 0:
        return "high"
    if top10_hits == 1:
        return "medium"
    return "low"


def _progressive_baselines(records: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    previous: list[int] | None = None
    counts: Counter[int] = Counter()
    outputs: dict[int, dict[str, Any]] = {}
    for record in records:
        draw = _draw(record, "target_draw")
        target = set(target_numbers(record))
        frequency_hits = None
        if counts:
            ranked = [number for number, _ in counts.most_common(MAX_NUMBER)]
            ranked.extend(number for number in range(1, MAX_NUMBER + 1) if number not in counts)
            frequency_hits = len(set(ranked[:10]) & target)
        if draw is not None:
            outputs[draw] = {
                "frequency_top10_hits": frequency_hits,
                "recency_hits": len(set(previous[:6]) & target) if previous else None,
            }
        counts.update(target)
        previous = target_numbers(record)
    return outputs


def build_draw_failure_report(replay_memory: str = "v4_replay_memory.json") -> dict[str, Any]:
    records, input_state = load_replay_records(replay_memory)
    recency = _progressive_baselines(records)
    missed_counts: Counter[int] = Counter()
    overestimated: Counter[int] = Counter()
    underestimated: Counter[int] = Counter()
    targets = []
    for record in records:
        rows = score_rows(record)
        top6 = [row["number"] for row in rows[:6]]
        top10 = [row["number"] for row in rows[:10]]
        top20 = [row["number"] for row in rows[:20]]
        target = set(target_numbers(record))
        top10_hits = len(set(top10) & target)
        top20_hits = len(set(top20) & target)
        missed = sorted(target - set(top20))
        for number in missed:
            missed_counts[number] += 1
        for row in rows[:10]:
            if not row["appeared"]:
                overestimated[row["number"]] += 1
        for row in rows[20:]:
            if row["appeared"]:
                underestimated[row["number"]] += 1
        draw = _draw(record, "target_draw")
        severity = _severity(top10_hits, top20_hits)
        targets.append(
            {
                "target_draw": draw,
                "target_numbers": sorted(target),
                "prediction_draw": _draw(record, "prediction_draw"),
                "cruncher_top6_numbers": top6,
                "cruncher_top10_numbers": top10,
                "cruncher_top10_hits": top10_hits,
                "cruncher_top20_hits": top20_hits,
                "frequency_top10_hits": recency.get(draw or -1, {}).get("frequency_top10_hits"),
                "recency_hits": recency.get(draw or -1, {}).get("recency_hits"),
                "random_expected_hits": random_expected_hits(10),
                "missed_winning_numbers": missed,
                "overestimated_missed_numbers": [row["number"] for row in rows[:10] if not row["appeared"]],
                "underestimated_hit_numbers": [row["number"] for row in rows[20:] if row["appeared"]],
                "failure_severity": severity,
                "notes": "diagnostic_only; replay failure report does not alter scores",
            }
        )
    return {
        "version": VERSION,
        "generated_at": utc_now(),
        "input_source": replay_memory,
        "input_state": input_state,
        "records_count": len(records),
        "targets": targets,
        "summary": {
            "high_or_extreme_failures": sum(1 for row in targets if row["failure_severity"] in ("high", "extreme")),
            "targets_with_zero_top10_hits": sum(1 for row in targets if row["cruncher_top10_hits"] == 0),
            "targets_with_zero_top20_hits": sum(1 for row in targets if row["cruncher_top20_hits"] == 0),
            "most_missed_numbers": [{"number": number, "count": count} for number, count in missed_counts.most_common(10)],
            "most_overestimated_numbers": [{"number": number, "count": count} for number, count in overestimated.most_common(10)],
            "most_underestimated_numbers": [{"number": number, "count": count} for number, count in underestimated.most_common(10)],
        },
        "recommendation": "diagnostic_only",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build draw-level replay failure report.")
    parser.add_argument("--replay-memory", default="v4_replay_memory.json")
    parser.add_argument("--output", default="v4_draw_failure_report.json")
    args = parser.parse_args()
    report = build_draw_failure_report(args.replay_memory)
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {args.output}; targets={len(report['targets'])}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
