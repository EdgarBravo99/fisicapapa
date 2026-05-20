#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Historical snapshot analyzer for Fisicapapa V4.3.1.

This is an evaluation tool, not a runner. It treats archived resultados.json
files as past predictions and grades them only against already revealed CSV
draws.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from v4_feedback_memory import (  # noqa: E402
    VALID_SNAPSHOT_SOURCES,
    detect_csv_path,
    extract_number_scores,
    extract_predicted_combinations,
    find_target_draw_in_csv,
    grade_combinations,
    grade_number_scores,
    infer_game_mode,
    infer_model_version,
    infer_prediction_draw,
    load_csv_draws,
)


def _safe_load(path: Path) -> tuple[dict[str, Any] | None, str | None]:
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


def _snapshot_source(data: dict[str, Any]) -> str:
    meta = data.get("snapshot_metadata")
    return str(meta.get("source") if isinstance(meta, dict) else "manual_snapshot")


def _snapshot_identity(data: dict[str, Any], target_draw: str | None) -> tuple[str, str, str, str, str]:
    meta = data.get("snapshot_metadata") if isinstance(data.get("snapshot_metadata"), dict) else {}
    return (
        str(infer_prediction_draw(data)),
        str(target_draw),
        str(infer_game_mode(data)),
        str(meta.get("source") or "manual_snapshot"),
        str(meta.get("commit_sha") or meta.get("content_sha256") or ""),
    )


def _quality_row(path: Path, data: dict[str, Any] | None, reason: str | None = None) -> dict[str, Any]:
    if not data:
        return {"path": str(path), "califiable": False, "omitted_reason": reason}
    meta = data.get("snapshot_metadata") if isinstance(data.get("snapshot_metadata"), dict) else {}
    seed = data.get("manual_suggestion_seed")
    return {
        "path": str(path),
        "commit_sha": meta.get("commit_sha"),
        "short_sha": meta.get("short_sha"),
        "snapshot_source": meta.get("source") or "manual_snapshot",
        "prediction_draw": infer_prediction_draw(data),
        "game_mode": infer_game_mode(data),
        "model_version": infer_model_version(data),
        "score_kind": data.get("score_kind"),
        "csv_path": data.get("csv_path"),
        "top_combinations": len(data.get("top_combinations", []) or []),
        "generator_pool": len(data.get("generator_pool", []) or []),
        "number_scores": len(data.get("number_scores", {}) or {}),
        "manual_suggestion_seed": len(seed) if isinstance(seed, list) else 0,
        "has_walk_forward": isinstance(data.get("walk_forward"), dict),
        "has_expert_scores_v4": "expert_scores_v4" in data,
        "has_complete_physics": isinstance(seed, list)
        and len([row for row in seed if isinstance(row, dict) and row.get("effective_weight") is not None]) == 56,
        "califiable": False,
        "omitted_reason": reason,
    }


def analyze_history(
    archive_dir: str | Path = "resultados_archive",
    csv_path: str | Path | None = None,
    output_path: str | Path = "v4_history_analysis.json",
    mode: str | None = None,
) -> dict[str, Any]:
    archive_path = Path(archive_dir)
    warnings: list[str] = []
    if csv_path is None:
        detected_csv, csv_warnings = detect_csv_path(archive_dir=archive_path)
        csv_path = detected_csv
        warnings.extend(csv_warnings)
    snapshots_imported = []
    snapshots_omitted = []
    records_used = []
    duplicates = []
    seen: set[tuple[str, str, str, str, str]] = set()
    draws = []
    if csv_path:
        try:
            draws = load_csv_draws(csv_path, mode)
        except Exception as exc:
            warnings.append(f"No se pudo cargar CSV revelado: {exc}")
    for path in sorted(archive_path.glob("resultados*.json")):
        if path.name == "index.json":
            continue
        data, error = _safe_load(path)
        if error or not data:
            snapshots_omitted.append(_quality_row(path, data, error))
            continue
        row = _quality_row(path, data)
        snapshots_imported.append(row)
        prediction_draw = infer_prediction_draw(data)
        if not csv_path or not draws:
            row["omitted_reason"] = "sin CSV revelado"
            snapshots_omitted.append(row)
            continue
        if prediction_draw is None:
            row["omitted_reason"] = "sin prediction_draw inferible"
            snapshots_omitted.append(row)
            continue
        target = find_target_draw_in_csv(draws, prediction_draw)
        if target is None:
            row["omitted_reason"] = f"sin target posterior para {prediction_draw}"
            snapshots_omitted.append(row)
            continue
        identity = _snapshot_identity(data, target.draw_id)
        if identity in seen:
            duplicates.append({"path": str(path), "identity": list(identity), "reason": "duplicado"})
            continue
        seen.add(identity)
        combos = extract_predicted_combinations(data, limit=250)
        number_scores = extract_number_scores(data)
        graded_combos = grade_combinations(combos, target.numbers)
        graded_numbers = grade_number_scores(number_scores, target.numbers)
        row["califiable"] = True
        row["target_draw"] = target.draw_id
        row["target_numbers"] = list(target.numbers)
        records_used.append({
            "path": str(path),
            "prediction_draw": str(prediction_draw),
            "target_draw": str(target.draw_id),
            "game_mode": infer_game_mode(data),
            "snapshot_source": _snapshot_source(data),
            "top_combinations": graded_combos[:10],
            "number_score_errors": graded_numbers,
            "best_hits_top10": max((item["hits"] for item in graded_combos[:10]), default=0),
            "average_hits_top10": round(sum(item["hits"] for item in graded_combos[:10]) / len(graded_combos[:10]), 6) if graded_combos[:10] else 0,
        })
    over: dict[str, int] = {}
    under: dict[str, int] = {}
    for record in records_used:
        for number, item in record["number_score_errors"].items():
            if item["error"] > 0 and not item["appeared"]:
                over[number] = over.get(number, 0) + 1
            if item["error"] < 0 and item["appeared"]:
                under[number] = under.get(number, 0) + 1
    real_records = [
        record for record in records_used
        if record.get("snapshot_source") in VALID_SNAPSHOT_SOURCES
    ]
    evidence_insufficient = len(real_records) < 3
    overfitting_level = "high" if evidence_insufficient else "low"
    analysis = {
        "version": "V4.3.1-history-analysis",
        "csv_used": str(csv_path) if csv_path else None,
        "summary": {
            "snapshots_imported": len(snapshots_imported),
            "snapshots_omitted": len(snapshots_omitted),
            "records_real_used": len(real_records),
            "records_duplicates_ignored": len(duplicates),
            "evidence_insufficient": evidence_insufficient,
            "overfitting_risk_level": overfitting_level,
        },
        "snapshots_imported": snapshots_imported,
        "snapshots_omitted": snapshots_omitted,
        "records_real_used": records_used,
        "records_duplicates_ignored": duplicates,
        "warnings": warnings,
        "evidence_insufficient": evidence_insufficient,
        "mistakes_summary": {
            "overestimated_numbers": dict(sorted(over.items(), key=lambda item: item[1], reverse=True)[:20]),
            "underestimated_numbers": dict(sorted(under.items(), key=lambda item: item[1], reverse=True)[:20]),
            "bad_score_buckets": {},
            "top_combo_failure_patterns": {},
            "expert_miscalibration": {},
            "physical_bias_errors": {},
            "graph_bias_errors": {},
            "transformer_bias_errors": {},
            "xgboost_bias_errors": {},
            "fourier_bias_errors": {},
            "monte_carlo_diversity_issues": {},
            "ranking_quality": {
                "best_hits_top10_max": max((record["best_hits_top10"] for record in records_used), default=0),
                "average_hits_top10": round(sum(record["average_hits_top10"] for record in records_used) / len(records_used), 6) if records_used else 0,
            },
            "walk_forward_gap": {},
            "overfitting_risk": {
                "level": overfitting_level,
                "reason": "menos de 3 records reales unicos" if evidence_insufficient else "evidencia minima suficiente",
            },
        },
    }
    Path(output_path).write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8")
    return analysis


def main() -> int:
    parser = argparse.ArgumentParser(description="Analiza snapshots historicos V4.3.1.")
    parser.add_argument("--archive-dir", default="resultados_archive")
    parser.add_argument("--csv", default=None)
    parser.add_argument("--mode", default=None)
    parser.add_argument("--output", default="v4_history_analysis.json")
    args = parser.parse_args()
    analysis = analyze_history(args.archive_dir, args.csv, args.output, args.mode)
    print(json.dumps(analysis.get("summary", {}), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
