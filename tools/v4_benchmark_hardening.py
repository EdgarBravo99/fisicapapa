# -*- coding: utf-8 -*-
"""Harden replay benchmark diagnostics without applying any prior."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MAX_NUMBER = 56
DRAW_SIZE = 6
VERSION = "V4.4-benchmark-hardening"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_int(value: Any) -> int | None:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None


def target_numbers(record: dict[str, Any]) -> list[int]:
    raw = record.get("target_numbers") or []
    if not isinstance(raw, list):
        return []
    numbers: list[int] = []
    for value in raw:
        parsed = parse_int(value)
        if parsed is not None and 1 <= parsed <= MAX_NUMBER and parsed not in numbers:
            numbers.append(parsed)
    return sorted(numbers)


def combo_numbers(row: Any) -> list[int]:
    raw = row.get("numbers") if isinstance(row, dict) else row
    if not isinstance(raw, list):
        return []
    numbers: list[int] = []
    for value in raw:
        parsed = parse_int(value)
        if parsed is not None and 1 <= parsed <= MAX_NUMBER and parsed not in numbers:
            numbers.append(parsed)
    return sorted(numbers) if len(numbers) == DRAW_SIZE else []


def combo_score(row: Any) -> float:
    if not isinstance(row, dict):
        return 0.0
    for key in ("score_percent", "original_score", "score_reference", "net_score", "score", "confidence"):
        try:
            value = float(row.get(key))
        except (TypeError, ValueError):
            continue
        return value * 100 if key == "net_score" and 0 <= value <= 1 else value
    return 0.0


def score_rows(record: dict[str, Any]) -> list[dict[str, Any]]:
    errors = record.get("number_score_errors") or {}
    if not isinstance(errors, dict):
        return []
    rows = []
    for number_text, row in errors.items():
        number = parse_int(number_text)
        if number is None or not (1 <= number <= MAX_NUMBER) or not isinstance(row, dict):
            continue
        try:
            score = float(row.get("predicted_score"))
        except (TypeError, ValueError):
            continue
        rows.append({"number": number, "score": score, "appeared": bool(row.get("appeared"))})
    return sorted(rows, key=lambda item: (-item["score"], item["number"]))


def load_replay_records(path: str | Path = "v4_replay_memory.json") -> tuple[list[dict[str, Any]], dict[str, Any]]:
    replay_path = Path(path)
    if not replay_path.exists():
        return [], {"available": False, "reason": "missing replay memory", "path": str(replay_path)}
    try:
        memory = json.loads(replay_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [], {"available": False, "reason": f"invalid json: {exc}", "path": str(replay_path)}
    records = memory.get("records") if isinstance(memory, dict) else []
    if not isinstance(records, list):
        return [], {"available": False, "reason": "records is not a list", "path": str(replay_path)}
    valid = []
    for record in records:
        if not isinstance(record, dict):
            continue
        if record.get("record_type") != "historical_replay":
            continue
        if record.get("leakage_passed") is not True:
            continue
        if not target_numbers(record) or not score_rows(record):
            continue
        valid.append(record)
    valid.sort(key=lambda row: (parse_int(row.get("target_draw")) or 0, str(row.get("target_draw") or "")))
    return valid, {"available": True, "path": str(replay_path), "raw_records_count": len(records)}


def topk_hits(record: dict[str, Any], k: int) -> int:
    return sum(1 for row in score_rows(record)[:k] if row["appeared"])


def topk_hit_rate(records: list[dict[str, Any]], k: int) -> float:
    predicted = sum(min(k, len(score_rows(record))) for record in records)
    if not predicted:
        return 0.0
    hits = sum(topk_hits(record, k) for record in records)
    return round(hits / predicted, 6)


def best_hits(record: dict[str, Any], limit: int) -> int:
    target = set(target_numbers(record))
    combos = record.get("top_combinations") or []
    if not isinstance(combos, list):
        return 0
    best = 0
    for combo in combos[:limit]:
        numbers = combo_numbers(combo)
        if numbers:
            best = max(best, len(set(numbers) & target))
    return best


def avg(values: list[float]) -> float:
    return round(sum(values) / len(values), 6) if values else 0.0


def random_expected_hits(k: int) -> float:
    return round(k * DRAW_SIZE / MAX_NUMBER, 6)


def frequency_baseline(records: list[dict[str, Any]], k: int = 10) -> dict[str, Any]:
    if len(records) < 3:
        return {"available": False, "reason": "insufficient data"}
    counts: Counter[int] = Counter()
    hits = 0
    evaluated = 0
    for record in records:
        target = set(target_numbers(record))
        if counts:
            ranked = [number for number, _ in counts.most_common(MAX_NUMBER)]
            ranked.extend(number for number in range(1, MAX_NUMBER + 1) if number not in counts)
            hits += len(set(ranked[:k]) & target)
            evaluated += 1
        counts.update(target)
    if evaluated < 2:
        return {"available": False, "reason": "insufficient prior draws"}
    return {"available": True, "records_evaluated": evaluated, "k": k, "average_hits": round(hits / evaluated, 6)}


def recency_baseline(records: list[dict[str, Any]], k: int = 10) -> dict[str, Any]:
    if len(records) < 2:
        return {"available": False, "reason": "insufficient data"}
    previous: list[int] | None = None
    hits = 0
    evaluated = 0
    for record in records:
        target = set(target_numbers(record))
        if previous:
            picks = previous[:k]
            hits += len(set(picks) & target)
            evaluated += 1
        previous = target_numbers(record)
    if not evaluated:
        return {"available": False, "reason": "no evaluable previous draw"}
    return {"available": True, "records_evaluated": evaluated, "k": min(k, DRAW_SIZE), "average_hits": round(hits / evaluated, 6)}


def record_edges(records: list[dict[str, Any]]) -> list[dict[str, float]]:
    rows = []
    counts: Counter[int] = Counter()
    previous: list[int] | None = None
    for record in records:
        cruncher_hits = topk_hits(record, 10)
        random_hits = random_expected_hits(10)
        target = set(target_numbers(record))
        freq_hits = None
        if counts:
            ranked = [number for number, _ in counts.most_common(MAX_NUMBER)]
            ranked.extend(number for number in range(1, MAX_NUMBER + 1) if number not in counts)
            freq_hits = len(set(ranked[:10]) & target)
        recency_hits = len(set(previous[:6]) & target) if previous else None
        rows.append(
            {
                "cruncher_hits_top10": float(cruncher_hits),
                "random_hits_top10": float(random_hits),
                "frequency_hits_top10": float(freq_hits) if freq_hits is not None else None,
                "recency_hits_top6": float(recency_hits) if recency_hits is not None else None,
                "cruncher_minus_random": round(cruncher_hits - random_hits, 6),
                "cruncher_minus_frequency": round(cruncher_hits - freq_hits, 6) if freq_hits is not None else None,
                "cruncher_minus_recency": round(cruncher_hits - recency_hits, 6) if recency_hits is not None else None,
            }
        )
        counts.update(target)
        previous = target_numbers(record)
    return rows


def build_hardening(replay_memory: str | Path = "v4_replay_memory.json") -> dict[str, Any]:
    records, input_state = load_replay_records(replay_memory)
    records_count = len(records)
    cruncher_top10_hits = avg([topk_hits(record, 10) for record in records])
    freq = frequency_baseline(records, 10)
    recency = recency_baseline(records, 10)
    random_hits = random_expected_hits(10)
    return {
        "version": VERSION,
        "generated_at": utc_now(),
        "input_source": str(replay_memory),
        "input_state": input_state,
        "records_count": records_count,
        "leakage_passed_count": records_count,
        "cruncher_top6_hit_rate": topk_hit_rate(records, 6),
        "cruncher_top10_hit_rate": topk_hit_rate(records, 10),
        "cruncher_top20_hit_rate": topk_hit_rate(records, 20),
        "best_hits_top10_avg": avg([best_hits(record, 10) for record in records]),
        "best_hits_top20_avg": avg([best_hits(record, 20) for record in records]),
        "random_expected_hits": random_hits,
        "frequency_baseline_hits": freq,
        "recency_baseline_hits": recency,
        "cruncher_minus_random": round(cruncher_top10_hits - random_hits, 6) if records else 0.0,
        "cruncher_minus_frequency": round(cruncher_top10_hits - freq["average_hits"], 6) if freq.get("available") else None,
        "cruncher_minus_recency": round(cruncher_top10_hits - recency["average_hits"], 6) if recency.get("available") else None,
        "record_edges": record_edges(records),
        "recommendation": "diagnostic_only",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build hardened benchmark diagnostics.")
    parser.add_argument("--replay-memory", default="v4_replay_memory.json")
    parser.add_argument("--output", default="v4_benchmark_hardening.json")
    args = parser.parse_args()
    report = build_hardening(args.replay_memory)
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {args.output}; records={report['records_count']}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
