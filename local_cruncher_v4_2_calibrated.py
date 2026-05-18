#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Runner calibrado V4.2 para Melate/Revancha.

Este archivo NO duplica el motor principal. Importa local_cruncher_v4_deep_stacking.py,
inyecta la calibración física de Melate posterior al sorteo 4212 y ejecuta el pipeline
normal V4.2.

Motivo:
- Los pesos base de las esferas cambian tras mantenimiento/pesaje.
- La Web V2 lee real_weight/base_weight/effective_weight desde resultados.json.
- Este runner garantiza que resultados.json salga con pesos físicos trazables.

Uso recomendado:
    py -X utf8 .\local_cruncher_v4_2_calibrated.py
"""

from __future__ import annotations

import importlib
from typing import Dict, Any

engine = importlib.import_module("local_cruncher_v4_deep_stacking")

# Calibración Melate capturada por el usuario, acorde al pesaje conocido después del sorteo 4212.
# Índice 0 reservado para que bola n = MELATE_WEIGHTS_4212[n].
MELATE_WEIGHTS_4212 = [
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
        "calibration_id": "melate_weights_after_draw_4212",
        "game_mode": "melate",
        "basis": "Pesaje proporcionado por usuario, posterior al sorteo 4212 y usado para entorno actual 4214.",
        "maintenance_note": "El usuario reporta posible mantenimiento reciente de tómbola/esferas; se reinicia la base física con pesos observados.",
        "weights_count": 56,
        "min_weight": min(MELATE_WEIGHTS_4212[1:]),
        "max_weight": max(MELATE_WEIGHTS_4212[1:]),
        "diff_weight": max(MELATE_WEIGHTS_4212[1:]) - min(MELATE_WEIGHTS_4212[1:]),
    },
    "revancha": {
        "calibration_id": "legacy_revancha_weights_in_main_engine",
        "game_mode": "revancha",
        "basis": "No se recibió tabla completa de 56 pesos actualizados para Revancha en este cambio.",
        "maintenance_note": "Pendiente actualizar cuando se tenga la lista completa 1-56.",
    },
}


def apply_weight_calibration() -> None:
    """Inyecta pesos calibrados en el motor principal antes de correr el pipeline."""
    if len(MELATE_WEIGHTS_4212) != engine.MAX_NUMBER + 1:
        raise RuntimeError(f"MELATE_WEIGHTS_4212 debe tener {engine.MAX_NUMBER + 1} entradas incluyendo índice 0.")

    engine.BALL_WEIGHTS["melate"] = MELATE_WEIGHTS_4212[:]
    engine.WEIGHT_CALIBRATION_METADATA = WEIGHT_CALIBRATION_METADATA

    original_physical_scores = engine.physical_scores

    def calibrated_physical_scores(draws, mode):
        scores, audit = original_physical_scores(draws, mode)
        weights = engine.np.asarray(engine.BALL_WEIGHTS[mode], dtype=engine.np.float64)
        audit["real_weight"] = weights
        audit["base_weight"] = weights
        audit["raw_weight"] = weights
        audit["calibration"] = WEIGHT_CALIBRATION_METADATA.get(mode, {})
        return scores, audit

    def calibrated_explain_number(n, experts, audit, score):
        raw = {k: float(experts[k][n]) for k in engine.EXPERT_NAMES}
        driver = max(raw.items(), key=lambda kv: kv[1])[0]
        labels = {
            "physical": "fisica de esferas",
            "transformer": "Transformer attention",
            "xgboost": "XGBoost tabular",
            "fourier": "micro-ciclos Fourier",
            "graph": "grafo de co-ocurrencia",
        }
        physics = audit["physics"]
        real_weight = float(physics.get("real_weight", physics.get("base_weight"))[n])
        effective_weight = float(physics["effective"][n])
        uses = int(physics["uses"][n])
        return {
            "number": n,
            "main_driver": driver,
            "main_driver_human": labels[driver],
            "reason": f"{labels[driver]} domina el score local dentro del buffer reciente",
            "meta_score": round(float(score[n] * 100), 6),
            "expert_raw": {k: round(v, 6) for k, v in raw.items()},
            "real_weight": round(real_weight, 4),
            "base_weight": round(real_weight, 4),
            "raw_weight": round(real_weight, 4),
            "effective_weight": round(effective_weight, 4),
            "weight_delta_from_wear": round(real_weight - effective_weight, 6),
            "physics_bonus": round(float(physics["bonus"][n]), 4),
            "uses_in_window": uses,
            "weight_calibration_id": physics.get("calibration", {}).get("calibration_id"),
        }

    original_run_pipeline = engine.run_pipeline

    def calibrated_run_pipeline():
        # Ejecuta el pipeline normal; los hooks anteriores hacen que audit/seed/pool exporten pesos reales.
        return original_run_pipeline()

    engine.physical_scores = calibrated_physical_scores
    engine.explain_number = calibrated_explain_number
    engine.run_pipeline = calibrated_run_pipeline


def main() -> None:
    apply_weight_calibration()
    print("Calibración física V4.2 aplicada:")
    print("  Melate -> melate_weights_after_draw_4212")
    print(f"  min={min(MELATE_WEIGHTS_4212[1:]):.4f}g max={max(MELATE_WEIGHTS_4212[1:]):.4f}g diff={max(MELATE_WEIGHTS_4212[1:]) - min(MELATE_WEIGHTS_4212[1:]):.4f}g")
    print("  Nota: Revancha no se actualizó porque falta tabla completa 1-56.")
    engine.main()


if __name__ == "__main__":
    main()
