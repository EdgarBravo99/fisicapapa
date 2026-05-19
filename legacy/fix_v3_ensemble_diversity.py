#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Parchea local_cruncher_v3.py para evitar que XGBoost u otro experto monopolice Optuna.

Qué añade:
- MAX_EXPERT_WEIGHT = 0.38
- MIN_ACTIVE_EXPERTS = 4
- Penalización de concentración tipo Herfindahl.
- Bonus/penalty por número de expertos activos.
- Clipping + redistribución de pesos después de Optuna.

Uso:
  py -X utf8 .\fix_v3_ensemble_diversity.py
  py -X utf8 .\local_cruncher_v3.py
"""
from pathlib import Path

TARGET = Path("local_cruncher_v3.py")
if not TARGET.exists():
    raise SystemExit(f"No existe {TARGET.resolve()}")

text = TARGET.read_text(encoding="utf-8")

# 1) Constantes de diversidad después de EXPERT_NAMES.
needle_constants = '''EXPERT_NAMES = [
    "physical",
    "temporal",
    "entropy",
    "fourier",
    "bayes",
    "xgboost",
    "lstm",
    "markov",
    "structural",
]
'''
replacement_constants = '''EXPERT_NAMES = [
    "physical",
    "temporal",
    "entropy",
    "fourier",
    "bayes",
    "xgboost",
    "lstm",
    "markov",
    "structural",
]

# Guardrails de jurado: ningún experto debe monopolizar el ensemble.
# XGBoost puede dominar si gana OOS, pero no tapar física, secuencia, Markov, Fourier, etc.
MAX_EXPERT_WEIGHT = 0.38
MIN_ACTIVE_EXPERTS = 4
DIVERSITY_PENALTY_STRENGTH = 1.35
ACTIVE_EXPERT_THRESHOLD = 0.055
'''
if "MAX_EXPERT_WEIGHT = 0.38" not in text:
    if needle_constants not in text:
        raise SystemExit("No encontré EXPERT_NAMES para insertar constantes de diversidad.")
    text = text.replace(needle_constants, replacement_constants, 1)
    print("Constantes de diversidad insertadas.")
else:
    print("Constantes de diversidad ya existían.")

# 2) Reemplaza normalize_trial_weights.
old_norm = '''def normalize_trial_weights(params: Dict[str, float]) -> Dict[str, float]:
    clean = {k: max(1e-6, float(params.get(k, 1e-6))) for k in EXPERT_NAMES}
    total = sum(clean.values()) or 1
    return {k: v / total for k, v in clean.items()}
'''
new_norm = '''def normalize_trial_weights(params: Dict[str, float]) -> Dict[str, float]:
    clean = {k: max(1e-6, float(params.get(k, 1e-6))) for k in EXPERT_NAMES}
    total = sum(clean.values()) or 1
    weights = {k: v / total for k, v in clean.items()}
    return enforce_weight_diversity(weights)


def enforce_weight_diversity(weights: Dict[str, float]) -> Dict[str, float]:
    # Cap duro por experto + redistribución proporcional al resto.
    w = {k: max(1e-8, float(weights.get(k, 0.0))) for k in EXPERT_NAMES}
    total = sum(w.values()) or 1.0
    w = {k: v / total for k, v in w.items()}

    excess = 0.0
    for k in EXPERT_NAMES:
        if w[k] > MAX_EXPERT_WEIGHT:
            excess += w[k] - MAX_EXPERT_WEIGHT
            w[k] = MAX_EXPERT_WEIGHT

    if excess > 0:
        eligible = [k for k in EXPERT_NAMES if w[k] < MAX_EXPERT_WEIGHT]
        eligible_total = sum(w[k] for k in eligible)
        if eligible_total <= 1e-12:
            spread = excess / len(EXPERT_NAMES)
            for k in EXPERT_NAMES:
                w[k] += spread
        else:
            for k in eligible:
                room = MAX_EXPERT_WEIGHT - w[k]
                add = excess * (w[k] / eligible_total)
                w[k] += min(room, add)

    total = sum(w.values()) or 1.0
    return {k: w[k] / total for k in EXPERT_NAMES}


def ensemble_diversity_penalty(weights: Dict[str, float]) -> float:
    # Herfindahl alto = concentración excesiva. El mínimo ideal con 9 expertos es ~0.111.
    hhi = sum(float(v) ** 2 for v in weights.values())
    active = sum(1 for v in weights.values() if float(v) >= ACTIVE_EXPERT_THRESHOLD)
    concentration_penalty = max(0.0, hhi - 0.24) * DIVERSITY_PENALTY_STRENGTH
    active_penalty = max(0, MIN_ACTIVE_EXPERTS - active) * 0.18
    return concentration_penalty + active_penalty
'''
if "def ensemble_diversity_penalty" not in text:
    if old_norm not in text:
        raise SystemExit("No encontré normalize_trial_weights original.")
    text = text.replace(old_norm, new_norm, 1)
    print("normalize_trial_weights reemplazado con guardrails.")
else:
    print("Guardrails de normalize_trial_weights ya existían.")

# 3) Penalización en objective.
old_objective_return = '''        return (
            metrics["avg_hits"] * 2.50
            + metrics["avg_hits_top10"] * 0.90
            + metrics["avg_hits_top12"] * 0.35
            - metrics["avg_mse"] * 2.20
        )
'''
new_objective_return = '''        return (
            metrics["avg_hits"] * 2.50
            + metrics["avg_hits_top10"] * 0.90
            + metrics["avg_hits_top12"] * 0.35
            - metrics["avg_mse"] * 2.20
            - ensemble_diversity_penalty(weights)
        )
'''
if "ensemble_diversity_penalty(weights)" not in text:
    if old_objective_return not in text:
        raise SystemExit("No encontré return de objective para parchear.")
    text = text.replace(old_objective_return, new_objective_return, 1)
    print("Objective de Optuna parcheado con penalización de diversidad.")
else:
    print("Objective ya tenía penalización de diversidad.")

# 4) Mejora audit trail.
old_audit = '''    audit = (
        f"Optuna ejecutó {len(study.trials)} pruebas sobre backtesting ciego secuencial. "
        f"El experto dominante fue {human_expert_name(leader)} con {leader_w:.1%} del peso neto. "
        f"La selección se hizo maximizando aciertos OOS recientes y penalizando MSE; solo se usaron datos hasta T-1 en cada fold."
    )
'''
new_audit = '''    active_experts = sum(1 for _, v in sorted_weights if v >= ACTIVE_EXPERT_THRESHOLD)
    audit = (
        f"Optuna ejecutó {len(study.trials)} pruebas sobre backtesting ciego secuencial. "
        f"El experto dominante fue {human_expert_name(leader)} con {leader_w:.1%} del peso neto. "
        f"Se aplicó guardrail de jurado: máximo {MAX_EXPERT_WEIGHT:.0%} por experto y penalización por concentración. "
        f"Expertos activos: {active_experts}/{len(EXPERT_NAMES)}. "
        f"La selección maximizó aciertos OOS recientes, penalizó MSE y evitó monopolios; solo se usaron datos hasta T-1 en cada fold."
    )
'''
if "guardrail de jurado" not in text:
    if old_audit not in text:
        raise SystemExit("No encontré audit trail original para parchear.")
    text = text.replace(old_audit, new_audit, 1)
    print("Audit trail actualizado.")
else:
    print("Audit trail ya mencionaba guardrail.")

TARGET.write_text(text, encoding="utf-8")
print("Parche de diversidad V3 aplicado correctamente.")
