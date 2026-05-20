# -*- coding: utf-8 -*-
"""Replay-memory helpers for Fisicapapa V4.3.2.

Replay memory is separate from live feedback memory. It grades predictions
generated today by replaying the past with a truncated CSV through the main
engine. By default it only computes a shadow prior and never installs it.
"""

from __future__ import annotations

import json
import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MAX_NUMBER = 56
ENABLE_REPLAY_PRIOR = False
REPLAY_MEMORY_VERSION = "V4.3.2-historical-replay-memory"
MIN_REPLAY_RECORDS_FOR_PRIOR = 30
SCORE_BUCKETS = ("p0_p20", "p20_p40", "p40_p60", "p60_p80", "p80_p90", "p90_p100")
RANK_BANDS = ("top6", "top10", "top20", "top40", "rest")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_int(value: Any) -> int | None:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None


def default_replay_memory() -> dict[str, Any]:
    return {
        "version": REPLAY_MEMORY_VERSION,
        "last_updated": None,
        "records": [],
        "aggregate": {
            "records_count": 0,
            "leakage_passed_count": 0,
            "shadow_prior_available": False,
            "shadow_prior_applied": False,
            "overestimated_numbers": {},
            "underestimated_numbers": {},
            "overestimated_weighted": {},
            "underestimated_weighted": {},
            "score_bucket_performance": {},
            "rank_band_performance": {},
            "calibration_summary": {},
            "quality_notes": [],
        },
    }


def load_replay_memory(path: str | Path = "v4_replay_memory.json") -> dict[str, Any]:
    memory_path = Path(path)
    if not memory_path.exists():
        return default_replay_memory()
    data = json.loads(memory_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Replay memory invalida: {memory_path}")
    data.setdefault("version", REPLAY_MEMORY_VERSION)
    data.setdefault("records", [])
    data.setdefault("aggregate", default_replay_memory()["aggregate"])
    return data


def save_replay_memory(memory: dict[str, Any], path: str | Path = "v4_replay_memory.json") -> None:
    records = memory.get("records")
    if not isinstance(records, list) or not records:
        return
    memory["version"] = REPLAY_MEMORY_VERSION
    memory["last_updated"] = _utc_now()
    memory["aggregate"] = rebuild_replay_aggregate(memory)
    Path(path).write_text(json.dumps(memory, ensure_ascii=False, indent=2), encoding="utf-8")


def _record_key(record: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(record.get("game_mode")),
        str(record.get("prediction_draw")),
        str(record.get("target_draw")),
    )


def _score_to_unit(value: Any) -> float | None:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None
    if 0 <= score <= 1:
        return score
    if 0 <= score <= 100:
        return score / 100.0
    return None


def _score_bucket(percentile: float) -> str:
    if percentile < 0.20:
        return "p0_p20"
    if percentile < 0.40:
        return "p20_p40"
    if percentile < 0.60:
        return "p40_p60"
    if percentile < 0.80:
        return "p60_p80"
    if percentile < 0.90:
        return "p80_p90"
    return "p90_p100"


def _rank_band(rank: int) -> str:
    if rank <= 6:
        return "top6"
    if rank <= 10:
        return "top10"
    if rank <= 20:
        return "top20"
    if rank <= 40:
        return "top40"
    return "rest"


def _empty_bucket_stats() -> dict[str, dict[str, float | int]]:
    return {
        bucket: {"predicted_count": 0, "appeared_count": 0, "hit_rate": 0.0, "avg_score": 0.0}
        for bucket in SCORE_BUCKETS
    }


def _empty_rank_stats() -> dict[str, dict[str, float | int]]:
    return {
        band: {"predicted_count": 0, "appeared_count": 0, "hit_rate": 0.0}
        for band in RANK_BANDS
    }


def normalize_replay_number_rows(record: dict[str, Any]) -> list[dict[str, Any]]:
    """Return normalized per-number replay rows without mutating old records."""
    raw = record.get("number_score_errors")
    if not isinstance(raw, dict):
        return []
    rows = []
    for number_text, item in raw.items():
        if not isinstance(item, dict):
            continue
        number = _parse_int(number_text)
        score = _score_to_unit(item.get("score") or item.get("predicted_score"))
        if number is None or not 1 <= number <= MAX_NUMBER or score is None:
            continue
        rows.append({
            "number": number,
            "score": score,
            "appeared": bool(item.get("appeared")),
            "existing_rank": _parse_int(item.get("rank")),
            "existing_percentile": _score_to_unit(item.get("percentile")),
            "existing_bucket": item.get("bucket") if isinstance(item.get("bucket"), str) else None,
        })
    rows.sort(key=lambda row: (-float(row["score"]), int(row["number"])))
    total = len(rows)
    for index, row in enumerate(rows):
        rank = row["existing_rank"] or index + 1
        percentile = row["existing_percentile"]
        if percentile is None:
            percentile = 1.0 if total <= 1 else (total - rank) / (total - 1)
        row["rank"] = rank
        row["percentile"] = round(float(percentile), 6)
        row["bucket"] = row["existing_bucket"] or _score_bucket(float(percentile))
        del row["existing_rank"]
        del row["existing_percentile"]
        del row["existing_bucket"]
    return rows


def _overestimated_severity(row: dict[str, Any]) -> float:
    if row.get("appeared"):
        return 0.0
    rank = int(row.get("rank") or 999)
    percentile = float(row.get("percentile") or 0)
    bucket = row.get("bucket")
    severity = 0.0
    if rank <= 6:
        severity = max(severity, 1.0)
    elif rank <= 10:
        severity = max(severity, 0.75)
    if percentile >= 0.90:
        severity = max(severity, 0.75)
    elif percentile >= 0.80:
        severity = max(severity, 0.50)
    if bucket in {"p80_p90", "p90_p100"}:
        severity = max(severity, 0.50)
    return severity


def _underestimated_severity(row: dict[str, Any]) -> float:
    if not row.get("appeared"):
        return 0.0
    rank = int(row.get("rank") or 0)
    percentile = float(row.get("percentile") or 1)
    bucket = row.get("bucket")
    severity = 0.0
    if rank > 40:
        severity = max(severity, 1.0)
    elif rank > 30:
        severity = max(severity, 0.75)
    elif rank > 20:
        severity = max(severity, 0.50)
    if percentile <= 0.20:
        severity = max(severity, 1.0)
    elif percentile <= 0.40:
        severity = max(severity, 0.75)
    elif percentile <= 0.50:
        severity = max(severity, 0.50)
    if bucket in {"p0_p20", "p20_p40", "p40_p60"}:
        severity = max(severity, 0.50)
    return severity


def _finalize_bucket_stats(stats: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    finalized = {}
    for key, row in stats.items():
        predicted = int(row.get("predicted_count", 0) or 0)
        appeared = int(row.get("appeared_count", 0) or 0)
        score_sum = float(row.pop("_score_sum", 0) or 0)
        finalized[key] = {
            "predicted_count": predicted,
            "appeared_count": appeared,
            "hit_rate": round(appeared / predicted, 6) if predicted else 0.0,
            "avg_score": round(score_sum / predicted, 6) if predicted else 0.0,
        }
    return finalized


def _finalize_rank_stats(stats: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    finalized = {}
    for key, row in stats.items():
        predicted = int(row.get("predicted_count", 0) or 0)
        appeared = int(row.get("appeared_count", 0) or 0)
        finalized[key] = {
            "predicted_count": predicted,
            "appeared_count": appeared,
            "hit_rate": round(appeared / predicted, 6) if predicted else 0.0,
        }
    return finalized


def _calibration_summary(records_count: int, bucket_stats: dict[str, dict[str, Any]], rank_stats: dict[str, dict[str, Any]]) -> dict[str, Any]:
    top10_hit_rate = (
        (
            rank_stats["top6"]["appeared_count"] + rank_stats["top10"]["appeared_count"]
        )
        / max(1, rank_stats["top6"]["predicted_count"] + rank_stats["top10"]["predicted_count"])
    )
    mid_bucket_hit_rate = (
        bucket_stats["p40_p60"]["appeared_count"]
        / max(1, bucket_stats["p40_p60"]["predicted_count"])
    )
    high_bucket_hit_rate = (
        (bucket_stats["p80_p90"]["appeared_count"] + bucket_stats["p90_p100"]["appeared_count"])
        / max(1, bucket_stats["p80_p90"]["predicted_count"] + bucket_stats["p90_p100"]["predicted_count"])
    )
    if high_bucket_hit_rate <= mid_bucket_hit_rate:
        signal = "weak"
        prior_quality = "diagnostic_only"
        reason = "Buckets altos no superan el hit_rate de buckets medios."
    elif high_bucket_hit_rate >= mid_bucket_hit_rate * 1.25 and top10_hit_rate > mid_bucket_hit_rate:
        signal = "strong"
        prior_quality = "usable_shadow" if records_count >= MIN_REPLAY_RECORDS_FOR_PRIOR else "needs_more_data"
        reason = "Buckets altos y top ranks muestran mejor hit_rate."
    else:
        signal = "moderate"
        prior_quality = "usable_shadow" if records_count >= MIN_REPLAY_RECORDS_FOR_PRIOR else "needs_more_data"
        reason = "Senal replay moderada; mantener como shadow prior."
    if records_count < MIN_REPLAY_RECORDS_FOR_PRIOR:
        prior_quality = "needs_more_data"
        reason = f"Se requieren {MIN_REPLAY_RECORDS_FOR_PRIOR}+ records replay; hay {records_count}."
    return {
        "top10_hit_rate": round(top10_hit_rate, 6),
        "mid_bucket_hit_rate": round(mid_bucket_hit_rate, 6),
        "high_bucket_hit_rate": round(high_bucket_hit_rate, 6),
        "ranking_signal_quality": signal,
        "prior_quality": prior_quality,
        "reason": reason,
    }


def add_replay_records(
    records: list[dict[str, Any]],
    memory_path: str | Path = "v4_replay_memory.json",
    dry_run: bool = False,
) -> dict[str, Any]:
    clean_records = [record for record in records if record.get("record_type") == "historical_replay" and record.get("leakage_passed")]
    if not clean_records:
        return {"changed": False, "records_added": 0, "warnings": ["No hay records replay reales calificables."]}
    memory = load_replay_memory(memory_path)
    existing = {_record_key(record) for record in memory.get("records", []) if isinstance(record, dict)}
    added = []
    for record in clean_records:
        key = _record_key(record)
        if key in existing:
            continue
        memory.setdefault("records", []).append(record)
        existing.add(key)
        added.append(record)
    if added and not dry_run:
        save_replay_memory(memory, memory_path)
    return {"changed": bool(added), "records_added": len(added), "memory": memory}


def rebuild_replay_aggregate(memory: dict[str, Any]) -> dict[str, Any]:
    records = [
        record for record in memory.get("records", [])
        if isinstance(record, dict) and record.get("record_type") == "historical_replay"
    ]
    over: dict[str, int] = {}
    under: dict[str, int] = {}
    over_weighted: dict[str, float] = {}
    under_weighted: dict[str, float] = {}
    bucket_stats = _empty_bucket_stats()
    rank_stats = _empty_rank_stats()
    leakage_passed = 0
    for record in records:
        if record.get("leakage_passed"):
            leakage_passed += 1
        for row in normalize_replay_number_rows(record):
            number_text = str(row["number"])
            bucket = str(row["bucket"])
            band = _rank_band(int(row["rank"]))
            bucket_stats[bucket]["predicted_count"] += 1
            bucket_stats[bucket]["appeared_count"] += 1 if row["appeared"] else 0
            bucket_stats[bucket]["_score_sum"] = float(bucket_stats[bucket].get("_score_sum", 0)) + float(row["score"])
            rank_stats[band]["predicted_count"] += 1
            rank_stats[band]["appeared_count"] += 1 if row["appeared"] else 0
            over_severity = _overestimated_severity(row)
            under_severity = _underestimated_severity(row)
            if over_severity:
                over[number_text] = over.get(number_text, 0) + 1
                over_weighted[number_text] = over_weighted.get(number_text, 0.0) + over_severity
            if under_severity:
                under[number_text] = under.get(number_text, 0) + 1
                under_weighted[number_text] = under_weighted.get(number_text, 0.0) + under_severity
    score_bucket_performance = _finalize_bucket_stats(bucket_stats)
    rank_band_performance = _finalize_rank_stats(rank_stats)
    calibration = _calibration_summary(leakage_passed, score_bucket_performance, rank_band_performance)
    quality_notes = []
    if calibration["prior_quality"] == "diagnostic_only":
        quality_notes.append("Replay prior calculado, pero no confiable todavia.")
    elif calibration["prior_quality"] == "usable_shadow":
        quality_notes.append("Replay prior calculado como shadow prior, no aplicado.")
    return {
        "records_count": len(records),
        "leakage_passed_count": leakage_passed,
        "shadow_prior_available": leakage_passed >= MIN_REPLAY_RECORDS_FOR_PRIOR,
        "shadow_prior_applied": False,
        "overestimated_numbers": dict(sorted(over.items(), key=lambda item: item[1], reverse=True)),
        "underestimated_numbers": dict(sorted(under.items(), key=lambda item: item[1], reverse=True)),
        "overestimated_weighted": {key: round(value, 6) for key, value in sorted(over_weighted.items(), key=lambda item: item[1], reverse=True)},
        "underestimated_weighted": {key: round(value, 6) for key, value in sorted(under_weighted.items(), key=lambda item: item[1], reverse=True)},
        "score_bucket_performance": score_bucket_performance,
        "rank_band_performance": rank_band_performance,
        "calibration_summary": calibration,
        "quality_notes": quality_notes,
    }


def compute_replay_prior(
    memory: dict[str, Any],
    enable_replay_prior: bool = ENABLE_REPLAY_PRIOR,
) -> dict[str, Any]:
    aggregate = rebuild_replay_aggregate(memory)
    records_count = int(aggregate.get("leakage_passed_count") or 0)
    max_adjustment = 0.03 if records_count >= 60 else 0.02
    prior = {
        "mode": "shadow_replay_prior",
        "eligible": records_count >= MIN_REPLAY_RECORDS_FOR_PRIOR,
        "applied": False,
        "enabled": bool(enable_replay_prior),
        "records_used": records_count,
        "max_number_adjustment": max_adjustment,
        "adjustments": {},
        "reason": "Replay prior calculado, no aplicado por defecto.",
        "prior_quality": aggregate.get("calibration_summary", {}).get("prior_quality"),
        "ranking_signal_quality": aggregate.get("calibration_summary", {}).get("ranking_signal_quality"),
    }
    if records_count < MIN_REPLAY_RECORDS_FOR_PRIOR:
        prior.update({
            "eligible": False,
            "reason": f"Replay requiere {MIN_REPLAY_RECORDS_FOR_PRIOR}+ records; hay {records_count}.",
        })
        return prior
    if aggregate.get("calibration_summary", {}).get("prior_quality") != "usable_shadow":
        prior.update({
            "eligible": False,
            "reason": "Replay prior diagnostic only: ranking signal weak or insufficient calibration quality.",
        })
        return prior
    if not enable_replay_prior:
        prior["reason"] = "ENABLE_REPLAY_PRIOR=False; shadow prior no aplicado."
    over = aggregate.get("overestimated_weighted") or {}
    under = aggregate.get("underestimated_weighted") or {}
    for number in range(1, MAX_NUMBER + 1):
        down = float(over.get(str(number), 0) or 0)
        up = float(under.get(str(number), 0) or 0)
        evidence = up - down
        if evidence == 0:
            continue
        scaled = max(-max_adjustment, min(max_adjustment, (evidence / max(1, records_count)) * max_adjustment))
        if scaled:
            prior["adjustments"][str(number)] = round(scaled, 8)
    return prior


def compute_combined_prior(live_prior: dict[str, Any] | None, replay_prior: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "mode": "combined_live_replay_prior",
        "enabled": False,
        "applied": False,
        "weights": {"live": 0.7, "replay": 0.3},
        "live_prior_available": bool(live_prior and live_prior.get("eligible")),
        "replay_prior_available": bool(replay_prior and replay_prior.get("eligible")),
        "reason": "Estructura preparada; no activada por defecto.",
    }


def build_replay_prior_audit(memory: dict[str, Any]) -> dict[str, Any]:
    aggregate = rebuild_replay_aggregate(memory)
    prior = compute_replay_prior(memory)
    return {
        "version": REPLAY_MEMORY_VERSION,
        "mode": prior.get("mode"),
        "shadow_prior_available": bool(prior.get("eligible")),
        "shadow_prior_applied": False,
        "records_replay": aggregate.get("records_count", 0),
        "leakage_passed_count": aggregate.get("leakage_passed_count", 0),
        "max_number_adjustment": prior.get("max_number_adjustment"),
        "prior_quality": aggregate.get("calibration_summary", {}).get("prior_quality"),
        "ranking_signal_quality": aggregate.get("calibration_summary", {}).get("ranking_signal_quality"),
        "top_numbers_down": list((aggregate.get("overestimated_weighted") or {}).items())[:10],
        "top_numbers_up": list((aggregate.get("underestimated_weighted") or {}).items())[:10],
        "reason": prior.get("reason"),
    }


def rebuild_replay_memory_file(path: str | Path = "v4_replay_memory.json") -> dict[str, Any]:
    memory_path = Path(path)
    memory = load_replay_memory(memory_path)
    if not memory.get("records"):
        return {"changed": False, "reason": "No hay records replay; no se escribe memoria vacia."}
    memory["aggregate"] = rebuild_replay_aggregate(memory)
    save_replay_memory(memory, memory_path)
    return {"changed": True, "path": str(memory_path), "aggregate": memory["aggregate"]}


def main() -> None:
    parser = argparse.ArgumentParser(description="Herramientas de replay memory V4.3.3.")
    parser.add_argument("--rebuild", action="store_true", help="Recalcula aggregate de v4_replay_memory.json sin cambiar records.")
    parser.add_argument("--path", default="v4_replay_memory.json")
    args = parser.parse_args()
    if args.rebuild:
        print(json.dumps(rebuild_replay_memory_file(args.path), ensure_ascii=False, indent=2))
    else:
        memory = load_replay_memory(args.path)
        print(json.dumps({"aggregate": rebuild_replay_aggregate(memory)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
