# -*- coding: utf-8 -*-
"""Read-only physics regime audit for sphere weight history."""

from __future__ import annotations

import argparse
import json
import math
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VERSION = "V4.4-physics-regime-audit"
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


def _winning_numbers(record: dict[str, Any]) -> list[int]:
    raw = record.get("winning_numbers") or []
    if not isinstance(raw, list):
        return []
    numbers: list[int] = []
    for value in raw:
        parsed = _parse_int(value)
        if parsed is not None and 1 <= parsed <= 56 and parsed not in numbers:
            numbers.append(parsed)
    return sorted(numbers)


def _mean(values: list[float]) -> float:
    return round(statistics.fmean(values), 6) if values else 0.0


def _std(values: list[float]) -> float:
    return round(statistics.pstdev(values), 6) if len(values) > 1 else 0.0


def _block_for_number(number: int) -> str:
    for name, numbers in BLOCKS.items():
        if number in numbers:
            return name
    return "unknown"


def _record_metrics(record: dict[str, Any]) -> dict[str, Any]:
    weights = _weights(record)
    winners = _winning_numbers(record)
    values = [weights[number] for number in sorted(weights)]
    global_mean = _mean(values)
    global_std = _std(values)
    winner_values = [weights[number] for number in winners if number in weights]
    blocks: dict[str, dict[str, Any]] = {}
    for name, numbers in BLOCKS.items():
        block_values = [weights[number] for number in numbers if number in weights]
        blocks[name] = {
            "mean": _mean(block_values),
            "std": _std(block_values),
            "count": len(block_values),
        }

    z_scores = {}
    for number, weight in weights.items():
        z_scores[str(number)] = 0.0 if math.isclose(global_std, 0.0) else round((weight - global_mean) / global_std, 6)
    max_z_number, max_z = max(z_scores.items(), key=lambda item: abs(item[1])) if z_scores else ("N/D", 0.0)
    winner_blocks = {name: 0 for name in BLOCKS}
    for number in winners:
        block = _block_for_number(number)
        if block in winner_blocks:
            winner_blocks[block] += 1

    high_block = blocks["33_56"]
    high_minus_global = round(high_block["mean"] - global_mean, 6)
    uniformity = 0.0
    if global_std:
        uniformity = round(max(0.0, (global_std - high_block["std"]) / global_std), 6)

    return {
        "draw_id": record.get("draw_id"),
        "game_mode": record.get("game_mode"),
        "global_mean_weight": global_mean,
        "global_std_weight": global_std,
        "winner_mean_weight": _mean(winner_values),
        "winner_vs_global_delta": round(_mean(winner_values) - global_mean, 6),
        "block_1_21_mean": blocks["1_21"]["mean"],
        "block_1_21_std": blocks["1_21"]["std"],
        "block_22_32_mean": blocks["22_32"]["mean"],
        "block_22_32_std": blocks["22_32"]["std"],
        "block_33_56_mean": high_block["mean"],
        "block_33_56_std": high_block["std"],
        "block_33_56_minus_global": high_minus_global,
        "block_33_56_uniformity_score": uniformity,
        "max_ball_z_score": {"number": max_z_number, "z_score": max_z},
        "winner_block_distribution": winner_blocks,
        "blocks": blocks,
        "weights_count": len(weights),
    }


def _event_from_latest(record: dict[str, Any], metrics: dict[str, Any], records_count: int) -> dict[str, Any]:
    suspected = record.get("status") == "suspected_physics_event_not_confirmed"
    evidence = []
    if metrics["block_33_56_minus_global"] > 0:
        evidence.append("33-56 tiene mayor peso promedio que el global.")
    if metrics["block_33_56_std"] <= metrics["global_std_weight"]:
        evidence.append("33-56 tiene desviacion estandar menor o igual que la global.")
    high_winners = metrics["winner_block_distribution"].get("33_56", 0)
    evidence.append(f"{high_winners} numeros ganadores caen dentro del bloque 33-56.")

    severity = "low"
    if suspected and metrics["block_33_56_minus_global"] >= 0.04 and high_winners >= 2:
        severity = "medium"
    if suspected and metrics["block_33_56_minus_global"] >= 0.06 and high_winners >= 3:
        severity = "high"

    return {
        "suspected": bool(suspected),
        "draw_id": record.get("draw_id"),
        "type": "high_block_uniformity_shift" if suspected else "none",
        "severity": severity,
        "status": "hypothesis_not_confirmed",
        "evidence": evidence,
        "manual_observation": record.get("manual_observation") or "",
        "records_available": records_count,
    }


def build_analysis(weights_path: str | Path) -> dict[str, Any]:
    path = Path(weights_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    records = data.get("records") if isinstance(data, dict) else []
    if not isinstance(records, list):
        records = []
    valid_records = [record for record in records if isinstance(record, dict) and len(_weights(record)) == 56]
    latest = max(valid_records, key=lambda row: _parse_int(row.get("draw_id")) or 0) if valid_records else {}
    latest_metrics = _record_metrics(latest) if latest else {}
    can_estimate = len(valid_records) >= 5
    return {
        "version": VERSION,
        "generated_at": _utc_now(),
        "source_file": str(path),
        "records_count": len(valid_records),
        "latest_draw": latest.get("draw_id"),
        "latest_event": _event_from_latest(latest, latest_metrics, len(valid_records)) if latest else {
            "suspected": False,
            "status": "no_valid_weight_records",
            "evidence": [],
        },
        "latest_metrics": latest_metrics,
        "blocks": latest_metrics.get("blocks", {}),
        "regime_timing": {
            "can_estimate_periodicity": can_estimate,
            "reason": "Se requiere historial de pesos de multiples sorteos." if not can_estimate else "Historial suficiente para iniciar estimacion simple.",
            "estimated_regime_lengths": [],
            "mean_regime_length": None,
        },
        "recommendation": "diagnostic_only",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build V4.4 physics regime diagnostic.")
    parser.add_argument("--weights", default="sphere_weight_history.json")
    parser.add_argument("--output", default="v4_physics_regime_analysis.json")
    args = parser.parse_args()

    report = build_analysis(args.weights)
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {args.output} for latest draw {report.get('latest_draw')}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
