#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
Runner calibrado V4.2 para Melate/Revancha.

Este archivo NO duplica el motor principal. Importa local_cruncher_v4_deep_stacking.py,
inyecta la calibración física observada para el entorno 4214 y ejecuta el pipeline normal V4.2.

Regla física crítica:
- La vida útil/desgaste de las esferas se reinicia tras la calibración/mantenimiento del sorteo 4213.
- Por eso uses_in_window, wear sigmoide y effective_weight se calculan SOLO con sorteos posteriores a 4213.
- El histórico sigue sirviendo para expertos estadísticos, pero NO para desgaste físico de esferas.

Uso recomendado:
    py -X utf8 .\local_cruncher_v4_2_calibrated.py

Si lo abres con doble clic y ocurre un error, este runner NO cierra la consola:
- imprime el traceback completo
- guarda cruncher_error.log
- espera Enter antes de salir
"""

from __future__ import annotations

import importlib
import hashlib
import json
import shutil
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional

from v4_feedback_memory import (
    apply_memory_prior_to_score_vector,
    annotate_results_with_memory,
    build_memory_prior_audit,
    compute_memory_prior,
    detect_csv_path,
    infer_game_mode,
    infer_prediction_draw,
    load_feedback_memory,
    update_feedback_memory_from_archive,
    update_feedback_memory_from_snapshot,
)
from v4_github_sync import (
    GitSyncError,
    import_resultados_history_from_git,
    register_archive_snapshot,
    safe_git_pull_rebase_main,
    sync_outputs_to_github_or_desktop,
)
from tools.v4_history_analyzer import analyze_history

engine = None

SYNC_PATHS = [
    "resultados.json",
    "v4_feedback_memory.json",
    "v4_history_analysis.json",
    "resultados_archive",
    "v4_feedback_memory.py",
    "v4_github_sync.py",
    "tools",
    "v4-feedback-memory-panel.js",
    "README.md",
    "resultados_archive/README.md",
    "index.html",
    "v4-visual-system.css",
    "v4-clean-app.js",
    "v4-results-panels.js",
    "v4-system-diagnostics.js",
    "v4-combo-comparator.js",
]

# Punto de reset físico: la calibración/mantenimiento deja las bolas en una nueva línea base.
# Para predecir después del 4213, el desgaste solo debe contar sorteos con draw_id > 4213.
WEAR_RESET_AFTER_DRAW_ID = 4213
WEAR_RESET_MODE = "draw_id_gt_4213"

# Calibración capturada por el usuario para el estado actual de máquina/esferas.
# Índice 0 reservado para que bola n = CALIBRATED_WEIGHTS_2026_05_17[n].
CALIBRATED_WEIGHTS_2026_05_17 = [
    0,
    4.53, 4.57, 4.58, 4.59, 4.58, 4.55, 4.58, 4.55,
    4.54, 4.54, 4.60, 4.59, 4.53, 4.61, 4.56, 4.58,
    4.54, 4.58, 4.53, 4.54, 4.57, 4.56, 4.52, 4.56,
    4.54, 4.54, 4.54, 4.51, 4.58, 4.59, 4.58, 4.55,
    4.59, 4.58, 4.53, 4.51, 4.59, 4.53, 4.61, 4.54,
    4.58, 4.59, 4.56, 4.61, 4.57, 4.52, 4.59, 4.52,
    4.59, 4.55, 4.56, 4.56, 4.59, 4.57, 4.57, 4.57,
]

WEIGHT_CALIBRATION_METADATA: Dict[str, Any] = {
    "melate": {
        "calibration_id": "weights_2026_05_17_reset_after_draw_4213",
        "game_mode": "melate",
        "draw_id": "4213",
        "calibration_context_draw_id": "4214",
        "calibration_date": "2026-05-17",
        "basis": "Pesaje proporcionado por usuario; vida útil física reiniciada después del sorteo 4213.",
        "maintenance_note": "Tras mantenimiento/calibración, el desgaste físico de esferas no debe heredar usos históricos.",
        "wear_reset_after_draw_id": WEAR_RESET_AFTER_DRAW_ID,
        "wear_reset_mode": WEAR_RESET_MODE,
        "weights_count": 56,
        "min_weight": min(CALIBRATED_WEIGHTS_2026_05_17[1:]),
        "max_weight": max(CALIBRATED_WEIGHTS_2026_05_17[1:]),
        "diff_weight": max(CALIBRATED_WEIGHTS_2026_05_17[1:]) - min(CALIBRATED_WEIGHTS_2026_05_17[1:]),
    },
    "revancha": {
        "calibration_id": "weights_2026_05_17_reset_after_draw_4213",
        "game_mode": "revancha",
        "draw_id": "4213",
        "calibration_context_draw_id": "4214",
        "calibration_date": "2026-05-17",
        "basis": "Pesaje proporcionado por usuario; vida útil física reiniciada después del sorteo 4213.",
        "maintenance_note": "Tras mantenimiento/calibración, el desgaste físico de esferas no debe heredar usos históricos.",
        "wear_reset_after_draw_id": WEAR_RESET_AFTER_DRAW_ID,
        "wear_reset_mode": WEAR_RESET_MODE,
        "weights_count": 56,
        "min_weight": min(CALIBRATED_WEIGHTS_2026_05_17[1:]),
        "max_weight": max(CALIBRATED_WEIGHTS_2026_05_17[1:]),
        "diff_weight": max(CALIBRATED_WEIGHTS_2026_05_17[1:]) - min(CALIBRATED_WEIGHTS_2026_05_17[1:]),
    },
}


def load_engine():
    """Importa el motor principal dentro de try/except para que errores de import no cierren la consola."""
    global engine
    if engine is None:
        engine = importlib.import_module("local_cruncher_v4_deep_stacking")
    return engine


def parse_draw_id(value: Any) -> Optional[int]:
    try:
        return int(float(str(value).strip()))
    except Exception:
        return None


def filter_draws_after_calibration(draws):
    """Devuelve solo sorteos posteriores al reset físico.

    Esto evita que la vida útil de las bolas herede impactos anteriores al mantenimiento.
    """
    filtered = []
    for draw in draws:
        draw_id = parse_draw_id(getattr(draw, "draw_id", None))
        if draw_id is not None and draw_id > WEAR_RESET_AFTER_DRAW_ID:
            filtered.append(draw)
    return filtered


def apply_weight_calibration() -> None:
    """Inyecta pesos calibrados y reemplaza el cálculo físico para resetear vida útil."""
    eng = load_engine()

    if len(CALIBRATED_WEIGHTS_2026_05_17) != eng.MAX_NUMBER + 1:
        raise RuntimeError(
            f"CALIBRATED_WEIGHTS_2026_05_17 debe tener {eng.MAX_NUMBER + 1} entradas incluyendo índice 0."
        )

    eng.BALL_WEIGHTS["melate"] = CALIBRATED_WEIGHTS_2026_05_17[:]
    eng.BALL_WEIGHTS["revancha"] = CALIBRATED_WEIGHTS_2026_05_17[:]
    eng.WEIGHT_CALIBRATION_METADATA = WEIGHT_CALIBRATION_METADATA

    def calibrated_physical_scores(draws, mode):
        """Cálculo físico calibrado.

        Importante:
        - Los pesos base vienen del pesaje calibrado.
        - uses/wear/effective se calculan solo desde draw_id > 4213.
        - El desgaste sigmoide se normaliza para que uses=0 implique wear=0.
        """
        weights = eng.np.asarray(eng.BALL_WEIGHTS[mode], dtype=eng.np.float64)
        usage_draws = filter_draws_after_calibration(draws)
        uses = eng.counts(usage_draws) if usage_draws else eng.np.zeros(eng.MAX_NUMBER + 1, dtype=eng.np.float64)

        eff = eng.np.zeros(eng.MAX_NUMBER + 1, dtype=eng.np.float64)
        bonus = eng.np.zeros(eng.MAX_NUMBER + 1, dtype=eng.np.float64)
        wear_raw_at_zero = 0.085 / (1 + eng.math.exp(-0.055 * (0 - 60.0)))

        for n in range(1, eng.MAX_NUMBER + 1):
            wear_raw = 0.085 / (1 + eng.math.exp(-0.055 * (uses[n] - 60.0)))
            wear = max(0.0, wear_raw - wear_raw_at_zero)
            eff[n] = weights[n] - wear

        avg = float(eng.np.mean(eff[1:]))
        denominator = max(1, len(usage_draws))
        for n in range(1, eng.MAX_NUMBER + 1):
            recurrent_bonus = 8 if uses[n] / denominator > 0.35 else 0
            bonus[n] = max(-15, min(20, -((eff[n] - avg) / 0.05) * 6 + recurrent_bonus))

        calibration = dict(WEIGHT_CALIBRATION_METADATA.get(mode, {}))
        calibration.update({
            "usage_draws_after_calibration": len(usage_draws),
            "usage_draw_ids_after_calibration": [getattr(d, "draw_id", None) for d in usage_draws[-12:]],
            "wear_formula": "wear=max(0, sigmoid_uses - sigmoid_uses_at_0); uses counted only for draw_id > 4213",
        })

        return eng.minmax(50 + bonus * 1.5), {
            "uses": uses,
            "effective": eff,
            "bonus": bonus,
            "avg_effective": avg,
            "real_weight": weights,
            "base_weight": weights,
            "raw_weight": weights,
            "min_weight": float(eng.np.min(weights[1:])),
            "max_weight": float(eng.np.max(weights[1:])),
            "diff_weight": float(eng.np.ptp(weights[1:])),
            "regulatory_ok": bool(eng.np.ptp(weights[1:]) <= 0.30),
            "calibration": calibration,
        }

    def calibrated_explain_number(n, experts, audit, score):
        raw = {k: float(experts[k][n]) for k in eng.EXPERT_NAMES}
        driver = max(raw.items(), key=lambda kv: kv[1])[0]
        labels = {
            "physical": "fisica de esferas",
            "transformer": "Transformer attention",
            "xgboost": "XGBoost tabular",
            "fourier": "micro-ciclos Fourier",
            "graph": "grafo de co-ocurrencia",
        }
        physics = audit["physics"]
        real_source = physics.get("real_weight", physics.get("base_weight"))
        if real_source is None:
            raise RuntimeError("physics audit no contiene real_weight/base_weight; no se puede exportar calibración física.")
        real_weight = float(real_source[n])
        effective_weight = float(physics["effective"][n])
        uses = int(physics["uses"][n])
        calibration = physics.get("calibration", {})
        return {
            "number": n,
            "main_driver": driver,
            "main_driver_human": labels.get(driver, driver),
            "reason": f"{labels.get(driver, driver)} domina el score local dentro del buffer reciente",
            "meta_score": round(float(score[n] * 100), 6),
            "expert_raw": {k: round(v, 6) for k, v in raw.items()},
            "real_weight": round(real_weight, 4),
            "base_weight": round(real_weight, 4),
            "raw_weight": round(real_weight, 4),
            "effective_weight": round(effective_weight, 4),
            "weight_delta_from_wear": round(real_weight - effective_weight, 6),
            "physics_bonus": round(float(physics["bonus"][n]), 4),
            "uses_in_window": uses,
            "uses_since_calibration": uses,
            "weight_lifecycle_reset_after_draw_id": calibration.get("wear_reset_after_draw_id"),
            "weight_calibration_id": calibration.get("calibration_id"),
            "weight_calibration_date": calibration.get("calibration_date"),
            "weight_calibration_draw_id": calibration.get("draw_id"),
            "weight_calibration_context_draw_id": calibration.get("calibration_context_draw_id"),
        }

    eng.physical_scores = calibrated_physical_scores
    eng.explain_number = calibrated_explain_number


def archive_current_results() -> Optional[Path]:
    """Guarda un snapshot del resultados.json actual antes de sobrescribirlo."""
    source = Path("resultados.json")
    if not source.exists():
        return None
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    raw_text = source.read_text(encoding="utf-8", errors="replace")
    try:
        data = json.loads(raw_text)
        if not isinstance(data, dict):
            raise ValueError("resultados.json no es objeto JSON")
        draw_id = infer_prediction_draw(data) or "unknown"
    except Exception as exc:
        draw_id = "unknown"
        archive_dir = Path("resultados_archive")
        archive_dir.mkdir(exist_ok=True)
        target = archive_dir / f"resultados_unknown_{timestamp}.corrupt.json"
        shutil.copy2(source, target)
        print(f"warning: resultados.json actual no es JSON valido; se archivo copia cruda sin index: {exc}")
        return target
    archive_dir = Path("resultados_archive")
    archive_dir.mkdir(exist_ok=True)
    target = archive_dir / f"resultados_{draw_id}_{timestamp}.json"
    metadata = {
        "source": "local_pre_run_archive",
        "archived_at": datetime.now(timezone.utc).isoformat(),
        "original_path": "resultados.json",
        "content_sha256": hashlib.sha256(raw_text.encode("utf-8", errors="replace")).hexdigest(),
        "prediction_draw": str(draw_id),
        "game_mode": data.get("game_mode"),
        "model_version": data.get("model_version"),
        "score_kind": data.get("score_kind"),
    }
    data["snapshot_metadata"] = metadata
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    register_archive_snapshot(target, metadata, archive_dir, status="available")
    return target


def print_calibration_banner() -> None:
    print("Calibración física V4.2 aplicada:")
    print("  Melate/Revancha -> weights_2026_05_17_reset_after_draw_4213")
    print(
        f"  min={min(CALIBRATED_WEIGHTS_2026_05_17[1:]):.4f}g "
        f"max={max(CALIBRATED_WEIGHTS_2026_05_17[1:]):.4f}g "
        f"diff={max(CALIBRATED_WEIGHTS_2026_05_17[1:]) - min(CALIBRATED_WEIGHTS_2026_05_17[1:]):.4f}g"
    )
    print("  Vida útil/desgaste: RESET después del sorteo 4213; solo cuenta draw_id > 4213")


def prepare_history_memory_prior() -> tuple[dict[str, Any], dict[str, Any]]:
    """Importa historico, califica snapshots y construye prior diagnostico/aplicable."""
    status: dict[str, Any] = {
        "git_pull": {},
        "history_import": {},
        "archive": None,
        "csv_path": None,
        "memory_update": {},
        "history_analysis": {},
        "warnings": [],
    }
    pull = safe_git_pull_rebase_main()
    status["git_pull"] = pull
    for warning in pull.get("warnings", []):
        print("warning:", warning)
        status["warnings"].append(warning)

    history_import = import_resultados_history_from_git("resultados_archive", limit=50)
    status["history_import"] = history_import
    for warning in history_import.get("warnings", []):
        print("warning:", warning)
        status["warnings"].append(warning)
    print(
        "Historico Git: "
        f"importados={history_import.get('snapshots_imported', 0)} "
        f"existentes={history_import.get('snapshots_existing', 0)} "
        f"omitidos={history_import.get('snapshots_omitted', 0)}"
    )

    archived = archive_current_results()
    if archived:
        status["archive"] = str(archived)
        print(f"Snapshot previo guardado en: {archived}")

    csv_path, csv_warnings = detect_csv_path()
    for warning in csv_warnings:
        print("warning:", warning)
        status["warnings"].append(warning)
    if csv_path:
        status["csv_path"] = str(csv_path)
        memory_update = update_feedback_memory_from_archive(
            archive_dir="resultados_archive",
            csv_path=csv_path,
            memory_path="v4_feedback_memory.json",
            dry_run=False,
        )
        status["memory_update"] = memory_update
        for warning in memory_update.get("warnings", []):
            print("warning:", warning)
        print(
            "Memoria historica: "
            f"records_nuevos={memory_update.get('records_new', 0)} "
            f"duplicados={len(memory_update.get('duplicates', []))} "
            f"omitidos={len(memory_update.get('omitted', []))}"
        )
        try:
            analysis = analyze_history("resultados_archive", csv_path=csv_path, output_path="v4_history_analysis.json")
            status["history_analysis"] = analysis.get("summary", {})
        except Exception as exc:
            warning = f"No se pudo generar v4_history_analysis.json: {exc}"
            print("warning:", warning)
            status["warnings"].append(warning)
    else:
        print("feedback_memory: sin CSV revelado; queda diagnostic_only.")

    memory = load_feedback_memory("v4_feedback_memory.json")
    analysis_data = None
    history_path = Path("v4_history_analysis.json")
    if history_path.exists():
        try:
            analysis_data = json.loads(history_path.read_text(encoding="utf-8"))
        except Exception as exc:
            status["warnings"].append(f"Analisis historico ilegible: {exc}")
    prior = compute_memory_prior(memory, analysis_data)
    prior["history_import"] = {
        "attempted": True,
        "snapshots_imported": history_import.get("snapshots_imported", 0),
        "snapshots_existing": history_import.get("snapshots_existing", 0),
        "warnings": history_import.get("warnings", []),
    }
    if not csv_path:
        prior["eligible"] = False
        prior["mode"] = "diagnostic_only"
        prior["reason"] = "Sin CSV revelado; no se instala prior."
    print(f"Memory prior: mode={prior.get('mode')} eligible={prior.get('eligible')} reason={prior.get('reason')}")
    return prior, status


def run_pipeline_calibrated(archive_before: bool = True) -> None:
    eng = load_engine()
    apply_weight_calibration()
    memory_prior, workflow_status = prepare_history_memory_prior() if archive_before else (
        {"eligible": False, "mode": "diagnostic_only", "reason": "Archivo previo desactivado."},
        {},
    )
    original_meta_scores = getattr(eng, "meta_scores", None)
    prior_number_audit: list[dict[str, Any]] = []
    hook_installed = False
    if memory_prior.get("eligible") and original_meta_scores:
        def memory_aware_meta_scores(meta, live_X, experts):
            base_score = original_meta_scores(meta, live_X, experts)
            adjusted_score, audit = apply_memory_prior_to_score_vector(base_score, memory_prior)
            prior_number_audit.clear()
            prior_number_audit.extend(audit)
            return adjusted_score
        eng.meta_scores = memory_aware_meta_scores
        hook_installed = True
        print("memory_prior: hook pre-Monte-Carlo instalado.")
    elif memory_prior.get("eligible"):
        memory_prior["eligible"] = False
        memory_prior["mode"] = "diagnostic_only"
        memory_prior["reason"] = "eng.meta_scores no disponible; no se instala hook."
        print("warning: eng.meta_scores no disponible; pipeline corre normal.")
    try:
        eng.run_pipeline()
        if hook_installed:
            memory_prior["applied"] = True
    except Exception:
        memory_prior["applied"] = False
        if hook_installed:
            print("warning: fallo pipeline con memory_prior; se restaura hook y se relanza error.")
        raise
    finally:
        if hook_installed:
            eng.meta_scores = original_meta_scores
            print("memory_prior: hook restaurado.")
    prior_audit = build_memory_prior_audit(memory_prior, prior_number_audit)
    prior_audit["workflow_status"] = workflow_status
    summary = annotate_results_with_memory(memory_prior=memory_prior, prior_audit=prior_audit)
    if summary:
        print(
            "feedback_memory exportado en resultados.json "
            f"(records={summary.get('records_used')}, modo={summary.get('adjustment_mode')})."
        )
    else:
        print("feedback_memory: resultados.json queda con diagnostico de memoria pendiente.")


def sync_with_github() -> None:
    result = sync_outputs_to_github_or_desktop(SYNC_PATHS, "Update V4.3.1 smart history prior")
    print(f"Rama actual: {result.get('branch')}")
    for warning in result.get("warnings", []):
        print(f"warning: {warning}")
    print(f"GitHub sync: {result.get('reason')}")


def inspect_results() -> None:
    path = Path("resultados.json")
    if not path.exists():
        print("No existe resultados.json para inspeccionar.")
        return
    data = json.loads(path.read_text(encoding="utf-8"))
    print("score_kind:", data.get("score_kind"))
    print("source:", data.get("source"))
    print("model_version:", data.get("model_version"))
    print("game_mode:", data.get("game_mode"))
    print("prediction_draw:", infer_prediction_draw(data))
    print("top_combinations:", len(data.get("top_combinations", []) or []))
    print("generator_pool:", len(data.get("generator_pool", []) or []))
    print("feedback_memory:", data.get("feedback_memory", {}).get("adjustment_mode", "N/D"))


def update_memory_prompt() -> None:
    default_results = "resultados.json"
    raw_results = input(f"Snapshot resultados.json a calificar [{default_results}]: ").strip() or default_results
    results_path = Path(raw_results)
    if not results_path.exists():
        print(f"No existe snapshot: {results_path}")
        return
    try:
        snapshot = json.loads(results_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"No se pudo leer snapshot JSON: {exc}")
        return
    default_csv = str(snapshot.get("csv_path") or "")
    raw_csv = input(f"CSV historico actualizado [{default_csv or 'requerido'}]: ").strip() or default_csv
    if not raw_csv:
        print("CSV requerido. La memoria no usa resultados.json como verdad.")
        return
    mode = input(f"Modo [{infer_game_mode(snapshot)}]: ").strip() or infer_game_mode(snapshot)
    dry_raw = input("Dry-run sin escribir memoria? [s/N]: ").strip().lower()
    dry_run = dry_raw in {"s", "si", "y", "yes"}
    try:
        result = update_feedback_memory_from_snapshot(
            results_path=results_path,
            csv_path=raw_csv,
            mode=mode,
            dry_run=dry_run,
        )
    except Exception as exc:
        print(f"No se pudo calificar memoria: {exc}")
        return
    for warning in result.get("warnings", []):
        print("warning:", warning)
    if not result.get("changed"):
        print("Memoria sin cambios.")
        return
    record = result.get("record") or {}
    print(
        "Examen calificado: "
        f"prediccion {record.get('prediction_draw')} -> real {record.get('target_draw')} "
        f"best_hits={record.get('exam_grade', {}).get('best_hits')}"
    )
    if dry_run:
        print("Dry-run activo: no se escribio v4_feedback_memory.json.")
    else:
        print("v4_feedback_memory.json actualizado con al menos un record real.")


def run() -> None:
    load_engine()
    apply_weight_calibration()
    print_calibration_banner()
    print("\nMELATE LOCAL CRUNCHER V4.3 - RUNNER V4.2 CALIBRADO")
    print("[1] Ejecutar pipeline V4.3 completo")
    print("[2] Inspeccionar resultados.json")
    print("[3] Sincronizar resultados con GitHub")
    print("[4] Salir")
    choice = input("Opcion [1]: ").strip() or "1"
    if choice == "2":
        inspect_results()
    elif choice == "3":
        sync_with_github()
    elif choice == "4":
        print("Salida solicitada.")
    else:
        run_pipeline_calibrated(archive_before=True)
        upload = input("Subir resultados.json, memoria y snapshot a GitHub? [s/N]: ").strip().lower()
        if upload in {"s", "si", "y", "yes"}:
            sync_with_github()


def main() -> None:
    try:
        run()
    except KeyboardInterrupt:
        print("\nEjecución cancelada por el usuario.")
    except Exception:
        error_text = traceback.format_exc()
        print("\n" + "=" * 80)
        print("ERROR EN local_cruncher_v4_2_calibrated.py")
        print("=" * 80)
        print(error_text)
        log_path = Path("cruncher_error.log")
        log_path.write_text(error_text, encoding="utf-8")
        print(f"\nSe guardó el detalle en: {log_path.resolve()}")
        print("Copia ese archivo o pega aquí el traceback para corregir la causa exacta.")
    finally:
        try:
            input("\nPresiona ENTER para cerrar...")
        except Exception:
            pass


if __name__ == "__main__":
    main()
