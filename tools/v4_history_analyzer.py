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


EXPERT_KEYS = ("physical", "transformer", "xgboost", "fourier", "graph")
SCORE_BUCKETS = [(0, 20), (20, 40), (40, 60), (60, 80), (80, 100)]


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


def _bucket_label(score: float) -> str:
    for low, high in SCORE_BUCKETS:
        if low <= score < high or (high == 100 and score <= high):
            return f"{low}-{high}"
    return "out_of_range"


def _combo_numbers(combo: dict[str, Any]) -> list[int]:
    values = combo.get("numbers") or combo.get("nums") or combo.get("combo") or []
    parsed = []
    for value in values:
        try:
            parsed.append(int(float(str(value).strip())))
        except (TypeError, ValueError):
            continue
    numbers = sorted(set(parsed))
    return [number for number in numbers if 1 <= number <= 56]


def _combo_profile(numbers: list[int]) -> dict[str, Any]:
    if not numbers:
        return {}
    evens = len([number for number in numbers if number % 2 == 0])
    lows = len([number for number in numbers if number <= 28])
    under40 = len([number for number in numbers if number < 40])
    decades = len({(number - 1) // 10 for number in numbers})
    return {
        "even": evens,
        "odd": len(numbers) - evens,
        "low": lows,
        "high": len(numbers) - lows,
        "decades": decades,
        "sum_total": sum(numbers),
        "under40": under40,
        "dispersion": max(numbers) - min(numbers),
    }


def _avg_profile(items: list[dict[str, Any]]) -> dict[str, float]:
    if not items:
        return {}
    keys = ("even", "odd", "low", "high", "decades", "sum_total", "under40", "dispersion")
    return {key: round(sum(float(item.get(key, 0)) for item in items) / len(items), 4) for key in keys}


def _driver_key(row: dict[str, Any]) -> str:
    raw = str(row.get("main_driver") or row.get("winner_component") or row.get("main_driver_human") or "").lower()
    for key in EXPERT_KEYS:
        if key in raw:
            return key
    return "unknown"


def _number_driver_map(data: dict[str, Any]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    seed = data.get("manual_suggestion_seed")
    if isinstance(seed, list):
        for row in seed:
            if not isinstance(row, dict):
                continue
            number = row.get("number") or row.get("n") or row.get("ball")
            try:
                number_text = str(int(float(str(number))))
            except (TypeError, ValueError):
                continue
            mapping[number_text] = _driver_key(row)
    explanations = data.get("number_explanations")
    if isinstance(explanations, dict):
        for number_text, row in explanations.items():
            if isinstance(row, dict):
                mapping.setdefault(str(number_text), _driver_key(row))
    return mapping


def _score_bucket_analysis(records: list[dict[str, Any]]) -> dict[str, Any]:
    buckets = {
        f"{low}-{high}": {"total_predicted_numbers": 0, "appeared_count": 0, "errors": []}
        for low, high in SCORE_BUCKETS
    }
    for record in records:
        for item in record.get("number_score_errors", {}).values():
            score = float(item.get("predicted_score", 0))
            label = _bucket_label(score)
            if label not in buckets:
                continue
            buckets[label]["total_predicted_numbers"] += 1
            buckets[label]["appeared_count"] += 1 if item.get("appeared") else 0
            buckets[label]["errors"].append(float(item.get("error", 0)))
    output = {}
    for label, row in buckets.items():
        total = row["total_predicted_numbers"]
        appeared = row["appeared_count"]
        output[label] = {
            "total_predicted_numbers": total,
            "appeared_count": appeared,
            "hit_rate": round(appeared / total, 6) if total else 0,
            "avg_error": round(sum(row["errors"]) / len(row["errors"]), 6) if row["errors"] else 0,
        }
    medium_hit = max(output["40-60"]["hit_rate"], output["20-40"]["hit_rate"])
    high_hit = max(output["60-80"]["hit_rate"], output["80-100"]["hit_rate"])
    output["inflated_bucket_detected"] = bool(high_hit <= medium_hit and (output["60-80"]["total_predicted_numbers"] or output["80-100"]["total_predicted_numbers"]))
    return output


def _combo_failure_patterns(records: list[dict[str, Any]]) -> dict[str, Any]:
    weak: list[dict[str, Any]] = []
    better: list[dict[str, Any]] = []
    for record in records:
        for combo in record.get("top_combinations", []):
            profile = _combo_profile(combo.get("numbers", []))
            if not profile:
                continue
            profile["hits"] = combo.get("hits", 0)
            if int(combo.get("hits", 0)) <= 1:
                weak.append(profile)
            else:
                better.append(profile)
    weak_avg = _avg_profile(weak)
    better_avg = _avg_profile(better)
    recurrent = {}
    for key, value in weak_avg.items():
        delta = value - better_avg.get(key, value)
        if abs(delta) >= 0.5:
            recurrent[key] = {"weak_avg": value, "better_avg": better_avg.get(key, 0), "delta": round(delta, 4)}
    return {
        "weak_combos_count": len(weak),
        "better_combos_count": len(better),
        "weak_profile_avg": weak_avg,
        "better_profile_avg": better_avg,
        "recurrent_low_performance_patterns": recurrent,
    }


def _expert_miscalibration(records: list[dict[str, Any]]) -> dict[str, Any]:
    experts = {key: {"predicted_count": 0, "appeared_count": 0, "errors": [], "overestimated_count": 0, "underestimated_count": 0} for key in (*EXPERT_KEYS, "unknown")}
    for record in records:
        drivers = record.get("number_drivers", {})
        for number, item in record.get("number_score_errors", {}).items():
            key = drivers.get(str(number), "unknown")
            row = experts.setdefault(key, {"predicted_count": 0, "appeared_count": 0, "errors": [], "overestimated_count": 0, "underestimated_count": 0})
            error = float(item.get("error", 0))
            row["predicted_count"] += 1
            row["appeared_count"] += 1 if item.get("appeared") else 0
            row["errors"].append(error)
            row["overestimated_count"] += 1 if error > 0 and not item.get("appeared") else 0
            row["underestimated_count"] += 1 if error < 0 and item.get("appeared") else 0
    output = {}
    worst_key = None
    worst_score = -1.0
    for key, row in experts.items():
        avg_error = sum(row["errors"]) / len(row["errors"]) if row["errors"] else 0
        score = abs(avg_error) * max(1, row["predicted_count"])
        if row["predicted_count"] and score > worst_score:
            worst_key = key
            worst_score = score
        output[key] = {
            "predicted_count": row["predicted_count"],
            "appeared_count": row["appeared_count"],
            "avg_error": round(avg_error, 6),
            "overestimated_count": row["overestimated_count"],
            "underestimated_count": row["underestimated_count"],
        }
    output["most_miscalibrated_expert"] = worst_key
    return output


def _specific_expert_bias(expert_summary: dict[str, Any], key: str) -> dict[str, Any]:
    row = expert_summary.get(key, {})
    return {
        "predicted_count": row.get("predicted_count", 0),
        "appeared_count": row.get("appeared_count", 0),
        "avg_error": row.get("avg_error", 0),
        "overestimated_count": row.get("overestimated_count", 0),
        "underestimated_count": row.get("underestimated_count", 0),
        "status": "review" if row.get("predicted_count", 0) else "no_data",
    }


def _diversity_issues(raw_combo_sets: list[list[int]]) -> dict[str, Any]:
    combos = [tuple(sorted(combo)) for combo in raw_combo_sets if len(combo) == 6]
    unique_combos = len(set(combos))
    counts: dict[int, int] = {}
    for combo in combos:
        for number in combo:
            counts[number] = counts.get(number, 0) + 1
    pair_overlaps = []
    sample = combos[:100]
    for index, left in enumerate(sample):
        for right in sample[index + 1:]:
            pair_overlaps.append(len(set(left).intersection(right)))
    most_repeated = sorted(counts.items(), key=lambda item: item[1], reverse=True)[:10]
    concentration = (most_repeated[0][1] / len(combos)) if combos and most_repeated else 0
    return {
        "total_combos": len(combos),
        "unique_combos": unique_combos,
        "unique_numbers_used": len(counts),
        "avg_pair_overlap": round(sum(pair_overlaps) / len(pair_overlaps), 6) if pair_overlaps else 0,
        "most_repeated_numbers": [{"number": number, "count": count} for number, count in most_repeated],
        "repeated_number_concentration": round(concentration, 6),
        "diversity_issue_detected": bool(combos and (len(counts) < 18 or concentration > 0.45)),
    }


def _walk_forward_gap(records: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for record in records:
        exported = record.get("walk_forward_exported", {})
        actual_best = record.get("best_hits_top10", 0)
        actual_avg = record.get("average_hits_top10", 0)
        exported_avg = exported.get("avg_hits")
        exported_top10 = exported.get("avg_hits_top10")
        gap = None
        if isinstance(exported_top10, (int, float)):
            gap = round(float(exported_top10) - float(actual_avg), 6)
        rows.append({
            "prediction_draw": record.get("prediction_draw"),
            "target_draw": record.get("target_draw"),
            "exported_avg_hits": exported_avg,
            "exported_avg_hits_top10": exported_top10,
            "actual_best_hits_top10": actual_best,
            "actual_avg_hits_top10": actual_avg,
            "gap": gap,
            "possible_overconfidence": bool(gap is not None and gap > 0.75 and actual_best <= 1),
        })
    return {
        "records": rows,
        "possible_overconfidence_count": len([row for row in rows if row["possible_overconfidence"]]),
    }



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
    raw_combo_sets: list[list[int]] = []
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
        raw_pool = data.get("generator_pool") or data.get("top_combinations") or []
        if isinstance(raw_pool, list):
            raw_combo_sets.extend(_combo_numbers(combo) for combo in raw_pool if isinstance(combo, dict))
        walk_forward = data.get("walk_forward") if isinstance(data.get("walk_forward"), dict) else {}
        row["califiable"] = True
        row["target_draw"] = target.draw_id
        row["target_numbers"] = list(target.numbers)
        records_used.append({
            "path": str(path),
            "prediction_draw": str(prediction_draw),
            "target_draw": str(target.draw_id),
            "game_mode": infer_game_mode(data),
            "snapshot_source": _snapshot_source(data),
            "source_commit_sha": (data.get("snapshot_metadata") or {}).get("commit_sha") if isinstance(data.get("snapshot_metadata"), dict) else None,
            "source_content_sha256": (data.get("snapshot_metadata") or {}).get("content_sha256") if isinstance(data.get("snapshot_metadata"), dict) else None,
            "top_combinations": graded_combos[:10],
            "number_score_errors": graded_numbers,
            "number_drivers": _number_driver_map(data),
            "walk_forward_exported": {
                "avg_hits": walk_forward.get("avg_hits"),
                "avg_hits_top10": walk_forward.get("avg_hits_top10"),
            },
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
    unique_records_count = len({
        (
            str(record["prediction_draw"]),
            str(record["target_draw"]),
            str(record["game_mode"]),
            str(record["snapshot_source"]),
            str(record.get("source_commit_sha") or record.get("source_content_sha256") or record.get("path") or ""),
        )
        for record in real_records
    })
    duplicate_ratio = len(duplicates) / max(1, len(records_used) + len(duplicates))
    target_counts: dict[str, int] = {}
    for record in real_records:
        target_counts[record["target_draw"]] = target_counts.get(record["target_draw"], 0) + 1
    single_target_dominates = bool(target_counts and max(target_counts.values()) / max(1, len(real_records)) > 0.5)
    overfitting_level = "high" if evidence_insufficient or duplicate_ratio > 0.35 or single_target_dominates else "low"
    score_buckets = _score_bucket_analysis(records_used)
    combo_patterns = _combo_failure_patterns(records_used)
    expert_summary = _expert_miscalibration(records_used)
    diversity = _diversity_issues(raw_combo_sets)
    walk_gap = _walk_forward_gap(records_used)
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
            "bad_score_buckets": score_buckets,
            "top_combo_failure_patterns": combo_patterns,
            "expert_miscalibration": expert_summary,
            "physical_bias_errors": _specific_expert_bias(expert_summary, "physical"),
            "graph_bias_errors": _specific_expert_bias(expert_summary, "graph"),
            "transformer_bias_errors": _specific_expert_bias(expert_summary, "transformer"),
            "xgboost_bias_errors": _specific_expert_bias(expert_summary, "xgboost"),
            "fourier_bias_errors": _specific_expert_bias(expert_summary, "fourier"),
            "monte_carlo_diversity_issues": diversity,
            "ranking_quality": {
                "best_hits_top10_max": max((record["best_hits_top10"] for record in records_used), default=0),
                "average_hits_top10": round(sum(record["average_hits_top10"] for record in records_used) / len(records_used), 6) if records_used else 0,
            },
            "walk_forward_gap": walk_gap,
            "overfitting_risk": {
                "level": overfitting_level,
                "reason": "evidencia insuficiente o concentrada" if overfitting_level == "high" else "evidencia minima suficiente",
                "records_count": len(real_records),
                "unique_records_count": unique_records_count,
                "duplicate_ratio": round(duplicate_ratio, 6),
                "snapshots_per_target_draw": target_counts,
                "whether_single_target_dominates": single_target_dominates,
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
