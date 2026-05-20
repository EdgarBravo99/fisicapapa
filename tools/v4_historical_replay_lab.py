# -*- coding: utf-8 -*-
"""Historical replay lab using the main Fisicapapa engine with truncated CSVs."""

from __future__ import annotations

import argparse
import contextlib
import csv
import hashlib
import importlib
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from v4_feedback_memory import (  # noqa: E402
    extract_number_scores,
    extract_predicted_combinations,
    grade_combinations,
    grade_number_scores,
    load_csv_draws,
)
from v4_replay_memory import add_replay_records, build_replay_prior_audit, load_replay_memory  # noqa: E402

INTENSITY_ENV = {
    "replay_fast": {
        "MELATE_V4_MC_TOTAL": "100000",
        "MELATE_V4_MC_BATCH": "25000",
        "MELATE_V4_OOS_STEPS": "10",
    },
    "replay_medium": {
        "MELATE_V4_MC_TOTAL": "500000",
        "MELATE_V4_MC_BATCH": "50000",
        "MELATE_V4_OOS_STEPS": "20",
    },
    "replay_full": {},
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_int(value: Any) -> int | None:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None


def file_sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_csv_rows(csv_path: str | Path) -> tuple[list[str], list[dict[str, str]], str]:
    path = Path(csv_path)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError(f"CSV sin encabezados: {path}")
        rows = list(reader)
    lower = {name.lower().strip(): name for name in reader.fieldnames}
    draw_col = next((lower[name] for name in ("sorteo", "draw", "concurso", "id") if name in lower), None)
    if not draw_col:
        raise ValueError("No pude detectar columna de sorteo/draw en CSV.")
    return list(reader.fieldnames), rows, draw_col


def select_targets(
    csv_path: str | Path,
    start_draw: int | None = None,
    end_draw: int | None = None,
    max_targets: int = 3,
    min_train_rows: int = 150,
) -> list[int]:
    _fieldnames, rows, draw_col = read_csv_rows(csv_path)
    draw_ids = [parsed for parsed in (_parse_int(row.get(draw_col)) for row in rows) if parsed is not None]
    draw_ids = sorted(set(draw_ids))
    candidates = [
        draw_id for draw_id in draw_ids
        if (start_draw is None or draw_id >= start_draw)
        and (end_draw is None or draw_id <= end_draw)
        and len([prior for prior in draw_ids if prior < draw_id]) >= min_train_rows
    ]
    return candidates[-max_targets:]


def write_truncated_csv(
    source_csv: str | Path,
    target_draw: int,
    output_path: str | Path,
) -> dict[str, Any]:
    fieldnames, rows, draw_col = read_csv_rows(source_csv)
    train_rows = []
    target_in_train = False
    future_in_train = False
    for row in rows:
        draw_id = _parse_int(row.get(draw_col))
        if draw_id is None:
            continue
        if draw_id < target_draw:
            train_rows.append(row)
        if draw_id == target_draw and draw_id < target_draw:
            target_in_train = True
        if draw_id > target_draw and draw_id < target_draw:
            future_in_train = True
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(train_rows)
    train_draws = [_parse_int(row.get(draw_col)) for row in train_rows]
    leakage_passed = bool(train_rows and target_draw not in train_draws and all(draw_id is not None and draw_id < target_draw for draw_id in train_draws))
    return {
        "temp_csv_path": str(output),
        "rows_written": len(train_rows),
        "csv_train_until_draw": str(max(train_draws)) if train_draws else None,
        "target_draw_in_train": target_in_train or target_draw in train_draws,
        "future_draw_in_train": future_in_train or any(draw_id is not None and draw_id > target_draw for draw_id in train_draws),
        "leakage_passed": leakage_passed,
    }


@contextlib.contextmanager
def replay_environment(intensity: str) -> Iterator[dict[str, str | None]]:
    env_values = INTENSITY_ENV.get(intensity)
    if env_values is None:
        raise ValueError(f"Intensidad desconocida: {intensity}")
    original = {key: os.environ.get(key) for key in {"MELATE_V4_MC_TOTAL", "MELATE_V4_MC_BATCH", "MELATE_V4_OOS_STEPS"}}
    try:
        for key, value in env_values.items():
            os.environ[key] = value
        yield original
    finally:
        for key, value in original.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def load_main_engine_after_env() -> tuple[Any, Any]:
    calibrated = importlib.import_module("local_cruncher_v4_2_calibrated")
    calibrated.engine = None
    if "local_cruncher_v4_deep_stacking" in sys.modules:
        importlib.reload(sys.modules["local_cruncher_v4_deep_stacking"])
    eng = calibrated.load_engine()
    calibrated.apply_weight_calibration()
    return calibrated, eng


@contextlib.contextmanager
def patched_engine(eng: Any, game_mode: str, buffer_size: int, temp_csv_path: str | Path) -> Iterator[None]:
    original_choose_mode = eng.choose_mode
    original_choose_buffer = eng.choose_buffer
    original_load_draws = eng.load_draws
    eng.choose_mode = lambda: game_mode
    eng.choose_buffer = lambda: buffer_size
    eng.load_draws = lambda _path: original_load_draws(str(temp_csv_path))
    try:
        yield
    finally:
        eng.choose_mode = original_choose_mode
        eng.choose_buffer = original_choose_buffer
        eng.load_draws = original_load_draws


def _load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def build_replay_record(
    *,
    results: dict[str, Any],
    target_draw: Any,
    target_numbers: tuple[int, ...],
    game_mode: str,
    source_csv: str | Path,
    temp_csv_info: dict[str, Any],
    csv_hash_before: str,
    csv_hash_after: str,
    warnings: list[str],
) -> dict[str, Any]:
    prediction_draw = temp_csv_info.get("csv_train_until_draw")
    combos = extract_predicted_combinations(results, limit=10)
    number_scores = extract_number_scores(results)
    graded_combos = grade_combinations(combos, target_numbers)
    graded_numbers = grade_number_scores(number_scores, target_numbers)
    return {
        "record_type": "historical_replay",
        "game_mode": game_mode,
        "prediction_draw": str(prediction_draw),
        "target_draw": str(target_draw),
        "csv_train_until_draw": str(prediction_draw),
        "csv_truth_source": str(source_csv),
        "csv_temp_path": temp_csv_info.get("temp_csv_path"),
        "csv_original_hash_before": csv_hash_before,
        "csv_original_hash_after": csv_hash_after,
        "leakage_passed": bool(temp_csv_info.get("leakage_passed")) and csv_hash_before == csv_hash_after,
        "engine_used": "local_cruncher_v4_deep_stacking.run_pipeline",
        "uses_main_engine": True,
        "score_kind": results.get("score_kind"),
        "target_numbers": list(target_numbers),
        "top_combinations": graded_combos,
        "number_score_errors": graded_numbers,
        "score_bucket_analysis": {},
        "combo_profile_analysis": {},
        "expert_miscalibration": {},
        "monte_carlo_diversity": {
            "top_combinations": len(graded_combos),
            "unique_numbers_used": len({number for combo in graded_combos for number in combo.get("numbers", [])}),
        },
        "warnings": warnings,
    }


def run_single_replay(
    *,
    source_csv: str | Path,
    game_mode: str,
    target_draw: int,
    output_dir: str | Path,
    intensity: str,
    buffer_size: int,
) -> dict[str, Any]:
    csv_hash_before = file_sha256(source_csv)
    warnings: list[str] = []
    full_draws = load_csv_draws(source_csv, mode=game_mode)
    target = next((draw for draw in full_draws if _parse_int(draw.draw_id) == target_draw), None)
    if target is None:
        raise ValueError(f"Target draw {target_draw} no existe en CSV completo.")
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    original_cwd = Path.cwd()
    with replay_environment(intensity):
        calibrated, eng = load_main_engine_after_env()
        with tempfile.TemporaryDirectory(prefix="fisicapapa_replay_") as tmp:
            tmp_path = Path(tmp)
            temp_csv = tmp_path / Path(source_csv).name
            temp_info = write_truncated_csv(source_csv, target_draw, temp_csv)
            if not temp_info.get("leakage_passed"):
                raise RuntimeError(f"Replay leakage guard failed: {temp_info}")
            try:
                os.chdir(tmp_path)
                with patched_engine(eng, game_mode, buffer_size, temp_csv):
                    eng.run_pipeline()
                generated = tmp_path / "resultados.json"
                if not generated.exists():
                    raise RuntimeError("El motor principal no genero resultados.json en workdir temporal.")
                results = _load_json(generated)
            finally:
                os.chdir(original_cwd)
            csv_hash_after = file_sha256(source_csv)
            if csv_hash_before != csv_hash_after:
                warnings.append("CSV original cambio durante replay; record queda no confiable.")
            record = build_replay_record(
                results=results,
                target_draw=target.draw_id,
                target_numbers=target.numbers,
                game_mode=game_mode,
                source_csv=source_csv,
                temp_csv_info=temp_info,
                csv_hash_before=csv_hash_before,
                csv_hash_after=csv_hash_after,
                warnings=warnings,
            )
            snapshot = dict(results)
            snapshot["replay_record"] = record
            snapshot["snapshot_metadata"] = {
                "source": "historical_replay",
                "created_at": _utc_now(),
                "uses_main_engine": True,
                "target_draw": str(target.draw_id),
                "csv_train_until_draw": temp_info.get("csv_train_until_draw"),
            }
            target_file = output_path / f"replay_{game_mode}_{record['prediction_draw']}_to_{target.draw_id}.json"
            target_file.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
            record["snapshot_path"] = str(target_file)
            record["cwd_restored"] = Path.cwd() == original_cwd
            record["intensity"] = intensity
            record["engine_module_reloaded_after_env"] = True
            record["calibrated_runner_used"] = getattr(calibrated, "__name__", "local_cruncher_v4_2_calibrated")
            return record


def run_replay_lab(
    *,
    csv_path: str | Path,
    game_mode: str,
    start_draw: int | None,
    end_draw: int | None,
    max_targets: int,
    intensity: str,
    output_dir: str | Path,
    dry_run: bool,
    buffer_size: int,
) -> dict[str, Any]:
    targets = select_targets(csv_path, start_draw=start_draw, end_draw=end_draw, max_targets=max_targets)
    summary: dict[str, Any] = {
        "version": "V4.3.2-historical-replay-analysis",
        "generated_at": _utc_now(),
        "csv_path": str(csv_path),
        "game_mode": game_mode,
        "intensity": intensity,
        "dry_run": dry_run,
        "targets": targets,
        "records": [],
        "failures": [],
    }
    if dry_run:
        summary["planned_temp_csvs"] = [
            {"target_draw": target, "rule": f"train draws < {target}"}
            for target in targets
        ]
        Path("v4_replay_analysis.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        return summary
    for target in targets:
        try:
            summary["records"].append(run_single_replay(
                source_csv=csv_path,
                game_mode=game_mode,
                target_draw=target,
                output_dir=output_dir,
                intensity=intensity,
                buffer_size=buffer_size,
            ))
        except Exception as exc:
            summary["failures"].append({"target_draw": target, "reason": str(exc)})
    if summary["records"]:
        add_result = add_replay_records(summary["records"])
        memory = load_replay_memory("v4_replay_memory.json")
        summary["replay_memory_update"] = {key: value for key, value in add_result.items() if key != "memory"}
        summary["replay_prior_audit"] = build_replay_prior_audit(memory)
    Path("v4_replay_analysis.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay historico anti-leakage usando el motor principal.")
    parser.add_argument("--csv", required=True)
    parser.add_argument("--game-mode", required=True, choices=["melate", "revancha"])
    parser.add_argument("--start-draw", type=int)
    parser.add_argument("--end-draw", type=int)
    parser.add_argument("--max-targets", type=int, default=3)
    parser.add_argument("--intensity", choices=sorted(INTENSITY_ENV), default="replay_fast")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output-dir", default="replay_archive")
    parser.add_argument("--buffer-size", type=int, default=200)
    args = parser.parse_args()
    result = run_replay_lab(
        csv_path=args.csv,
        game_mode=args.game_mode,
        start_draw=args.start_draw,
        end_draw=args.end_draw,
        max_targets=max(1, args.max_targets),
        intensity=args.intensity,
        output_dir=args.output_dir,
        dry_run=args.dry_run,
        buffer_size=args.buffer_size,
    )
    print(json.dumps({key: result.get(key) for key in ("dry_run", "targets", "failures")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
