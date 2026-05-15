#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Patch local_cruncher_v3.py with a physics ablation gate.

Goal: physical should keep high weight only if it improves OOS ensemble performance.
Run:
  py -X utf8 .\fix_v3_physics_ablation_gate.py
  py -X utf8 .\local_cruncher_v3.py
"""
from pathlib import Path

TARGET = Path("local_cruncher_v3.py")
if not TARGET.exists():
    raise SystemExit(f"No existe {TARGET.resolve()}")

text = TARGET.read_text(encoding="utf-8")

if "PHYSICS_ABLATION_MIN_GAIN" not in text:
    marker = ''']

REQUIRED_LIBS = ['''
    insert = ''']

# Guardrails V3: el ensemble debe comportarse como jurado, no como experto único.
MAX_EXPERT_WEIGHT = 0.38
MIN_ACTIVE_EXPERTS = 4
ACTIVE_EXPERT_THRESHOLD = 0.055
DIVERSITY_PENALTY_STRENGTH = 1.35

# Ablación física: physical solo conserva peso alto si mejora el ensemble OOS.
PHYSICS_ABLATION_CONSERVATIVE_CAP = 0.08
PHYSICS_ABLATION_MEDIUM_CAP = 0.14
PHYSICS_ABLATION_STRONG_CAP = 0.22
PHYSICS_ABLATION_ELITE_CAP = 0.30
PHYSICS_ABLATION_MIN_GAIN = 0.035
PHYSICS_ABLATION_STRONG_GAIN = 0.105
PHYSICS_ABLATION_ELITE_GAIN = 0.180

REQUIRED_LIBS = '''
    if marker not in text:
        raise SystemExit("No encontré punto para insertar constantes de ablación.")
    text = text.replace(marker, insert, 1)

old_norm = '''def normalize_trial_weights(params: Dict[str, float]) -> Dict[str, float]:
    clean = {k: max(1e-6, float(params.get(k, 1e-6))) for k in EXPERT_NAMES}
    total = sum(clean.values()) or 1
    return {k: v / total for k, v in clean.items()}
'''
new_norm = '''def normalize_trial_weights(params: Dict[str, float]) -> Dict[str, float]:
    clean = {k: max(1e-6, float(params.get(k, 1e-6))) for k in EXPERT_NAMES}
    total = sum(clean.values()) or 1.0
    w = {k: v / total for k, v in clean.items()}
    return enforce_weight_diversity(w)


def enforce_weight_diversity(weights: Dict[str, float]) -> Dict[str, float]:
    w = {k: max(1e-8, float(weights.get(k, 0.0))) for k in EXPERT_NAMES}
    total = sum(w.values()) or 1.0
    w = {k: v / total for k, v in w.items()}
    excess = 0.0
    for k in EXPERT_NAMES:
        if w[k] > MAX_EXPERT_WEIGHT:
            excess += w[k] - MAX_EXPERT_WEIGHT
            w[k] = MAX_EXPERT_WEIGHT
    if excess > 0:
        receivers = [k for k in EXPERT_NAMES if w[k] < MAX_EXPERT_WEIGHT]
        receiver_total = sum(w[k] for k in receivers) or 1.0
        for k in receivers:
            w[k] += excess * (w[k] / receiver_total)
    total = sum(w.values()) or 1.0
    return {k: w[k] / total for k in EXPERT_NAMES}


def ensemble_diversity_penalty(weights: Dict[str, float]) -> float:
    hhi = sum(float(v) ** 2 for v in weights.values())
    active = sum(1 for v in weights.values() if float(v) >= ACTIVE_EXPERT_THRESHOLD)
    return max(0.0, hhi - 0.24) * DIVERSITY_PENALTY_STRENGTH + max(0, MIN_ACTIVE_EXPERTS - active) * 0.18
'''
if "def enforce_weight_diversity" not in text:
    if old_norm not in text:
        raise SystemExit("No encontré normalize_trial_weights original.")
    text = text.replace(old_norm, new_norm, 1)

helpers_marker = '''def run_optuna(records: Sequence[FoldRecord]):
'''
helpers = r'''
def metrics_utility(metrics: Dict[str, float]) -> float:
    return (
        float(metrics.get("avg_hits", 0.0)) * 2.50
        + float(metrics.get("avg_hits_top10", 0.0)) * 0.90
        + float(metrics.get("avg_hits_top12", 0.0)) * 0.35
        - float(metrics.get("avg_mse", 1.0)) * 2.20
    )


def remove_physics_and_renormalize(weights: Dict[str, float]) -> Dict[str, float]:
    w = {k: max(0.0, float(weights.get(k, 0.0))) for k in EXPERT_NAMES}
    w["physical"] = 0.0
    total = sum(v for k, v in w.items() if k != "physical")
    if total <= 1e-12:
        receivers = [k for k in EXPERT_NAMES if k != "physical"]
        for k in receivers:
            w[k] = 1.0 / len(receivers)
    else:
        for k in EXPERT_NAMES:
            if k != "physical":
                w[k] /= total
    return w


def cap_physics_and_renormalize(weights: Dict[str, float], cap: float) -> Dict[str, float]:
    w = {k: max(0.0, float(weights.get(k, 0.0))) for k in EXPERT_NAMES}
    total = sum(w.values()) or 1.0
    w = {k: v / total for k, v in w.items()}
    cap = max(0.0, min(float(cap), 1.0))
    if w.get("physical", 0.0) <= cap:
        return w
    excess = w["physical"] - cap
    w["physical"] = cap
    receivers = [k for k in EXPERT_NAMES if k != "physical"]
    receiver_total = sum(w[k] for k in receivers) or 1.0
    for k in receivers:
        w[k] += excess * (w[k] / receiver_total)
    total = sum(w.values()) or 1.0
    return {k: w[k] / total for k in EXPERT_NAMES}


def apply_physics_ablation_gate(records: Sequence[FoldRecord], weights: Dict[str, float]):
    with_metrics = evaluate_weights(records, weights)
    without_weights = remove_physics_and_renormalize(weights)
    without_metrics = evaluate_weights(records, without_weights)
    with_u = metrics_utility(with_metrics)
    without_u = metrics_utility(without_metrics)
    gain = with_u - without_u
    original_physical = float(weights.get("physical", 0.0))
    if gain <= 0:
        cap, level, reason = PHYSICS_ABLATION_CONSERVATIVE_CAP, "bloqueada", "quitar física igualó o mejoró el ensemble"
    elif gain < PHYSICS_ABLATION_MIN_GAIN:
        cap, level, reason = PHYSICS_ABLATION_CONSERVATIVE_CAP, "débil", "la mejora por física fue marginal"
    elif gain < PHYSICS_ABLATION_STRONG_GAIN:
        cap, level, reason = PHYSICS_ABLATION_MEDIUM_CAP, "media", "la física aportó, pero no debe dominar"
    elif gain < PHYSICS_ABLATION_ELITE_GAIN:
        cap, level, reason = PHYSICS_ABLATION_STRONG_CAP, "fuerte", "la física mejoró el ensemble con claridad"
    else:
        cap, level, reason = PHYSICS_ABLATION_ELITE_CAP, "élite", "la física mejoró el ensemble de forma sostenida"
    gated = cap_physics_and_renormalize(weights, cap)
    payload = {
        "utility_with_physics": round(float(with_u), 6),
        "utility_without_physics": round(float(without_u), 6),
        "gain_vs_without_physics": round(float(gain), 6),
        "original_physical_weight": round(float(original_physical), 6),
        "final_physical_weight": round(float(gated.get("physical", 0.0)), 6),
        "applied_cap": round(float(cap), 6),
        "level": level,
        "reason": reason,
    }
    audit = (
        f"Ablación física: utilidad con física={with_u:.4f}, sin física={without_u:.4f}, ganancia={gain:.4f}. "
        f"Nivel={level}; {reason}. Peso físico original={original_physical:.1%}, cap={cap:.0%}, final={gated.get('physical', 0.0):.1%}."
    )
    return gated, payload, audit

'''
if "def apply_physics_ablation_gate" not in text:
    if helpers_marker not in text:
        raise SystemExit("No encontré run_optuna para insertar helpers.")
    text = text.replace(helpers_marker, helpers + helpers_marker, 1)

start = text.find("def run_optuna(records: Sequence[FoldRecord]):")
end = text.find("\n\n# ═══════════════════════════════════════════════════════\n# MONTE CARLO GPU", start)
if start == -1 or end == -1:
    raise SystemExit("No localicé run_optuna completo.")
old_block = text[start:end]
new_block = r'''def run_optuna(records: Sequence[FoldRecord]):
    optuna.logging.set_verbosity(optuna.logging.WARNING)

    def objective(trial):
        raw = {name: trial.suggest_float(name, 0.001, 1.0, log=True) for name in EXPERT_NAMES}
        weights = normalize_trial_weights(raw)
        metrics = evaluate_weights(records, weights)
        return metrics_utility(metrics) - ensemble_diversity_penalty(weights)

    sampler = optuna.samplers.TPESampler(seed=RANDOM_SEED, multivariate=True, group=True)
    study = optuna.create_study(direction="maximize", sampler=sampler)
    study.optimize(objective, n_trials=OPTUNA_TRIALS, show_progress_bar=False)
    weights = normalize_trial_weights(study.best_params)
    weights, physics_ablation, physics_ablation_audit = apply_physics_ablation_gate(records, weights)
    metrics = evaluate_weights(records, weights)
    metrics["physics_ablation"] = physics_ablation
    top_trials = []
    for tr in sorted(study.trials, key=lambda t: t.value if t.value is not None else -999, reverse=True)[:8]:
        if tr.value is None:
            continue
        tw = normalize_trial_weights(tr.params)
        tw, _, _ = apply_physics_ablation_gate(records, tw)
        top_trials.append({"value": round(float(tr.value), 6), "weights": {k: round(v, 6) for k, v in tw.items()}})
    sorted_weights = sorted(weights.items(), key=lambda kv: kv[1], reverse=True)
    leader, leader_w = sorted_weights[0]
    active = sum(1 for _, v in sorted_weights if v >= ACTIVE_EXPERT_THRESHOLD)
    audit = (
        f"Optuna ejecutó {len(study.trials)} pruebas OOS. "
        f"Experto dominante: {human_expert_name(leader)} con {leader_w:.1%}. "
        f"Se aplicó guardrail de diversidad y prueba de ablación física. {physics_ablation_audit} "
        f"Expertos activos: {active}/{len(EXPERT_NAMES)}."
    )
    return weights, metrics, top_trials, audit
'''
if "prueba de ablación física" not in old_block:
    text = text[:start] + new_block + text[end:]

old_export = '''            "avg_mse": round(float(wf_metrics["avg_mse"]), 8),
            "rows": wf_metrics["rows"],
'''
new_export = '''            "avg_mse": round(float(wf_metrics["avg_mse"]), 8),
            "physics_ablation": wf_metrics.get("physics_ablation", {}),
            "rows": wf_metrics["rows"],
'''
if '"physics_ablation": wf_metrics.get("physics_ablation", {})' not in text and old_export in text:
    text = text.replace(old_export, new_export, 1)

TARGET.write_text(text, encoding="utf-8")
print("Parche V3 de ablación física aplicado correctamente.")
