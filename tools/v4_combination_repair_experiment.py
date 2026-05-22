# -*- coding: utf-8 -*-
"""Diagnostic combination repair experiment using existing replay combos only."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from v4_benchmark_hardening import combo_numbers, combo_score, load_replay_records, score_rows, target_numbers, utc_now

VERSION = "V4.4-combination-repair-experiment"


def _avg(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 6) if values else None


def _pool(record: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for source in ("top_combinations", "generator_pool"):
        raw = record.get(source) or []
        if not isinstance(raw, list):
            continue
        for index, item in enumerate(raw):
            numbers = combo_numbers(item)
            if not numbers:
                continue
            rows.append(
                {
                    "numbers": numbers,
                    "score": combo_score(item),
                    "source": source,
                    "source_rank": index + 1,
                }
            )
    unique: dict[tuple[int, ...], dict[str, Any]] = {}
    for row in rows:
        key = tuple(row["numbers"])
        if key not in unique or row["score"] > unique[key]["score"]:
            unique[key] = row
    return list(unique.values())


def _top_numbers(record: dict[str, Any], k: int) -> list[int]:
    return [row["number"] for row in score_rows(record)[:k]]


def _frequency_rank(counts: Counter[int]) -> list[int]:
    ranked = [number for number, _ in counts.most_common(56)]
    ranked.extend(number for number in range(1, 57) if number not in counts)
    return ranked


def _jaccard(left: list[int], right: list[int]) -> float:
    union = set(left) | set(right)
    return len(set(left) & set(right)) / len(union) if union else 0.0


def _avg_jaccard(combos: list[list[int]]) -> float:
    if len(combos) < 2:
        return 0.0
    total = 0.0
    pairs = 0
    for index, combo in enumerate(combos):
        for other in combos[index + 1 :]:
            total += _jaccard(combo, other)
            pairs += 1
    return round(total / pairs, 6) if pairs else 0.0


def _best_hits(rows: list[dict[str, Any]], target: set[int], limit: int) -> int | None:
    selected = rows[:limit]
    if len(selected) < limit:
        return None
    return max((len(set(row["numbers"]) & target) for row in selected), default=0)


def _select(pool: list[dict[str, Any]], mode: str, top6: list[int], frequency: list[int]) -> list[dict[str, Any]]:
    if mode == "original_top_combinations":
        return sorted(pool, key=lambda row: (row["source"] != "top_combinations", row["source_rank"]))[:20]
    freq_top = set(frequency[:10])
    top6_set = set(top6)
    if mode == "top6_seeded_combinations":
        key = lambda row: (len(set(row["numbers"]) & top6_set), row["score"])
    elif mode == "frequency_seeded_existing_combinations":
        key = lambda row: (len(set(row["numbers"]) & freq_top), row["score"])
    else:
        key = lambda row: (len(set(row["numbers"]) & top6_set) + len(set(row["numbers"]) & freq_top), row["score"])
    return sorted(pool, key=key, reverse=True)[:20]


def _empty() -> dict[str, Any]:
    return {
        "records_evaluated": 0,
        "best_hits_top10": [],
        "best_hits_top20": [],
        "average_pairwise_jaccard": [],
        "unique_numbers_covered": [],
        "score_loss_proxy": [],
    }


def _summarize(raw: dict[str, Any], original: dict[str, Any] | None = None) -> dict[str, Any]:
    top10 = _avg(raw["best_hits_top10"])
    top20 = _avg(raw["best_hits_top20"])
    unique = _avg(raw["unique_numbers_covered"])
    original_unique = _avg((original or {}).get("unique_numbers_covered", [])) if original else None
    return {
        "records_evaluated": raw["records_evaluated"],
        "best_hits_top10_avg": top10,
        "best_hits_top20_avg": top20,
        "average_pairwise_jaccard": _avg(raw["average_pairwise_jaccard"]),
        "unique_numbers_covered": unique,
        "coverage_gain": round(unique - original_unique, 6) if unique is not None and original_unique is not None else None,
        "score_loss_proxy": _avg(raw["score_loss_proxy"]),
        "repair_improves_best_of_n": bool(top10 is not None and original and _avg(original["best_hits_top10"]) is not None and top10 > _avg(original["best_hits_top10"])),
    }


def build_combination_repair(replay_memory: str = "v4_replay_memory.json") -> dict[str, Any]:
    records, input_state = load_replay_records(replay_memory)
    counts: Counter[int] = Counter()
    variants = {
        "original_top_combinations": _empty(),
        "top6_seeded_combinations": _empty(),
        "frequency_seeded_existing_combinations": _empty(),
        "hybrid_seeded_existing_combinations": _empty(),
    }
    unavailable = 0
    for record in records:
        pool = _pool(record)
        target = set(target_numbers(record))
        top6 = _top_numbers(record, 6)
        frequency = _frequency_rank(counts) if counts else []
        if len(pool) < 10:
            unavailable += 1
            counts.update(target)
            continue
        for name in variants:
            if name != "original_top_combinations" and not frequency:
                continue
            selected = _select(pool, name, top6, frequency)
            top10_hits = _best_hits(selected, target, 10)
            top20_hits = _best_hits(selected, target, min(20, len(selected)))
            if top10_hits is None:
                continue
            variants[name]["records_evaluated"] += 1
            variants[name]["best_hits_top10"].append(float(top10_hits))
            if top20_hits is not None:
                variants[name]["best_hits_top20"].append(float(top20_hits))
            combos = [row["numbers"] for row in selected[:10]]
            variants[name]["average_pairwise_jaccard"].append(_avg_jaccard(combos))
            variants[name]["unique_numbers_covered"].append(float(len(set(number for combo in combos for number in combo))))
            original_score = _avg([combo_score(row) for row in pool[:10]]) or 0.0
            selected_score = _avg([float(row["score"]) for row in selected[:10]]) or 0.0
            variants[name]["score_loss_proxy"].append(round(original_score - selected_score, 6))
        counts.update(target)
    original_raw = variants["original_top_combinations"]
    summarized = {name: _summarize(raw, original_raw if name != "original_top_combinations" else None) for name, raw in variants.items()}
    improvements = [row["repair_improves_best_of_n"] for name, row in summarized.items() if name != "original_top_combinations"]
    available = any(row["records_evaluated"] for row in summarized.values()) and unavailable < len(records)
    return {
        "version": VERSION,
        "generated_at": utc_now(),
        "input_source": replay_memory,
        "input_state": input_state,
        "combination_repair_available": available,
        "records_evaluated": max((row["records_evaluated"] for row in summarized.values()), default=0),
        "variants": summarized,
        "summary": {
            "combination_issue_confirmed": True,
            "existing_pool_can_help": any(improvements),
            "records_without_pool": unavailable,
            "recommendation": "diagnostic_only",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run diagnostic combination repair experiment.")
    parser.add_argument("--replay-memory", default="v4_replay_memory.json")
    parser.add_argument("--output", default="v4_combination_repair_experiment.json")
    args = parser.parse_args()
    report = build_combination_repair(args.replay_memory)
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {args.output}; available={report['combination_repair_available']}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
