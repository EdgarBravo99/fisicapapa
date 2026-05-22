# -*- coding: utf-8 -*-
"""Diagnostic ranking repair experiments for replay records.

The experiment never modifies replay memory, resultados.json, or any prior.
It only tests whether post-ranking ideas would have improved replay outcomes.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from v4_benchmark_hardening import DRAW_SIZE, MAX_NUMBER, load_replay_records, score_rows, target_numbers, utc_now

VERSION = "V4.4-ranking-repair-experiment"
RANDOM_TOP10_HITS = 10 * DRAW_SIZE / MAX_NUMBER
RANDOM_TOP20_HITS = 20 * DRAW_SIZE / MAX_NUMBER


def _avg(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 6) if values else None


def _hits(ranking: list[int], target: set[int], k: int) -> int | None:
    if len(ranking) < k:
        return None
    return len(set(ranking[:k]) & target)


def _jaccard(left: list[int], right: list[int]) -> float:
    union = set(left) | set(right)
    return len(set(left) & set(right)) / len(union) if union else 0.0


def _unique_ranked(numbers: list[int]) -> list[int]:
    output: list[int] = []
    for number in numbers:
        if 1 <= number <= MAX_NUMBER and number not in output:
            output.append(number)
    return output


def _original_rank(record: dict[str, Any]) -> list[int]:
    return [row["number"] for row in score_rows(record)]


def _frequency_rank(counts: Counter[int]) -> list[int]:
    ranked = [number for number, _ in counts.most_common(MAX_NUMBER)]
    ranked.extend(number for number in range(1, MAX_NUMBER + 1) if number not in counts)
    return ranked


def _rank_scores(ranking: list[int]) -> dict[int, float]:
    total = max(len(ranking) - 1, 1)
    return {number: 1.0 - (index / total) for index, number in enumerate(ranking)}


def _score_rank(record: dict[str, Any]) -> dict[int, float]:
    rows = score_rows(record)
    raw = {row["number"]: float(row["score"]) for row in rows}
    if not raw:
        return {}
    low = min(raw.values())
    high = max(raw.values())
    span = high - low or 1.0
    return {number: (score - low) / span for number, score in raw.items()}


def _penalized_rank(record: dict[str, Any], penalty: float) -> list[int]:
    rows = score_rows(record)
    adjusted = []
    for index, row in enumerate(rows, start=1):
        score = float(row["score"])
        if 7 <= index <= 20:
            score *= 1.0 - penalty
        adjusted.append((row["number"], score))
    return [number for number, _ in sorted(adjusted, key=lambda item: (-item[1], item[0]))]


def _hybrid_rank(record: dict[str, Any], counts: Counter[int], cruncher_weight: float) -> list[int]:
    original = _original_rank(record)
    cruncher = _rank_scores(original)
    max_count = max(counts.values(), default=0) or 1
    freq = {number: counts.get(number, 0) / max_count for number in range(1, MAX_NUMBER + 1)}
    blended = {
        number: cruncher_weight * cruncher.get(number, 0.0) + (1.0 - cruncher_weight) * freq.get(number, 0.0)
        for number in range(1, MAX_NUMBER + 1)
    }
    return [number for number, _ in sorted(blended.items(), key=lambda item: (-item[1], item[0]))]


def _variant_rankings(record: dict[str, Any], counts: Counter[int]) -> dict[str, dict[str, Any]]:
    original = _original_rank(record)
    top6 = original[:6]
    variants: dict[str, dict[str, Any]] = {
        "original_cruncher": {"ranking": original, "evaluable": True, "notes": []},
        "top6_only": {"ranking": top6, "evaluable": True, "notes": ["top10/top20 not comparable"]},
        "rank_7_20_penalized_5": {"ranking": _penalized_rank(record, 0.05), "evaluable": True, "notes": ["diagnostic penalty only"]},
        "rank_7_20_penalized_10": {"ranking": _penalized_rank(record, 0.10), "evaluable": True, "notes": ["diagnostic penalty only"]},
        "rank_7_20_penalized_15": {"ranking": _penalized_rank(record, 0.15), "evaluable": True, "notes": ["diagnostic penalty only"]},
    }
    if not counts:
        for name in (
            "top6_preserved_plus_frequency",
            "top6_preserved_plus_frequency_no_duplicates",
            "hybrid_cruncher_frequency_70_30",
            "hybrid_cruncher_frequency_50_50",
            "frequency_only",
        ):
            variants[name] = {"ranking": [], "evaluable": False, "notes": ["not_evaluable_for_frequency"]}
        return variants
    frequency = _frequency_rank(counts)
    variants["top6_preserved_plus_frequency"] = {
        "ranking": top6 + frequency[:14],
        "evaluable": True,
        "notes": ["duplicates may occupy diagnostic slots"],
    }
    variants["top6_preserved_plus_frequency_no_duplicates"] = {
        "ranking": _unique_ranked(top6 + frequency),
        "evaluable": True,
        "notes": ["top6 preserved; frequency fills remaining slots"],
    }
    variants["hybrid_cruncher_frequency_70_30"] = {
        "ranking": _hybrid_rank(record, counts, 0.70),
        "evaluable": True,
        "notes": ["70% cruncher rank, 30% progressive frequency"],
    }
    variants["hybrid_cruncher_frequency_50_50"] = {
        "ranking": _hybrid_rank(record, counts, 0.50),
        "evaluable": True,
        "notes": ["50% cruncher rank, 50% progressive frequency"],
    }
    variants["frequency_only"] = {"ranking": frequency, "evaluable": True, "notes": ["progressive frequency baseline"]}
    return variants


def _empty_variant() -> dict[str, Any]:
    return {
        "records_evaluated": 0,
        "top6_hits": [],
        "top10_hits": [],
        "top20_hits": [],
        "overlap_original": [],
        "overlap_frequency": [],
        "record_results": [],
        "notes": [],
    }


def _summarize(name: str, raw: dict[str, Any], original_avg: float | None, frequency_avg: float | None) -> dict[str, Any]:
    records = raw["records_evaluated"]
    top6_avg = _avg(raw["top6_hits"])
    top10_avg = _avg(raw["top10_hits"])
    top20_avg = _avg(raw["top20_hits"])
    return {
        "records_evaluated": records,
        "top6_avg_hits": top6_avg,
        "top10_avg_hits": top10_avg,
        "top20_avg_hits": top20_avg,
        "top6_hit_rate": round(top6_avg / 6, 6) if top6_avg is not None else None,
        "top10_hit_rate": round(top10_avg / 10, 6) if top10_avg is not None else None,
        "top20_hit_rate": round(top20_avg / 20, 6) if top20_avg is not None else None,
        "beats_random": bool(top10_avg is not None and top10_avg > RANDOM_TOP10_HITS),
        "beats_frequency": bool(top10_avg is not None and frequency_avg is not None and top10_avg > frequency_avg),
        "beats_original": bool(name != "original_cruncher" and top10_avg is not None and original_avg is not None and top10_avg > original_avg),
        "avg_overlap_with_original_top10": _avg(raw["overlap_original"]),
        "avg_overlap_with_frequency_top10": _avg(raw["overlap_frequency"]),
        "rank_monotonicity_proxy": round((top6_avg or 0.0) - ((top20_avg or 0.0) - (top10_avg or 0.0)), 6) if top6_avg is not None else None,
        "notes": sorted(set(raw["notes"])),
        "record_results": raw["record_results"],
    }


def build_ranking_repair_experiment(replay_memory: str = "v4_replay_memory.json") -> dict[str, Any]:
    records, input_state = load_replay_records(replay_memory)
    counts: Counter[int] = Counter()
    raw: dict[str, dict[str, Any]] = {}
    for record in records:
        target = set(target_numbers(record))
        original = _original_rank(record)
        frequency = _frequency_rank(counts) if counts else []
        variants = _variant_rankings(record, counts)
        target_draw = record.get("target_draw")
        for name, payload in variants.items():
            raw.setdefault(name, _empty_variant())
            if not payload["evaluable"]:
                raw[name]["notes"].extend(payload["notes"])
                continue
            ranking = payload["ranking"]
            raw[name]["records_evaluated"] += 1
            raw[name]["notes"].extend(payload["notes"])
            top6_hits = _hits(ranking, target, 6)
            top10_hits = _hits(ranking, target, 10)
            top20_hits = _hits(ranking, target, 20)
            if top6_hits is not None:
                raw[name]["top6_hits"].append(float(top6_hits))
            if top10_hits is not None:
                raw[name]["top10_hits"].append(float(top10_hits))
            if top20_hits is not None:
                raw[name]["top20_hits"].append(float(top20_hits))
            raw[name]["overlap_original"].append(_jaccard(ranking[:10], original[:10]))
            if frequency:
                raw[name]["overlap_frequency"].append(_jaccard(ranking[:10], frequency[:10]))
            raw[name]["record_results"].append(
                {
                    "target_draw": target_draw,
                    "top6_hits": top6_hits,
                    "top10_hits": top10_hits,
                    "top20_hits": top20_hits,
                    "ranking_top20": ranking[:20],
                }
            )
        counts.update(target)
    original_avg = _avg(raw.get("original_cruncher", {}).get("top10_hits", []))
    frequency_avg = _avg(raw.get("frequency_only", {}).get("top10_hits", []))
    variants = {name: _summarize(name, payload, original_avg, frequency_avg) for name, payload in raw.items()}
    comparable = {
        name: row
        for name, row in variants.items()
        if name not in ("original_cruncher", "random_expected") and row.get("top10_avg_hits") is not None
    }
    best_name = max(comparable, key=lambda name: comparable[name]["top10_avg_hits"], default=None)
    best_variant = {
        "name": best_name,
        "reason": "highest diagnostic top10 average among repair variants" if best_name else "no comparable repair variant",
    }
    improves = any(row["beats_original"] for row in comparable.values())
    beats_freq = any(row["beats_frequency"] for row in comparable.values())
    beats_random = any(row["beats_random"] for row in comparable.values())
    variants["random_expected"] = {
        "records_evaluated": len(records),
        "top6_avg_hits": 6 * DRAW_SIZE / MAX_NUMBER,
        "top10_avg_hits": RANDOM_TOP10_HITS,
        "top20_avg_hits": RANDOM_TOP20_HITS,
        "beats_random": False,
        "beats_frequency": False,
        "beats_original": False,
        "notes": ["theoretical random expectation"],
    }
    return {
        "version": VERSION,
        "generated_at": utc_now(),
        "input_source": replay_memory,
        "input_state": input_state,
        "records_count": len(records),
        "records_evaluated": max((row.get("records_evaluated", 0) for row in variants.values()), default=0),
        "mode": "diagnostic_only",
        "variants": variants,
        "best_variant": best_variant,
        "summary": {
            "ranking_repair_improves_original": improves,
            "ranking_repair_beats_frequency": beats_freq,
            "ranking_repair_beats_random": beats_random,
            "eligible_for_future_experiment": False,
            "recommendation": "diagnostic_only",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run diagnostic ranking repair experiments.")
    parser.add_argument("--replay-memory", default="v4_replay_memory.json")
    parser.add_argument("--output", default="v4_ranking_repair_experiment.json")
    args = parser.parse_args()
    report = build_ranking_repair_experiment(args.replay_memory)
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {args.output}; best_variant={report['best_variant']['name']}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
