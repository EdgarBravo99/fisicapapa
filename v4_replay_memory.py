# -*- coding: utf-8 -*-
"""Replay-memory helpers for Fisicapapa V4.3.2.

Replay memory is separate from live feedback memory. It grades predictions
generated today by replaying the past with a truncated CSV through the main
engine. By default it only computes a shadow prior and never installs it.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MAX_NUMBER = 56
ENABLE_REPLAY_PRIOR = False
REPLAY_MEMORY_VERSION = "V4.3.2-historical-replay-memory"
MIN_REPLAY_RECORDS_FOR_PRIOR = 30


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
    records = [record for record in memory.get("records", []) if isinstance(record, dict)]
    over: dict[str, int] = {}
    under: dict[str, int] = {}
    leakage_passed = 0
    for record in records:
        if record.get("leakage_passed"):
            leakage_passed += 1
        for number, row in (record.get("number_score_errors") or {}).items():
            error = float(row.get("error", 0) or 0)
            appeared = bool(row.get("appeared"))
            if error > 0 and not appeared:
                over[str(number)] = over.get(str(number), 0) + 1
            if error < 0 and appeared:
                under[str(number)] = under.get(str(number), 0) + 1
    return {
        "records_count": len(records),
        "leakage_passed_count": leakage_passed,
        "shadow_prior_available": leakage_passed >= MIN_REPLAY_RECORDS_FOR_PRIOR,
        "shadow_prior_applied": False,
        "overestimated_numbers": dict(sorted(over.items(), key=lambda item: item[1], reverse=True)),
        "underestimated_numbers": dict(sorted(under.items(), key=lambda item: item[1], reverse=True)),
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
    }
    if records_count < MIN_REPLAY_RECORDS_FOR_PRIOR:
        prior.update({
            "eligible": False,
            "reason": f"Replay requiere {MIN_REPLAY_RECORDS_FOR_PRIOR}+ records; hay {records_count}.",
        })
        return prior
    if not enable_replay_prior:
        prior["reason"] = "ENABLE_REPLAY_PRIOR=False; shadow prior no aplicado."
    over = aggregate.get("overestimated_numbers") or {}
    under = aggregate.get("underestimated_numbers") or {}
    for number in range(1, MAX_NUMBER + 1):
        down = int(over.get(str(number), 0) or 0)
        up = int(under.get(str(number), 0) or 0)
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
        "top_numbers_down": list((aggregate.get("overestimated_numbers") or {}).items())[:10],
        "top_numbers_up": list((aggregate.get("underestimated_numbers") or {}).items())[:10],
        "reason": prior.get("reason"),
    }
