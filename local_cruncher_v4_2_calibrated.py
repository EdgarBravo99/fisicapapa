#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Runner calibrado V4.2 para Melate/Revancha.

Este archivo NO duplica el motor principal. Importa local_cruncher_v4_deep_stacking.py,
inyecta la calibración física observada el 17/05/2026 para el sorteo 4214 y ejecuta
el pipeline normal V4.2.

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

# Calibración capturada por el usuario, fecha 17/05/2026, sorteo 4214.
# Índice 0 reservado para que bola n = CALIBRATED_WEIGHTS_2026_05_17_DRAW_4214[n].
CALIBRATED_WEIGHTS_2026_05_17_DRAW_4214 = [
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
        "calibration_id": "weights_2026_05_17_draw_4214",
        "game_mode": "melate",
        "draw_id": "4214",
        "calibration_date": "2026-05-17",
        "basis": "Pesaje proporcionado por usuario para el sorteo 4214, fecha 17/05/2026.",
        "maintenance_note": "El usuario reporta posible mantenimiento reciente de tómbola/esferas; se reinicia la base física con pesos observados.",
        "weights_count": 56,
        "min_weight": min(CALIBRATED_WEIGHTS_2026_05_17_DRAW_4214[1:]),
        "max_weight": max(CALIBRATED_WEIGHTS_2026_05_17_DRAW_4214[1:]),
        "diff_weight": max(CALIBRATED_WEIGHTS_2026_05_17_DRAW_4214[1:]) - min(CALIBRATED_WEIGHTS_2026_05_17_DRAW_4214[1:]),
    },
    "revancha": {
        "calibration_id": "weights_2026_05_17_draw_4214",
        "game_mode": "revancha",
        "draw_id": "4214",
        "calibration_date": "2026-05-17",
        "basis": "Pesaje proporcionado por usuario para el sorteo 4214, fecha 17/05/2026. Se aplica a Revancha porque el usuario confirmó mantenimiento/estado actual de máquina.",
        "maintenance_note": "El usuario reporta posible mantenimiento reciente de tómbola/esferas; se reinicia la base física con pesos observados.",
        "weights_count": 56,
        "min_weight": min(CALIBRATED_WEIGHTS_2026_05_17_DRAW_4214[1:]),
        "max_weight": max(CALIBRATED_WEIGHTS_2026_05_17_DRAW_4214[1:]),
        "diff_weight": max(CALIBRATED_WEIGHTS_2026_05_17_DRAW_4214[1:]) - min(CALIBRATED_WEIGHTS_2026_05_17_DRAW_4214[1:]),
    },
}


def apply_weight_calibration() -> None:
    """Inyecta pesos calibrados en el motor principal antes de correr el pipeline."""
    if len(CALIBRATED_WEIGHTS_2026_05_17_DRAW_4214) != engine.MAX_NUMBER + 1:
        raise RuntimeError(
            f"CALIBRATED_WEIGHTS_2026_05_17_DRAW_4214 debe tener {engine.MAX_NUMBER + 1} entradas incluyendo índice 0."
        )

    # El usuario confirmó que esta calibración corresponde al estado actual observado al 17/05/2026.
    engine.BALL_WEIGHTS["melate"] = CALIBRATED_WEIGHTS_2026_05_17_DRAW_4214[:]
    engine.BALL_WEIGHTS["revancha"] = CALIBRATED_WEIGHTS_2026_05_17_DRAW_4214[:]
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
        calibration = physics.get("calibration", {})
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
            "weight_calibration_id": calibration.get("calibration_id"),
            "weight_calibration_date": calibration.get("calibration_date"),
            "weight_calibration_draw_id": calibration.get("draw_id"),
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
    print("  Melate/Revancha -> weights_2026_05_17_draw_4214")
    print(f"  min={min(CALIBRATED_WEIGHTS_2026_05_17_DRAW_4214[1:]):.4f}g max={max(CALIBRATED_WEIGHTS_2026_05_17_DRAW_4214[1:]):.4f}g diff={max(CALIBRATED_WEIGHTS_2026_05_17_DRAW_4214[1:]) - min(CALIBRATED_WEIGHTS_2026_05_17_DRAW_4214[1:]):.4f}g")
    print("  Fecha calibración: 2026-05-17 | Sorteo: 4214")
    engine.main()


if __name__ == "__main__":
    main()
