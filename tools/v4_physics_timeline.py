# -*- coding: utf-8 -*-
"""Build a simple diagnostic timeline from sphere weight history."""

from __future__ import annotations

import argparse
import json
import math
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VERSION = "V4.4-physics-timeline"
BLOCKS = {
    "1_21": range(1, 22),
    "22_32": range(22, 33),
    "33_56": range(33, 57),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_int(value: Any) -> int | None:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None


def _weights(record: dict[str, Any]) -> dict[int, float]:
    raw = record.get("weights_grams") or {}
    if not isinstance(raw, dict):
        return {}
    weights: dict[int, float] = {}
    for key, value in raw.items():
        number = _parse_int(key)
        try:
            weight = float(value)
        except (TypeError, ValueError):
            continue
        if number is not None and 1 <= number <= 56:
            weights[number] = weight
    return weights


def _winning(record: dict[str, Any]) -> list[int]:
    raw = record.get("winning_numbers") or []
    if not isinstance(raw, list):
        return []
    numbers = []
    for value in raw:
        parsed = _parse_int(value)
        if parsed is not None and 1 <= parsed <= 56 and parsed not in numbers:
            numbers.append(parsed)
    return sorted(numbers)


def _mean(values: list[float]) -> float:
    return round(statistics.fmean(values), 6) if values else 0.0


def _std(values: list[float]) -> float:
    return round(statistics.pstdev(values), 6) if len(values) > 1 else 0.0


def _block_for(number: int) -> str:
    for name, numbers in BLOCKS.items():
        if number in numbers:
            return name
    return "unknown"


def record_metrics(record: dict[str, Any]) -> dict[str, Any]:
    weights = _weights(record)
    winners = _winning(record)
    values = [weights[number] for number in sorted(weights)]
    global_mean = _mean(values)
    global_std = _std(values)
    winner_values = [weights[number] for number in winners if number in weights]
    block_values = {
        name: [weights[number] for number in numbers if number in weights]
        for name, numbers in BLOCKS.items()
    }
    winner_blocks = {name: 0 for name in BLOCKS}
    for number in winners:
        block = _block_for(number)
        if block in winner_blocks:
            winner_blocks[block] += 1
    return {
        "draw_id": record.get("draw_id"),
        "game_mode": record.get("game_mode"),
        "status": record.get("status") or "observed_weight_record",
        "global_mean_weight": global_mean,
        "global_std_weight": global_std,
        "block_1_21_mean": _mean(block_values["1_21"]),
        "block_1_21_std": _std(block_values["1_21"]),
        "block_22_32_mean": _mean(block_values["22_32"]),
        "block_22_32_std": _std(block_values["22_32"]),
        "block_33_56_mean": _mean(block_values["33_56"]),
        "block_33_56_std": _std(block_values["33_56"]),
        "block_33_56_minus_global": round(_mean(block_values["33_56"]) - global_mean, 6),
        "winner_mean_weight": _mean(winner_values),
        "winner_vs_global_delta": round(_mean(winner_values) - global_mean, 6),
        "winner_block_distribution": winner_blocks,
        "weights_count": len(weights),
    }


def _shift(previous: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    mean_shifts = {
        "block_1_21": round(current["block_1_21_mean"] - previous["block_1_21_mean"], 6),
        "block_22_32": round(current["block_22_32_mean"] - previous["block_22_32_mean"], 6),
        "block_33_56": round(current["block_33_56_mean"] - previous["block_33_56_mean"], 6),
    }
    largest_block = max(mean_shifts.items(), key=lambda item: abs(item[1]))
    global_mean_shift = round(current["global_mean_weight"] - previous["global_mean_weight"], 6)
    high_std_shift = round(current["block_33_56_std"] - previous["block_33_56_std"], 6)
    suspected = abs(global_mean_shift) >= 0.03 or abs(largest_block[1]) >= 0.04 or abs(high_std_shift) >= 0.025
    return {
        "from_draw": previous["draw_id"],
        "to_draw": current["draw_id"],
        "game_mode": current.get("game_mode"),
        "global_mean_shift": global_mean_shift,
        "global_std_shift": round(current["global_std_weight"] - previous["global_std_weight"], 6),
        "block_1_21_mean_shift": mean_shifts["block_1_21"],
        "block_22_32_mean_shift": mean_shifts["block_22_32"],
        "block_33_56_mean_shift": mean_shifts["block_33_56"],
        "block_33_56_std_shift": high_std_shift,
        "largest_block_shift": {"block": largest_block[0], "delta": largest_block[1]},
        "uniformity_shift": round(previous["block_33_56_std"] - current["block_33_56_std"], 6),
        "suspected_shift": bool(suspected),
    }


def _event_summary(timeline: list[dict[str, Any]], shifts: list[dict[str, Any]]) -> dict[str, Any]:
    records_count = len(timeline)
    events = [row for row in timeline if row.get("status") == "suspected_physics_event_not_confirmed"]
    events.extend(row for row in shifts if row.get("suspected_shift"))
    if records_count < 5:
        reason = "Se requieren al menos 5 registros de pesos para shifts preliminares."
        can_estimate = False
        preliminary = False
        changepoint = False
    elif records_count < 10:
        reason = "Hay registros suficientes para shifts simples, pero no para periodicidad."
        can_estimate = False
        preliminary = False
        changepoint = False
    elif records_count < 20:
        reason = "Puede revisarse tendencia simple; periodicidad sigue preliminar."
        can_estimate = False
        preliminary = True
        changepoint = False
    else:
        reason = "Historial suficiente para evaluar metodos de changepoint en un PR futuro."
        can_estimate = True
        preliminary = True
        changepoint = True
    return {
        "events_detected_count": len(events),
        "latest_event_draw": events[-1].get("to_draw") or events[-1].get("draw_id") if events else None,
        "can_estimate_periodicity": can_estimate,
        "preliminary_periodicity_possible": preliminary,
        "eligible_for_future_changepoint_methods": changepoint,
        "reason": reason,
    }


def build_timeline(weights_path: str | Path) -> dict[str, Any]:
    path = Path(weights_path)
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"records": []}
    records = data.get("records") if isinstance(data, dict) else []
    if not isinstance(records, list):
        records = []
    valid = [record for record in records if isinstance(record, dict) and len(_weights(record)) == 56]
    valid.sort(key=lambda row: (_parse_int(row.get("draw_id")) or 0, str(row.get("game_mode") or "")))
    timeline = [record_metrics(record) for record in valid]
    shifts = [_shift(timeline[index - 1], timeline[index]) for index in range(1, len(timeline))]
    return {
        "version": VERSION,
        "generated_at": _utc_now(),
        "source_file": str(path),
        "records_count": len(timeline),
        "latest_draw": timeline[-1]["draw_id"] if timeline else None,
        "timeline": timeline,
        "shifts": shifts,
        "event_summary": _event_summary(timeline, shifts),
        "recommendation": "diagnostic_only",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build physics regime timeline.")
    parser.add_argument("--weights", default="sphere_weight_history.json")
    parser.add_argument("--output", default="v4_physics_regime_timeline.json")
    args = parser.parse_args()
    report = build_timeline(args.weights)
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {args.output}; records={report['records_count']}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
