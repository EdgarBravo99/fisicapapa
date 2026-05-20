#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Persistent exam-style feedback memory for Fisicapapa V4.3.

This module grades old ``resultados.json`` snapshots against draws that are
already revealed in the CSV. A snapshot is a past prediction, never ground
truth. The CSV is the only revealed truth source.
"""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MAX_NUMBER = 56
PICK_COUNT = 6
MEMORY_VERSION = "V4.3-persistent-exam-memory"
VALID_SNAPSHOT_SOURCES = {"git_history", "local_pre_run_archive"}
CSV_CANDIDATES = [
    "melate.csv",
    "revancha.csv",
    "historial_melate.csv",
    "historial_revancha.csv",
    "historial.csv",
]


@dataclass(frozen=True)
class Draw:
    draw_id: str
    date: str | None
    numbers: tuple[int, ...]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_int(value: Any) -> int | None:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def _record_unique_key(record: dict[str, Any]) -> tuple[str, str, str, str, str]:
    source = str(record.get("snapshot_source") or "unknown")
    commit_or_hash = str(record.get("source_commit_sha") or record.get("source_content_sha256") or "")
    return (
        str(record.get("prediction_draw")),
        str(record.get("target_draw")),
        str(record.get("game_mode")),
        source,
        commit_or_hash,
    )


def _snapshot_metadata(results_json: dict[str, Any]) -> dict[str, Any]:
    meta = results_json.get("snapshot_metadata")
    return meta if isinstance(meta, dict) else {}


def _snapshot_source(results_json: dict[str, Any]) -> str:
    return str(_snapshot_metadata(results_json).get("source") or "manual_snapshot")


def _score_to_100(value: Any) -> float | None:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None
    if 0 <= score <= 1:
        return score * 100
    if 0 <= score <= 100:
        return score
    return None


def default_feedback_memory() -> dict[str, Any]:
    return {
        "version": MEMORY_VERSION,
        "last_updated": None,
        "records": [],
        "aggregate": {
            "records_count": 0,
            "average_hits_top_combinations": 0,
            "best_hits_seen": 0,
            "overestimated_numbers": {},
            "underestimated_numbers": {},
            "combo_score_buckets": {},
            "profile_performance": {},
            "memory_adjustments": {},
        },
    }


def load_feedback_memory(path: str | Path = "v4_feedback_memory.json") -> dict[str, Any]:
    memory_path = Path(path)
    if not memory_path.exists():
        return default_feedback_memory()
    try:
        data = json.loads(memory_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Memoria invalida en {memory_path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"Memoria invalida en {memory_path}: se esperaba objeto JSON.")
    data.setdefault("version", MEMORY_VERSION)
    data.setdefault("last_updated", None)
    data.setdefault("records", [])
    data.setdefault("aggregate", default_feedback_memory()["aggregate"])
    return data


def save_feedback_memory(memory: dict[str, Any], path: str | Path = "v4_feedback_memory.json") -> None:
    records = memory.get("records")
    if not isinstance(records, list) or not records:
        return
    memory["version"] = MEMORY_VERSION
    memory["last_updated"] = _utc_now()
    Path(path).write_text(json.dumps(memory, ensure_ascii=False, indent=2), encoding="utf-8")


def infer_prediction_draw(results_json: dict[str, Any]) -> str | None:
    candidates = [
        results_json.get("prediction_draw"),
        results_json.get("target_prediction_draw"),
        results_json.get("historical_forgetting", {}).get("buffer_last_draw"),
    ]
    rows = results_json.get("walk_forward", {}).get("rows")
    if isinstance(rows, list) and rows:
        candidates.append(rows[-1].get("draw_id"))
    for value in candidates:
        parsed = _parse_int(value)
        if parsed is not None:
            return str(parsed)
    return None


def infer_model_version(results_json: dict[str, Any]) -> str:
    return str(results_json.get("model_version") or results_json.get("source") or "unknown")


def infer_game_mode(results_json: dict[str, Any]) -> str:
    return str(results_json.get("game_mode") or results_json.get("mode") or "unknown").lower()


def detect_number_columns(fieldnames: list[str]) -> list[str]:
    lower = {str(col).lower().strip(): col for col in fieldnames}
    for names in (
        ["n1", "n2", "n3", "n4", "n5", "n6"],
        ["num1", "num2", "num3", "num4", "num5", "num6"],
        ["bola1", "bola2", "bola3", "bola4", "bola5", "bola6"],
    ):
        if all(name in lower for name in names):
            return [lower[name] for name in names]
    numeric_candidates: list[str] = []
    rows_sample: list[dict[str, str]] = []
    return numeric_candidates if rows_sample else []


def load_csv_draws(csv_path: str | Path, mode: str | None = None) -> list[Draw]:
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"No existe CSV historico: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError(f"CSV sin encabezados: {path}")
        rows = list(reader)
    lower = {str(col).lower().strip(): col for col in reader.fieldnames}
    number_cols = detect_number_columns(reader.fieldnames)
    if not number_cols:
        scored: list[tuple[float, str]] = []
        for col in reader.fieldnames:
            values = [_parse_int(row.get(col)) for row in rows]
            valid = [value for value in values if value is not None]
            if not rows:
                continue
            valid_ratio = len(valid) / len(rows)
            range_ratio = len([value for value in valid if 1 <= value <= MAX_NUMBER]) / max(1, len(rows))
            if valid_ratio > 0.80 and range_ratio > 0.55:
                scored.append((range_ratio, col))
        number_cols = [col for _score, col in sorted(scored, reverse=True)[:PICK_COUNT]]
    if len(number_cols) < PICK_COUNT:
        raise ValueError("No pude detectar columnas de numeros n1..n6 en el CSV.")
    draw_col = next((lower[name] for name in ("sorteo", "draw", "concurso", "id") if name in lower), None)
    date_col = next((lower[name] for name in ("fecha", "date") if name in lower), None)
    draws: list[Draw] = []
    for index, row in enumerate(rows):
        numbers = sorted({
            value for value in (_parse_int(row.get(col)) for col in number_cols)
            if value is not None and 1 <= value <= MAX_NUMBER
        })
        if len(numbers) != PICK_COUNT:
            continue
        draw_id = str(row.get(draw_col) if draw_col else index).strip()
        date = str(row.get(date_col)).strip() if date_col and row.get(date_col) else None
        draws.append(Draw(draw_id=draw_id, date=date, numbers=tuple(numbers)))
    draws.sort(key=lambda draw: _parse_int(draw.draw_id) or -1)
    return draws


def find_target_draw_in_csv(csv_rows: list[Draw], prediction_draw: str | int | None) -> Draw | None:
    prediction_id = _parse_int(prediction_draw)
    if prediction_id is None:
        return None
    for draw in csv_rows:
        draw_id = _parse_int(draw.draw_id)
        if draw_id is not None and draw_id > prediction_id:
            return draw
    return None


def _combo_numbers(combo: Any) -> list[int]:
    raw = combo if isinstance(combo, list) else combo.get("numbers") or combo.get("nums") or combo.get("combo") or []
    parsed_numbers = []
    for value in raw:
        parsed = _parse_int(value)
        if parsed is not None and 1 <= parsed <= MAX_NUMBER:
            parsed_numbers.append(parsed)
    numbers = sorted(set(parsed_numbers))
    return numbers if len(numbers) == PICK_COUNT else []


def extract_predicted_combinations(results_json: dict[str, Any], limit: int = 10) -> list[dict[str, Any]]:
    source = results_json.get("top_combinations") or results_json.get("generator_pool") or []
    combos: list[dict[str, Any]] = []
    for combo in source[:limit] if isinstance(source, list) else []:
        numbers = _combo_numbers(combo)
        if not numbers:
            continue
        score = None
        if isinstance(combo, dict):
            for field in ("score_percent", "net_score", "confidence", "score"):
                score = _score_to_100(combo.get(field))
                if score is not None:
                    break
        combos.append({"numbers": numbers, "score": score})
    return combos


def extract_number_scores(results_json: dict[str, Any]) -> dict[str, float]:
    scores: dict[str, float] = {}
    raw = results_json.get("number_scores")
    if isinstance(raw, dict):
        for key, value in raw.items():
            number = _parse_int(key)
            score = _score_to_100(value)
            if number is not None and 1 <= number <= MAX_NUMBER and score is not None:
                scores[str(number)] = score
    if scores:
        return scores
    seed = results_json.get("manual_suggestion_seed")
    if isinstance(seed, list):
        for row in seed:
            if not isinstance(row, dict):
                continue
            number = _parse_int(row.get("number") or row.get("n") or row.get("ball"))
            score = _score_to_100(row.get("meta_score") or row.get("score") or row.get("score_percent"))
            if number is not None and 1 <= number <= MAX_NUMBER and score is not None:
                scores[str(number)] = score
    return scores


def grade_combinations(predicted_combos: list[dict[str, Any]], target_numbers: tuple[int, ...]) -> list[dict[str, Any]]:
    target = set(target_numbers)
    graded = []
    for combo in predicted_combos:
        numbers = combo["numbers"]
        hit_numbers = sorted(target.intersection(numbers))
        hits = len(hit_numbers)
        if not 0 <= hits <= PICK_COUNT:
            raise ValueError(f"Hits fuera de rango para {numbers}: {hits}")
        graded.append({
            "numbers": numbers,
            "score": combo.get("score"),
            "hits": hits,
            "hit_numbers": hit_numbers,
            "missed_numbers": [number for number in numbers if number not in target],
        })
    return graded


def grade_number_scores(number_scores: dict[str, float], target_numbers: tuple[int, ...]) -> dict[str, dict[str, Any]]:
    target = set(target_numbers)
    graded: dict[str, dict[str, Any]] = {}
    for number_text, predicted_score in number_scores.items():
        number = _parse_int(number_text)
        if number is None or not 1 <= number <= MAX_NUMBER:
            continue
        appeared = number in target
        expected = 100.0 if appeared else 0.0
        graded[str(number)] = {
            "predicted_score": round(predicted_score, 6),
            "appeared": appeared,
            "error": round(predicted_score - expected, 6),
        }
    return graded


def rebuild_aggregate(memory: dict[str, Any]) -> dict[str, Any]:
    records = memory.get("records", [])
    unique_keys = {_record_unique_key(record) for record in records}
    valid_records = [
        record for record in records
        if record.get("snapshot_source") in VALID_SNAPSHOT_SOURCES and not record.get("mock")
    ]
    valid_unique_keys = {_record_unique_key(record) for record in valid_records}
    over: dict[str, list[float]] = {}
    under: dict[str, list[float]] = {}
    hits: list[int] = []
    for record in valid_records:
        combos = record.get("top_combinations", [])
        if combos:
            hits.extend(int(combo.get("hits", 0)) for combo in combos)
        for number, row in record.get("number_score_errors", {}).items():
            error = float(row.get("error", 0))
            if error > 0 and not row.get("appeared"):
                over.setdefault(number, []).append(error)
            elif error < 0 and row.get("appeared"):
                under.setdefault(number, []).append(error)
    aggregate = {
        "records_count": len(records),
        "unique_records_count": len(unique_keys),
        "valid_real_records_count": len(valid_unique_keys),
        "average_hits_top_combinations": round(sum(hits) / len(hits), 6) if hits else 0,
        "best_hits_seen": max(hits) if hits else 0,
        "overestimated_numbers": {
            number: {"count": len(values), "avg_error": round(sum(values) / len(values), 6)}
            for number, values in sorted(over.items(), key=lambda item: sum(item[1]) / len(item[1]), reverse=True)
        },
        "underestimated_numbers": {
            number: {"count": len(values), "avg_error": round(sum(values) / len(values), 6)}
            for number, values in sorted(under.items(), key=lambda item: sum(item[1]) / len(item[1]))
        },
        "combo_score_buckets": {},
        "profile_performance": {},
        "memory_adjustments": {},
    }
    memory["aggregate"] = aggregate
    return aggregate


def memory_strength_from_records(records_count: int) -> float:
    if records_count >= 10:
        return 1.0
    if records_count >= 8:
        return 0.75
    if records_count >= 5:
        return 0.5
    if records_count >= 3:
        return 0.25
    return 0.0


def compute_memory_adjustments(
    memory: dict[str, Any],
    max_number_adjustment: float = 0.05,
    min_records_for_adjustment: int = 3,
) -> dict[str, Any]:
    aggregate = memory.get("aggregate") or rebuild_aggregate(memory)
    records_count = int(aggregate.get("valid_real_records_count") or 0)
    if records_count < min_records_for_adjustment:
        return {
            "enabled": False,
            "reason": f"Se requieren {min_records_for_adjustment} records reales unicos; hay {records_count}.",
            "adjustments": {},
        }
    strength = memory_strength_from_records(records_count)
    adjustments: dict[str, float] = {}
    for number, row in aggregate.get("overestimated_numbers", {}).items():
        if int(row.get("count", 0)) >= 2:
            adjustments[number] = round(-max_number_adjustment * strength, 8)
    for number, row in aggregate.get("underestimated_numbers", {}).items():
        if int(row.get("count", 0)) >= 2:
            adjustments[number] = round(max_number_adjustment * strength, 8)
    aggregate["memory_adjustments"] = adjustments
    return {
        "enabled": bool(adjustments),
        "reason": "Prior suave calculado para hook pre-Monte-Carlo.",
        "adjustments": adjustments,
        "memory_strength": strength,
        "valid_real_records_count": records_count,
    }


def summarize_feedback_memory(memory: dict[str, Any]) -> dict[str, Any]:
    aggregate = rebuild_aggregate(memory)
    records = memory.get("records", [])
    last = records[-1] if records else {}
    adjustments = compute_memory_adjustments(memory)
    return {
        "enabled": bool(records),
        "version": MEMORY_VERSION,
        "records_used": aggregate["records_count"],
        "valid_real_records_used": aggregate.get("valid_real_records_count", 0),
        "adjustment_mode": "diagnostic_only" if not adjustments["enabled"] else "pre_monte_carlo_memory_prior",
        "memory_strength": adjustments.get("memory_strength", 0),
        "max_number_adjustment": 0.05,
        "max_combo_adjustment": 0.05,
        "last_graded_prediction_draw": last.get("prediction_draw"),
        "last_graded_target_draw": last.get("target_draw"),
        "overestimated_numbers_top": list(aggregate["overestimated_numbers"].items())[:10],
        "underestimated_numbers_top": list(aggregate["underestimated_numbers"].items())[:10],
        "applied_adjustments": {},
        "memory_prior_applied": False,
        "note": "Memoria basada en calificacion de predicciones pasadas contra sorteos reales ya revelados. No usa resultados.json como verdad y no mira el futuro.",
    }


def update_feedback_memory_from_snapshot(
    results_path: str | Path,
    csv_path: str | Path,
    mode: str | None = None,
    memory_path: str | Path = "v4_feedback_memory.json",
    dry_run: bool = False,
) -> dict[str, Any]:
    warnings: list[str] = []
    path = Path(results_path)
    if not path.exists():
        return {"changed": False, "warnings": [f"No existe snapshot: {path}"], "record": None}
    raw_text = path.read_text(encoding="utf-8")
    try:
        results = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        return {"changed": False, "warnings": [f"Snapshot corrupto o vacio omitido: {path} ({exc})"], "record": None}
    if not isinstance(results, dict):
        return {"changed": False, "warnings": [f"Snapshot omitido porque no es objeto JSON: {path}"], "record": None}
    prediction_draw = infer_prediction_draw(results)
    if prediction_draw is None:
        return {"changed": False, "warnings": ["No pude inferir prediction_draw del snapshot."], "record": None}
    meta = _snapshot_metadata(results)
    snapshot_source = _snapshot_source(results)
    source_commit_sha = meta.get("commit_sha")
    source_content_sha256 = meta.get("content_sha256") or _content_hash(raw_text)
    game_mode = (mode or infer_game_mode(results)).lower()
    draws = load_csv_draws(csv_path, game_mode)
    target = find_target_draw_in_csv(draws, prediction_draw)
    if target is None:
        return {
            "changed": False,
            "warnings": [f"CSV no contiene sorteo posterior a prediction_draw={prediction_draw}. No se inventa target."],
            "record": None,
        }
    combos = extract_predicted_combinations(results)
    if not combos:
        warnings.append("Snapshot sin top_combinations ni generator_pool evaluable.")
    number_scores = extract_number_scores(results)
    if not number_scores:
        warnings.append("Snapshot sin number_scores evaluable.")
    graded_combos = grade_combinations(combos, target.numbers)
    graded_numbers = grade_number_scores(number_scores, target.numbers)
    memory = load_feedback_memory(memory_path)
    candidate_record = {
        "prediction_draw": str(prediction_draw),
        "target_draw": str(target.draw_id),
        "game_mode": game_mode,
        "snapshot_source": snapshot_source,
        "source_commit_sha": source_commit_sha,
        "source_content_sha256": source_content_sha256,
    }
    record_key = _record_unique_key(candidate_record)
    for existing in memory.get("records", []):
        existing_key = _record_unique_key(existing)
        if existing_key == record_key:
            return {"changed": False, "warnings": [f"Record ya existe: {record_key}"], "record": existing}
    average_hits = sum(item["hits"] for item in graded_combos) / len(graded_combos) if graded_combos else 0
    best_hits = max((item["hits"] for item in graded_combos), default=0)
    record = {
        "prediction_draw": str(prediction_draw),
        "target_draw": str(target.draw_id),
        "target_date": target.date,
        "target_numbers": list(target.numbers),
        "game_mode": game_mode,
        "snapshot_source": snapshot_source,
        "source_commit_sha": source_commit_sha,
        "source_content_sha256": source_content_sha256,
        "snapshot_path": str(path),
        "model_version": infer_model_version(results),
        "generated_at": results.get("last_update") or results.get("generated_at"),
        "graded_at": _utc_now(),
        "top_combinations": graded_combos,
        "number_score_errors": graded_numbers,
        "exam_grade": {
            "average_hits": round(average_hits, 6),
            "best_hits": best_hits,
            "score_inflation_detected": bool(graded_combos and average_hits < 1.0),
        },
        "warnings": warnings,
    }
    memory.setdefault("records", []).append(record)
    rebuild_aggregate(memory)
    if not dry_run:
        save_feedback_memory(memory, memory_path)
    return {"changed": True, "warnings": warnings, "record": record, "memory": memory}


def _load_json_file(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return None, str(exc)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        return None, f"JSON invalido: {exc}"
    if not isinstance(data, dict):
        return None, "JSON no es objeto"
    return data, None


def detect_csv_path(
    current_results_path: str | Path = "resultados.json",
    archive_dir: str | Path = "resultados_archive",
) -> tuple[Path | None, list[str]]:
    warnings: list[str] = []
    candidates: list[Path] = []
    current = Path(current_results_path)
    if current.exists():
        data, error = _load_json_file(current)
        if data:
            csv_path = data.get("csv_path")
            if csv_path:
                candidates.append(Path(str(csv_path)))
        elif error:
            warnings.append(f"No pude leer csv_path de resultados.json actual: {error}")
    archive_path = Path(archive_dir)
    for snapshot_path in sorted(archive_path.glob("resultados*.json")):
        if snapshot_path.name == "index.json":
            continue
        data, _error = _load_json_file(snapshot_path)
        if data and data.get("csv_path"):
            candidates.append(Path(str(data.get("csv_path"))))
    candidates.extend(Path(name) for name in CSV_CANDIDATES)
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        if candidate.exists():
            return candidate, warnings
    warnings.append("No hay CSV revelado; se importa historico pero no se puede calificar memoria.")
    return None, warnings


def find_ungraded_snapshots(
    archive_dir: str | Path,
    memory: dict[str, Any],
    csv_path: str | Path,
    mode: str | None = None,
) -> dict[str, Any]:
    archive_path = Path(archive_dir)
    existing_keys = {_record_unique_key(record) for record in memory.get("records", [])}
    draws = load_csv_draws(csv_path, mode)
    snapshots: list[Path] = []
    omitted: list[dict[str, Any]] = []
    duplicates: list[dict[str, Any]] = []
    for path in sorted(archive_path.glob("resultados*.json")):
        if path.name == "index.json":
            continue
        data, error = _load_json_file(path)
        if error or not data:
            omitted.append({"path": str(path), "reason": error or "snapshot ilegible"})
            continue
        prediction_draw = infer_prediction_draw(data)
        if prediction_draw is None:
            omitted.append({"path": str(path), "reason": "sin prediction_draw inferible"})
            continue
        game_mode = (mode or infer_game_mode(data)).lower()
        target = find_target_draw_in_csv(draws, prediction_draw)
        if target is None:
            omitted.append({"path": str(path), "reason": f"sin target posterior para {prediction_draw}"})
            continue
        meta = _snapshot_metadata(data)
        text = path.read_text(encoding="utf-8")
        candidate = {
            "prediction_draw": str(prediction_draw),
            "target_draw": str(target.draw_id),
            "game_mode": game_mode,
            "snapshot_source": _snapshot_source(data),
            "source_commit_sha": meta.get("commit_sha"),
            "source_content_sha256": meta.get("content_sha256") or _content_hash(text),
        }
        key = _record_unique_key(candidate)
        if key in existing_keys:
            duplicates.append({"path": str(path), "reason": "record duplicado", "key": list(key)})
            continue
        snapshots.append(path)
    return {"snapshots": snapshots, "omitted": omitted, "duplicates": duplicates}


def update_feedback_memory_from_archive(
    archive_dir: str | Path = "resultados_archive",
    csv_path: str | Path | None = None,
    mode: str | None = None,
    memory_path: str | Path = "v4_feedback_memory.json",
    dry_run: bool = False,
) -> dict[str, Any]:
    warnings: list[str] = []
    if csv_path is None:
        detected_csv, csv_warnings = detect_csv_path(archive_dir=archive_dir)
        warnings.extend(csv_warnings)
        csv_path = detected_csv
    if csv_path is None:
        return {"changed": False, "records_new": 0, "warnings": warnings, "omitted": [], "duplicates": []}
    memory = load_feedback_memory(memory_path)
    try:
        ungraded = find_ungraded_snapshots(archive_dir, memory, csv_path, mode)
    except Exception as exc:
        return {"changed": False, "records_new": 0, "warnings": [*warnings, str(exc)], "omitted": [], "duplicates": []}
    records_new = 0
    changed = False
    for snapshot_path in ungraded["snapshots"]:
        result = update_feedback_memory_from_snapshot(snapshot_path, csv_path, mode=mode, memory_path=memory_path, dry_run=dry_run)
        warnings.extend(result.get("warnings", []))
        if result.get("changed"):
            records_new += 1
            changed = True
    return {
        "changed": changed,
        "records_new": records_new,
        "csv_path": str(csv_path),
        "warnings": warnings,
        "omitted": ungraded["omitted"],
        "duplicates": ungraded["duplicates"],
    }


def grade_all_imported_snapshots(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return update_feedback_memory_from_archive(*args, **kwargs)


def load_history_analysis(path: str | Path = "v4_history_analysis.json") -> dict[str, Any] | None:
    analysis_path = Path(path)
    if not analysis_path.exists():
        return None
    data, error = _load_json_file(analysis_path)
    if error:
        return None
    return data


def compute_memory_prior(
    memory: dict[str, Any],
    history_analysis: dict[str, Any] | None = None,
    max_number_adjustment: float = 0.05,
) -> dict[str, Any]:
    aggregate = rebuild_aggregate(memory)
    valid_count = int(aggregate.get("valid_real_records_count") or 0)
    analysis = history_analysis or {}
    overfit = analysis.get("mistakes_summary", {}).get("overfitting_risk", {})
    insufficient = bool(analysis.get("evidence_insufficient") or overfit.get("level") == "high")
    if valid_count < 3:
        return {"eligible": False, "mode": "diagnostic_only", "reason": f"Se requieren 3 records reales unicos; hay {valid_count}.", "adjustments": {}, "records_used": valid_count}
    if insufficient:
        return {"eligible": False, "mode": "diagnostic_only", "reason": "Analisis historico marco evidencia insuficiente o riesgo alto de overfitting.", "adjustments": {}, "records_used": valid_count}
    adjustments = compute_memory_adjustments(memory, max_number_adjustment=max_number_adjustment)
    if not adjustments.get("enabled"):
        return {"eligible": False, "mode": "diagnostic_only", "reason": adjustments.get("reason"), "adjustments": {}, "records_used": valid_count}
    return {
        "eligible": True,
        "mode": "pre_monte_carlo_memory_prior",
        "reason": "Prior pre-Monte-Carlo elegible con records reales unicos.",
        "adjustments": adjustments.get("adjustments", {}),
        "records_used": valid_count,
        "memory_strength": adjustments.get("memory_strength", 0),
        "max_number_adjustment": max_number_adjustment,
    }


def apply_memory_prior_to_score_vector(score_vector: Any, memory_prior: dict[str, Any]) -> tuple[Any, list[dict[str, Any]]]:
    adjustments = memory_prior.get("adjustments") or {}
    if not adjustments:
        return score_vector, []
    audit: list[dict[str, Any]] = []
    try:
        import numpy as np  # type: ignore
    except Exception:
        np = None
    adjusted = score_vector.copy() if hasattr(score_vector, "copy") else list(score_vector)
    for number_text, delta in adjustments.items():
        number = _parse_int(number_text)
        if number is None:
            continue
        index = number - 1 if len(adjusted) == MAX_NUMBER else number
        if index < 0 or index >= len(adjusted):
            continue
        before = float(adjusted[index])
        after = max(0.0, min(1.0, before * (1.0 + float(delta))))
        adjusted[index] = after
        audit.append({
            "number": number,
            "before_score": round(before, 8),
            "after_score": round(after, 8),
            "delta": round(after - before, 8),
            "adjustment_direction": "up" if after > before else "down",
            "reason": "historically_underestimated" if float(delta) > 0 else "historically_overestimated",
            "records_used": memory_prior.get("records_used", 0),
            "memory_strength": memory_prior.get("memory_strength", 0),
        })
    if np is not None and hasattr(score_vector, "shape"):
        adjusted = np.asarray(adjusted, dtype=float)
    return adjusted, audit


def build_memory_prior_audit(memory_prior: dict[str, Any], number_audit: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "mode": memory_prior.get("mode", "diagnostic_only"),
        "memory_prior_applied": bool(memory_prior.get("applied")),
        "eligible": bool(memory_prior.get("eligible")),
        "records_used": memory_prior.get("records_used", 0),
        "memory_strength": memory_prior.get("memory_strength", 0),
        "max_number_adjustment": memory_prior.get("max_number_adjustment", 0.05),
        "number_prior": number_audit or [],
        "reason": memory_prior.get("reason"),
    }


def build_before_after_number_summary(number_audit: list[dict[str, Any]]) -> dict[str, Any]:
    changed = [row for row in number_audit if row.get("delta")]
    return {
        "number_scores_changed": len(changed),
        "max_delta_seen": max((abs(float(row.get("delta", 0))) for row in changed), default=0),
        "numbers_up": [row for row in changed if row.get("adjustment_direction") == "up"][:10],
        "numbers_down": [row for row in changed if row.get("adjustment_direction") == "down"][:10],
    }


def annotate_results_with_memory(
    results_path: str | Path = "resultados.json",
    memory_path: str | Path = "v4_feedback_memory.json",
    history_analysis_path: str | Path = "v4_history_analysis.json",
    memory_prior: dict[str, Any] | None = None,
    prior_audit: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    results_file = Path(results_path)
    if not results_file.exists():
        return None
    memory_file = Path(memory_path)
    memory = load_feedback_memory(memory_file) if memory_file.exists() else default_feedback_memory()
    results = json.loads(results_file.read_text(encoding="utf-8"))
    summary = summarize_feedback_memory(memory)
    if memory_prior:
        summary["adjustment_mode"] = memory_prior.get("mode", summary.get("adjustment_mode"))
        summary["memory_strength"] = memory_prior.get("memory_strength", summary.get("memory_strength", 0))
        summary["valid_real_records_used"] = memory_prior.get("records_used", summary.get("valid_real_records_used", 0))
        summary["memory_prior_applied"] = bool(memory_prior.get("applied"))
    if prior_audit:
        summary["before_after_summary"] = build_before_after_number_summary(prior_audit.get("number_prior", []))
    results["feedback_memory"] = summary
    analysis = load_history_analysis(history_analysis_path)
    if analysis:
        results["history_analysis_summary"] = analysis.get("summary", {})
        results["memory_prior_audit"] = prior_audit or {}
    elif prior_audit:
        results["memory_prior_audit"] = prior_audit
    results_file.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary
