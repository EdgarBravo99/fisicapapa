#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Parchea local_cruncher_v3.py para que la física de esferas no reciba peso por fe,
sino por evidencia OOS en sorteos ganadores ocultos.

Qué añade:
- Diagnóstico OOS por experto: hits top6/top10/top12, MSE y lift ganador vs no ganador.
- Cap dinámico para physical según evidencia real en walk-forward.
- Redistribución de peso si physical no demuestra señal suficiente.
- Audit trail con explicación del peso físico permitido.

Uso:
  py -X utf8 .\fix_v3_physics_oos_calibration.py
  py -X utf8 .\local_cruncher_v3.py
"""
from pathlib import Path

TARGET = Path("local_cruncher_v3.py")
if not TARGET.exists():
    raise SystemExit(f"No existe {TARGET.resolve()}")

text = TARGET.read_text(encoding="utf-8")

# 1) Constantes después de EXPERT_NAMES.
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

# Calibración OOS: la física de esferas debe ganarse su peso con sorteos ocultos.
PHYSICS_MIN_WEIGHT = 0.025
PHYSICS_MAX_WEIGHT_WEAK = 0.08
PHYSICS_MAX_WEIGHT_MEDIUM = 0.16
PHYSICS_MAX_WEIGHT_STRONG = 0.26
PHYSICS_MAX_WEIGHT_ELITE = 0.34
PHYSICS_RANDOM_TOP10_BASELINE = 6 * 10 / 56
PHYSICS_RANDOM_TOP6_BASELINE = 6 * 6 / 56
'''
if "PHYSICS_MIN_WEIGHT = 0.025" not in text:
    if needle_constants not in text:
        raise SystemExit("No encontré EXPERT_NAMES para insertar constantes de calibración física.")
    text = text.replace(needle_constants, replacement_constants, 1)
    print("Constantes de calibración física insertadas.")
else:
    print("Constantes de calibración física ya existían.")

# 2) Insertar funciones antes de run_optuna.
needle_insert = '''def run_optuna(records: Sequence[FoldRecord]):
'''
insert_block = r'''
def single_expert_oos_diagnostics(records: Sequence[FoldRecord]) -> Dict[str, Dict[str, float]]:
    diagnostics: Dict[str, Dict[str, float]] = {}
    for expert_name in EXPERT_NAMES:
        hits6, hits10, hits12, mses, lifts, actual_means, non_actual_means = [], [], [], [], [], [], []
        for rec in records:
            scores = np.asarray(rec.experts[expert_name], dtype=np.float64)
            order = list(map(int, np.argsort(scores[1:])[::-1] + 1))
            actual = set(rec.actual)
            h6 = len(actual.intersection(order[:6]))
            h10 = len(actual.intersection(order[:10]))
            h12 = len(actual.intersection(order[:12]))
            y = np.zeros(MAX_NUMBER + 1)
            for n in actual:
                y[n] = 1.0
            mse = float(np.mean((y[1:] - scores[1:]) ** 2))
            actual_values = [float(scores[n]) for n in actual]
            non_actual_values = [float(scores[n]) for n in range(1, MAX_NUMBER + 1) if n not in actual]
            actual_mean = float(np.mean(actual_values)) if actual_values else 0.0
            non_actual_mean = float(np.mean(non_actual_values)) if non_actual_values else 0.0
            lift = actual_mean - non_actual_mean
            hits6.append(h6)
            hits10.append(h10)
            hits12.append(h12)
            mses.append(mse)
            lifts.append(lift)
            actual_means.append(actual_mean)
            non_actual_means.append(non_actual_mean)
        diagnostics[expert_name] = {
            "avg_hits_top6": float(np.mean(hits6)) if hits6 else 0.0,
            "avg_hits_top10": float(np.mean(hits10)) if hits10 else 0.0,
            "avg_hits_top12": float(np.mean(hits12)) if hits12 else 0.0,
            "avg_mse": float(np.mean(mses)) if mses else 0.0,
            "winner_lift": float(np.mean(lifts)) if lifts else 0.0,
            "winner_score_mean": float(np.mean(actual_means)) if actual_means else 0.0,
            "non_winner_score_mean": float(np.mean(non_actual_means)) if non_actual_means else 0.0,
        }
    return diagnostics


def estimate_physics_weight_cap(expert_diag: Dict[str, Dict[str, float]]) -> Tuple[float, str]:
    phys = expert_diag.get("physical", {})
    p_top10 = float(phys.get("avg_hits_top10", 0.0))
    p_top6 = float(phys.get("avg_hits_top6", 0.0))
    p_lift = float(phys.get("winner_lift", 0.0))
    p_mse = float(phys.get("avg_mse", 1.0))

    utilities = {}
    for name, row in expert_diag.items():
        utilities[name] = (
            float(row.get("avg_hits_top6", 0.0)) * 2.50
            + float(row.get("avg_hits_top10", 0.0)) * 0.90
            + float(row.get("avg_hits_top12", 0.0)) * 0.35
            + max(0.0, float(row.get("winner_lift", 0.0))) * 1.25
            - float(row.get("avg_mse", 1.0)) * 2.20
        )
    best_name = max(utilities, key=utilities.get) if utilities else "physical"
    best_utility = utilities.get(best_name, 0.0)
    phys_utility = utilities.get("physical", 0.0)
    relative = phys_utility / max(abs(best_utility), 1e-9)

    if p_top10 <= PHYSICS_RANDOM_TOP10_BASELINE * 1.02 and p_lift <= 0:
        return PHYSICS_MAX_WEIGHT_WEAK, (
            f"La física quedó en modo débil: Top10={p_top10:.2f} vs azar={PHYSICS_RANDOM_TOP10_BASELINE:.2f}, "
            f"lift ganador={p_lift:.4f}. Se limita a {PHYSICS_MAX_WEIGHT_WEAK:.0%}."
        )
    if p_top10 < PHYSICS_RANDOM_TOP10_BASELINE * 1.22 or p_lift < 0.010:
        return PHYSICS_MAX_WEIGHT_MEDIUM, (
            f"La física mostró señal moderada: Top10={p_top10:.2f}, lift={p_lift:.4f}. "
            f"Se limita a {PHYSICS_MAX_WEIGHT_MEDIUM:.0%}."
        )
    if relative >= 0.92 and p_top6 >= PHYSICS_RANDOM_TOP6_BASELINE * 1.18 and p_lift >= 0.020:
        return PHYSICS_MAX_WEIGHT_ELITE, (
            f"La física sí explicó ganadores OOS con fuerza: Top6={p_top6:.2f}, Top10={p_top10:.2f}, "
            f"lift={p_lift:.4f}, utilidad relativa={relative:.2f}. Puede subir hasta {PHYSICS_MAX_WEIGHT_ELITE:.0%}."
        )
    return PHYSICS_MAX_WEIGHT_STRONG, (
        f"La física fue útil pero no dominante: Top6={p_top6:.2f}, Top10={p_top10:.2f}, "
        f"lift={p_lift:.4f}, MSE={p_mse:.4f}. Se limita a {PHYSICS_MAX_WEIGHT_STRONG:.0%}."
    )


def apply_physics_oos_cap(weights: Dict[str, float], physics_cap: float) -> Dict[str, float]:
    w = {k: max(0.0, float(weights.get(k, 0.0))) for k in EXPERT_NAMES}
    total = sum(w.values()) or 1.0
    w = {k: v / total for k, v in w.items()}
    cap = max(PHYSICS_MIN_WEIGHT, min(float(physics_cap), PHYSICS_MAX_WEIGHT_ELITE))
    if w.get("physical", 0.0) <= cap:
        return w
    excess = w["physical"] - cap
    w["physical"] = cap
    receivers = [k for k in EXPERT_NAMES if k != "physical"]
    receiver_total = sum(w[k] for k in receivers)
    if receiver_total <= 1e-12:
        for k in receivers:
            w[k] += excess / len(receivers)
    else:
        for k in receivers:
            w[k] += excess * (w[k] / receiver_total)
    total = sum(w.values()) or 1.0
    return {k: w[k] / total for k in EXPERT_NAMES}

'''
if "def single_expert_oos_diagnostics" not in text:
    if needle_insert not in text:
        raise SystemExit("No encontré run_optuna para insertar diagnósticos físicos.")
    text = text.replace(needle_insert, insert_block + needle_insert, 1)
    print("Funciones de diagnóstico OOS físico insertadas.")
else:
    print("Funciones de diagnóstico OOS físico ya existían.")

# 3) Reemplazar run_optuna completo por versión calibrada.
start = text.find("def run_optuna(records: Sequence[FoldRecord]):")
end = text.find("\n\n# ═══════════════════════════════════════════════════════\n# MONTE CARLO GPU", start)
if start == -1 or end == -1:
    raise SystemExit("No pude localizar el bloque run_optuna completo.")
current_block = text[start:end]
new_run_optuna = r'''def run_optuna(records: Sequence[FoldRecord]):
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    expert_diag = single_expert_oos_diagnostics(records)
    physics_cap, physics_audit = estimate_physics_weight_cap(expert_diag)

    def objective(trial):
        raw = {name: trial.suggest_float(name, 0.001, 1.0, log=True) for name in EXPERT_NAMES}
        weights = normalize_trial_weights(raw)
        weights = apply_physics_oos_cap(weights, physics_cap)
        if "ensemble_diversity_penalty" in globals():
            diversity_penalty = ensemble_diversity_penalty(weights)
        else:
            diversity_penalty = 0.0
        metrics = evaluate_weights(records, weights)
        return (
            metrics["avg_hits"] * 2.50
            + metrics["avg_hits_top10"] * 0.90
            + metrics["avg_hits_top12"] * 0.35
            - metrics["avg_mse"] * 2.20
            - diversity_penalty
        )

    sampler = optuna.samplers.TPESampler(seed=RANDOM_SEED, multivariate=True, group=True)
    study = optuna.create_study(direction="maximize", sampler=sampler)
    study.optimize(objective, n_trials=OPTUNA_TRIALS, show_progress_bar=False)
    weights = apply_physics_oos_cap(normalize_trial_weights(study.best_params), physics_cap)
    metrics = evaluate_weights(records, weights)
    top_trials = []
    for tr in sorted(study.trials, key=lambda t: t.value if t.value is not None else -999, reverse=True)[:8]:
        if tr.value is None:
            continue
        trial_weights = apply_physics_oos_cap(normalize_trial_weights(tr.params), physics_cap)
        top_trials.append({
            "value": round(float(tr.value), 6),
            "weights": {k: round(v, 6) for k, v in trial_weights.items()},
        })
    sorted_weights = sorted(weights.items(), key=lambda kv: kv[1], reverse=True)
    leader, leader_w = sorted_weights[0]
    phys = expert_diag.get("physical", {})
    active_experts = sum(1 for _, v in sorted_weights if v >= 0.055)
    audit = (
        f"Optuna ejecutó {len(study.trials)} pruebas sobre backtesting ciego secuencial. "
        f"El experto dominante fue {human_expert_name(leader)} con {leader_w:.1%} del peso neto. "
        f"Calibración física OOS: {physics_audit} "
        f"Métricas físicas ganadoras: Top6={phys.get('avg_hits_top6', 0):.2f}, "
        f"Top10={phys.get('avg_hits_top10', 0):.2f}, lift={phys.get('winner_lift', 0):.4f}, "
        f"MSE={phys.get('avg_mse', 0):.4f}. "
        f"Expertos activos: {active_experts}/{len(EXPERT_NAMES)}. "
        f"La selección maximizó aciertos OOS recientes, penalizó MSE y dejó que la física pese solo si explicó sorteos ganadores ocultos."
    )
    metrics["expert_diagnostics"] = {
        name: {k: round(float(v), 6) for k, v in row.items()}
        for name, row in expert_diag.items()
    }
    metrics["physics_calibration"] = {
        "cap": round(float(physics_cap), 6),
        "audit": physics_audit,
        "physical_final_weight": round(float(weights.get("physical", 0.0)), 6),
    }
    return weights, metrics, top_trials, audit
'''
if "Calibración física OOS" not in current_block:
    text = text[:start] + new_run_optuna + text[end:]
    print("run_optuna reemplazado con calibración física OOS.")
else:
    print("run_optuna ya tenía calibración física OOS.")

# 4) Exportar en resultados.json campos específicos de diagnóstico si existe el bloque result.
needle_result = '''        "walk_forward": {
            "window_size": LSTM_WINDOW,
            "steps": len(oos_records),
            "avg_hits": round(float(wf_metrics["avg_hits"]), 6),
            "avg_hits_top10": round(float(wf_metrics["avg_hits_top10"]), 6),
            "avg_hits_top12": round(float(wf_metrics["avg_hits_top12"]), 6),
            "avg_mse": round(float(wf_metrics["avg_mse"]), 8),
            "rows": wf_metrics["rows"],
        },
'''
replacement_result = '''        "walk_forward": {
            "window_size": LSTM_WINDOW,
            "steps": len(oos_records),
            "avg_hits": round(float(wf_metrics["avg_hits"]), 6),
            "avg_hits_top10": round(float(wf_metrics["avg_hits_top10"]), 6),
            "avg_hits_top12": round(float(wf_metrics["avg_hits_top12"]), 6),
            "avg_mse": round(float(wf_metrics["avg_mse"]), 8),
            "expert_diagnostics": wf_metrics.get("expert_diagnostics", {}),
            "physics_calibration": wf_metrics.get("physics_calibration", {}),
            "rows": wf_metrics["rows"],
        },
'''
if '"physics_calibration": wf_metrics.get("physics_calibration", {})' not in text:
    if needle_result not in text:
        print("ADVERTENCIA: no encontré bloque walk_forward exacto; no exporté physics_calibration.")
    else:
        text = text.replace(needle_result, replacement_result, 1)
        print("Export walk_forward.physics_calibration agregado.")
else:
    print("Export physics_calibration ya existía.")

TARGET.write_text(text, encoding="utf-8")
print("Parche de calibración física OOS aplicado correctamente.")
