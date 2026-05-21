# -*- coding: utf-8 -*-
"""Lite diagnostic benchmark for replay memory.

The benchmark is intentionally read-only. It never updates replay memory,
resultados.json, or any prior state.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MAX_NUMBER = 56
DRAW_SIZE = 6
VERSION = "V4.4-baseline-benchmark-lite"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_int(value: Any) -> int | None:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None


def _target_numbers(record: dict[str, Any]) -> list[int]:
    raw = record.get("target_numbers") or []
    if not isinstance(raw, list):
        return []
    numbers: list[int] = []
    for value in raw:
        parsed = _parse_int(value)
        if parsed is not None and 1 <= parsed <= MAX_NUMBER and parsed not in numbers:
            numbers.append(parsed)
    return sorted(numbers)


def _combo_numbers(row: Any) -> list[int]:
    if isinstance(row, dict):
        raw = row.get("numbers") or []
    else:
        raw = row
    if not isinstance(raw, list):
        return []
    numbers: list[int] = []
    for value in raw:
        parsed = _parse_int(value)
        if parsed is not None and 1 <= parsed <= MAX_NUMBER and parsed not in numbers:
            numbers.append(parsed)
    return sorted(numbers) if len(numbers) == DRAW_SIZE else []


def _score_rows(record: dict[str, Any]) -> list[dict[str, Any]]:
    errors = record.get("number_score_errors") or {}
    if not isinstance(errors, dict):
        return []
    rows = []
    for number_text, row in errors.items():
        number = _parse_int(number_text)
        if number is None or not (1 <= number <= MAX_NUMBER) or not isinstance(row, dict):
            continue
        try:
            score = float(row.get("predicted_score"))
        except (TypeError, ValueError):
            continue
        rows.append({"number": number, "score": score, "appeared": bool(row.get("appeared"))})
    return sorted(rows, key=lambda item: (-item["score"], item["number"]))


def _valid_records(memory: dict[str, Any]) -> list[dict[str, Any]]:
    records = memory.get("records") if isinstance(memory, dict) else []
    if not isinstance(records, list):
        return []
    valid = []
    for record in records:
        if not isinstance(record, dict):
            continue
        if record.get("record_type") != "historical_replay":
            continue
        if record.get("leakage_passed") is not True:
            continue
        if not _target_numbers(record) or not _score_rows(record):
            continue
        valid.append(record)
    return sorted(valid, key=lambda row: (_parse_int(row.get("target_draw")) or 0, str(row.get("target_draw"))))


def _hit_rate_for_band(records: list[dict[str, Any]], k: int) -> float:
    predicted = 0
    hits = 0
    for record in records:
        rows = _score_rows(record)[:k]
        predicted += len(rows)
        hits += sum(1 for row in rows if row["appeared"])
    return round(hits / predicted, 6) if predicted else 0.0


def _best_hits_top10(record: dict[str, Any]) -> int:
    target = set(_target_numbers(record))
    combos = record.get("top_combinations") or []
    if not isinstance(combos, list):
        return 0
    best = 0
    for combo in combos[:10]:
        numbers = _combo_numbers(combo)
        if numbers:
            best = max(best, len(set(numbers) & target))
    return best


def _cruncher_metrics(records: list[dict[str, Any]]) -> dict[str, float]:
    if not records:
        return {
            "top6_hit_rate": 0.0,
            "top10_hit_rate": 0.0,
            "top20_hit_rate": 0.0,
            "best_hits_top10_avg": 0.0,
        }
    return {
        "top6_hit_rate": _hit_rate_for_band(records, 6),
        "top10_hit_rate": _hit_rate_for_band(records, 10),
        "top20_hit_rate": _hit_rate_for_band(records, 20),
        "best_hits_top10_avg": round(sum(_best_hits_top10(record) for record in records) / len(records), 6),
    }


def _random_baseline(records_count: int) -> dict[str, Any]:
    hit_rate = DRAW_SIZE / MAX_NUMBER
    return {
        "available": True,
        "records_count": records_count,
        "hit_rate_per_number": round(hit_rate, 6),
        "random_expected_hits_top6": round(6 * hit_rate, 6),
        "random_expected_hits_top10": round(10 * hit_rate, 6),
        "random_expected_hits_top20": round(20 * hit_rate, 6),
    }


def _frequency_baseline(records: list[dict[str, Any]]) -> dict[str, Any]:
    if len(records) < 3:
        return {"available": False, "reason": "Replay memory does not contain enough prior target draws for frequency baseline."}
    counts: Counter[int] = Counter()
    evaluated = 0
    hit_totals = {6: 0, 10: 0, 20: 0}
    prediction_totals = {6: 0, 10: 0, 20: 0}
    for record in records:
        target = set(_target_numbers(record))
        if counts:
            ranked = [number for number, _ in counts.most_common(MAX_NUMBER)]
            ranked.extend(number for number in range(1, MAX_NUMBER + 1) if number not in counts)
            for k in hit_totals:
                picks = ranked[:k]
                hit_totals[k] += len(set(picks) & target)
                prediction_totals[k] += len(picks)
            evaluated += 1
        counts.update(target)
    if evaluated < 2:
        return {"available": False, "reason": "Frequency baseline needs at least two evaluable prior draws."}
    return {
        "available": True,
        "records_evaluated": evaluated,
        "top6_hit_rate": round(hit_totals[6] / prediction_totals[6], 6),
        "top10_hit_rate": round(hit_totals[10] / prediction_totals[10], 6),
        "top20_hit_rate": round(hit_totals[20] / prediction_totals[20], 6),
        "frequency_baseline_hits": round(hit_totals[10] / evaluated, 6),
    }


def _recency_baseline(records: list[dict[str, Any]]) -> dict[str, Any]:
    if len(records) < 2:
        return {"available": False, "reason": "Replay memory does not contain enough sequential target draws for recency baseline."}
    evaluated = 0
    top6_hits = 0
    previous: list[int] | None = None
    for record in records:
        target = set(_target_numbers(record))
        if previous:
            top6_hits += len(set(previous[:6]) & target)
            evaluated += 1
        previous = _target_numbers(record)
    if not evaluated:
        return {"available": False, "reason": "Recency baseline has no evaluable previous draw."}
    return {
        "available": True,
        "records_evaluated": evaluated,
        "top6_hit_rate": round(top6_hits / (evaluated * 6), 6),
        "recency_baseline_hits": round(top6_hits / evaluated, 6),
    }


def _summary(records_count: int, cruncher: dict[str, float], baselines: dict[str, Any]) -> dict[str, str]:
    if records_count < 30:
        return {
            "signal_quality": "unknown",
            "recommendation": "diagnostic_only",
            "reason": "Se requieren al menos 30 replay records para comparar contra baselines.",
        }
    random_rate = baselines["random_uniform"]["hit_rate_per_number"]
    frequency_rate = baselines["frequency_baseline"].get("top10_hit_rate") if baselines["frequency_baseline"].get("available") else None
    reference = max(value for value in (random_rate, frequency_rate or 0.0) if value is not None)
    edge = cruncher["top10_hit_rate"] - reference
    if edge >= 0.05:
        quality = "strong"
    elif edge >= 0.02:
        quality = "moderate"
    elif edge > 0:
        quality = "weak"
    else:
        quality = "weak"
    reason = "Benchmark diagnostico: no activa prior."
    if edge <= 0:
        reason = "El top10 del cruncher no supera claramente el baseline disponible."
    return {"signal_quality": quality, "recommendation": "diagnostic_only", "reason": reason}


def build_benchmark(memory_path: str | Path) -> dict[str, Any]:
    path = Path(memory_path)
    if not path.exists():
        records: list[dict[str, Any]] = []
        input_status = "missing"
    else:
        memory = json.loads(path.read_text(encoding="utf-8"))
        records = _valid_records(memory)
        input_status = "loaded"

    cruncher = _cruncher_metrics(records)
    baselines = {
        "random_uniform": _random_baseline(len(records)),
        "frequency_baseline": _frequency_baseline(records),
        "recency_baseline": _recency_baseline(records),
    }
    return {
        "version": VERSION,
        "generated_at": _utc_now(),
        "input_source": str(path),
        "input_status": input_status,
        "records_count": len(records),
        "leakage_passed_count": len(records),
        "baselines": baselines,
        "cruncher_metrics": cruncher,
        "experimental_brier": {
            "enabled": False,
            "reason": "Scores internos no son probabilidades calibradas.",
        },
        "benchmark_summary": _summary(len(records), cruncher, baselines),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build V4.4 lite benchmark from replay memory.")
    parser.add_argument("--replay-memory", default="v4_replay_memory.json")
    parser.add_argument("--output", default="v4_baseline_benchmark.json")
    args = parser.parse_args()

    report = build_benchmark(args.replay_memory)
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {args.output} with {report['records_count']} replay records.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
