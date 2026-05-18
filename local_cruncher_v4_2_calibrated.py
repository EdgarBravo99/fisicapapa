#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
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
import traceback
from pathlib import Path
from typing import Dict, Any, Optional

engine = None

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


def run() -> None:
    eng = load_engine()
    apply_weight_calibration()
    print("Calibración física V4.2 aplicada:")
    print("  Melate/Revancha -> weights_2026_05_17_reset_after_draw_4213")
    print(
        f"  min={min(CALIBRATED_WEIGHTS_2026_05_17[1:]):.4f}g "
        f"max={max(CALIBRATED_WEIGHTS_2026_05_17[1:]):.4f}g "
        f"diff={max(CALIBRATED_WEIGHTS_2026_05_17[1:]) - min(CALIBRATED_WEIGHTS_2026_05_17[1:]):.4f}g"
    )
    print("  Vida útil/desgaste: RESET después del sorteo 4213; solo cuenta draw_id > 4213")
    eng.main()


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
