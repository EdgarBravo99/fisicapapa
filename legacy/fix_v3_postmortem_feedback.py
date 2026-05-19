#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Integra en local_cruncher_v3.py un módulo de post-mortem feedback.

Uso:
  py -X utf8 .\fix_v3_postmortem_feedback.py
  py -X utf8 .\local_cruncher_v3.py

Qué hace al correr local_cruncher_v3.py después del parche:
- Lee resultados.json anterior ANTES de sobrescribirlo.
- Si el CSV ya contiene un sorteo nuevo posterior al buffer_last_draw del JSON anterior,
  compara las combinaciones generadas contra ese sorteo real.
- Audita top_combinations y generator_pool.
- Penaliza suavemente a los expertos que impulsaron números fallidos.
- Refuerza suavemente a los expertos que sí estaban presentes en números acertados.
- Exporta postmortem_feedback en resultados.json.
"""
from pathlib import Path

TARGET = Path("local_cruncher_v3.py")
if not TARGET.exists():
    raise SystemExit(f"No existe {TARGET.resolve()}")

text = TARGET.read_text(encoding="utf-8")

marker = "PHYSICS_ABLATION_ELITE_GAIN = 0.180\n"
insert = """PHYSICS_ABLATION_ELITE_GAIN = 0.180

# Feedback post-mortem: aprende de resultados.json anterior contra el sorteo nuevo del CSV.
POSTMORTEM_LEARNING_RATE = 0.075
POSTMORTEM_MAX_WEIGHT_SHIFT = 0.045
POSTMORTEM_POOL_AUDIT_LIMIT = 80
POSTMORTEM_MISS_PENALTY = 0.70
POSTMORTEM_HIT_REWARD = 1.35
"""
if "POSTMORTEM_LEARNING_RATE" not in text:
    if marker not in text:
        raise SystemExit("No encontré punto para insertar constantes postmortem.")
    text = text.replace(marker, insert, 1)
    print("Constantes postmortem insertadas.")
else:
    print("Constantes postmortem ya existían.")

anchor = "\n\n# ═══════════════════════════════════════════════════════\n# PIPELINE FINAL\n# ═══════════════════════════════════════════════════════\n"
functions = r'''

def load_previous_results_for_feedback(game_mode: str, path: str = "resultados.json") -> Optional[Dict]:
    p = Path(path)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    if data.get("score_kind") != "optuna_weighted_net_score":
        return None
    if data.get("game_mode") != game_mode:
        return None
    return data


def combo_hits_against_draw(numbers: Sequence[int], actual: Sequence[int]) -> Dict:
    nums = sorted(int(n) for n in numbers if 1 <= int(n) <= MAX_NUMBER)
    real = sorted(int(n) for n in actual)
    hit_set = sorted(set(nums).intersection(real))
    miss_set = sorted(set(nums).difference(real))
    return {
        "numbers": nums,
        "hits": len(hit_set),
        "hit_numbers": hit_set,
        "missed_numbers": miss_set,
    }


def _combo_key(numbers: Sequence[int]) -> Tuple[int, ...]:
    return tuple(sorted(int(n) for n in numbers if 1 <= int(n) <= MAX_NUMBER))


def audit_previous_results(previous: Optional[Dict], latest_draw: Draw, game_mode: str) -> Dict:
    base = {
        "applicable": False,
        "applied": False,
        "reason": "No hay resultados.json anterior compatible para auditar.",
        "latest_draw_id": latest_draw.draw_id,
        "latest_draw_numbers": list(latest_draw.numbers),
        "previous_buffer_last_draw": None,
        "summary": {},
        "expert_credit": {name: 0.0 for name in EXPERT_NAMES},
        "expert_penalty": {name: 0.0 for name in EXPERT_NAMES},
        "weight_multiplier": {name: 1.0 for name in EXPERT_NAMES},
        "audited_top_combinations": [],
        "audited_pool_sample": [],
        "audit_log": "",
    }
    if not previous:
        return base
    prev_last = str(previous.get("historical_forgetting", {}).get("buffer_last_draw", ""))
    base["previous_buffer_last_draw"] = prev_last
    if str(latest_draw.draw_id) == prev_last:
        base["reason"] = "El CSV no contiene un sorteo nuevo respecto al resultados.json anterior; no se aplica feedback."
        return base
    if previous.get("game_mode") != game_mode:
        base["reason"] = "El resultados.json anterior corresponde a otro juego; se evita mezclar Melate/Revancha."
        return base

    actual = set(latest_draw.numbers)
    top = previous.get("top_combinations") or []
    pool = previous.get("generator_pool") or []
    unique_pool = []
    seen = set()
    for item in pool:
        nums = item.get("numbers") if isinstance(item, dict) else None
        if not isinstance(nums, list):
            continue
        key = _combo_key(nums)
        if key in seen:
            continue
        seen.add(key)
        unique_pool.append(item)
        if len(unique_pool) >= POSTMORTEM_POOL_AUDIT_LIMIT:
            break

    def audit_item(item: Dict, rank: int) -> Dict:
        nums = item.get("numbers", [])
        hit = combo_hits_against_draw(nums, latest_draw.numbers)
        return {
            "rank": rank,
            "numbers": hit["numbers"],
            "score_percent": item.get("score_percent"),
            "net_score": item.get("net_score"),
            "hits": hit["hits"],
            "hit_numbers": hit["hit_numbers"],
            "missed_numbers": hit["missed_numbers"],
            "plain_route": item.get("plain_route", ""),
        }

    audited_top = [audit_item(item, i + 1) for i, item in enumerate(top[:TOP_FINAL]) if isinstance(item, dict)]
    audited_pool = [audit_item(item, i + 1) for i, item in enumerate(unique_pool) if isinstance(item, dict)]

    credit = {name: 0.0 for name in EXPERT_NAMES}
    penalty = {name: 0.0 for name in EXPERT_NAMES}
    number_score_hit = []
    number_score_miss = []

    for rank, item in enumerate(unique_pool[:POSTMORTEM_POOL_AUDIT_LIMIT], start=1):
        nums = item.get("numbers", []) if isinstance(item, dict) else []
        rank_weight = max(0.25, 1.0 - (rank - 1) / max(1, POSTMORTEM_POOL_AUDIT_LIMIT))
        explanations = item.get("number_explanations") or []
        exp_by_number = {}
        for exp in explanations:
            try:
                exp_by_number[int(exp.get("number"))] = exp
            except Exception:
                pass
        for n in nums:
            exp = exp_by_number.get(int(n), {})
            driver = exp.get("main_driver") or exp.get("winner_component")
            raw = exp.get("expert_raw") if isinstance(exp.get("expert_raw"), dict) else {}
            if int(n) in actual:
                number_score_hit.append(float(item.get("score_percent") or 0.0))
                if driver in credit:
                    credit[driver] += POSTMORTEM_HIT_REWARD * rank_weight
                for k, v in raw.items():
                    if k in credit:
                        credit[k] += 0.18 * float(v) * rank_weight
            else:
                number_score_miss.append(float(item.get("score_percent") or 0.0))
                if driver in penalty:
                    penalty[driver] += POSTMORTEM_MISS_PENALTY * rank_weight
                for k, v in raw.items():
                    if k in penalty:
                        penalty[k] += 0.08 * float(v) * rank_weight

    max_hits_top = max([row["hits"] for row in audited_top] or [0])
    max_hits_pool = max([row["hits"] for row in audited_pool] or [0])
    avg_hits_top = float(np.mean([row["hits"] for row in audited_top])) if audited_top else 0.0
    avg_hits_pool = float(np.mean([row["hits"] for row in audited_pool])) if audited_pool else 0.0
    zero_hit_top = sum(1 for row in audited_top if row["hits"] == 0)
    zero_hit_pool = sum(1 for row in audited_pool if row["hits"] == 0)

    multipliers = {}
    for name in EXPERT_NAMES:
        signal = credit[name] - penalty[name]
        scale = abs(credit[name]) + abs(penalty[name]) + 1.0
        normalized = signal / scale
        delta = max(-POSTMORTEM_MAX_WEIGHT_SHIFT, min(POSTMORTEM_MAX_WEIGHT_SHIFT, POSTMORTEM_LEARNING_RATE * normalized))
        multipliers[name] = round(float(1.0 + delta), 8)

    log = (
        f"Post-mortem aplicado contra sorteo {latest_draw.draw_id}: real={' '.join(map(str, latest_draw.numbers))}. "
        f"Resultados previos venían de buffer_last_draw={prev_last}. "
        f"Top{len(audited_top)}: avg_hits={avg_hits_top:.2f}, max_hits={max_hits_top}, cero_hits={zero_hit_top}. "
        f"Pool auditado {len(audited_pool)}: avg_hits={avg_hits_pool:.2f}, max_hits={max_hits_pool}, cero_hits={zero_hit_pool}. "
        f"El feedback ajusta pesos de expertos de forma suave; no reescribe pesos físicos ni inventa probabilidad."
    )

    base.update({
        "applicable": True,
        "applied": True,
        "reason": "Se encontró sorteo nuevo en CSV posterior al resultados.json anterior.",
        "summary": {
            "top_count": len(audited_top),
            "pool_sample_count": len(audited_pool),
            "avg_hits_top": round(avg_hits_top, 6),
            "avg_hits_pool": round(avg_hits_pool, 6),
            "max_hits_top": int(max_hits_top),
            "max_hits_pool": int(max_hits_pool),
            "zero_hit_top": int(zero_hit_top),
            "zero_hit_pool": int(zero_hit_pool),
            "avg_score_hit_numbers": round(float(np.mean(number_score_hit)), 6) if number_score_hit else 0.0,
            "avg_score_missed_numbers": round(float(np.mean(number_score_miss)), 6) if number_score_miss else 0.0,
        },
        "expert_credit": {k: round(float(v), 6) for k, v in credit.items()},
        "expert_penalty": {k: round(float(v), 6) for k, v in penalty.items()},
        "weight_multiplier": multipliers,
        "audited_top_combinations": audited_top,
        "audited_pool_sample": audited_pool[:25],
        "audit_log": log,
    })
    return base


def apply_postmortem_feedback_to_weights(weights: Dict[str, float], feedback: Dict) -> Dict[str, float]:
    if not feedback or not feedback.get("applied"):
        return weights
    multipliers = feedback.get("weight_multiplier") or {}
    adjusted = {}
    for name in EXPERT_NAMES:
        adjusted[name] = max(1e-8, float(weights.get(name, 0.0)) * float(multipliers.get(name, 1.0)))
    total = sum(adjusted.values()) or 1.0
    adjusted = {k: v / total for k, v in adjusted.items()}
    adjusted = enforce_weight_diversity(adjusted)
    if "physical" in adjusted and adjusted["physical"] > PHYSICS_MAX_WEIGHT_ELITE:
        adjusted = cap_physics_and_renormalize(adjusted, PHYSICS_MAX_WEIGHT_ELITE)
    return adjusted

'''
if "def audit_previous_results(" not in text:
    if anchor not in text:
        raise SystemExit("No encontré sección PIPELINE FINAL para insertar funciones postmortem.")
    text = text.replace(anchor, functions + anchor, 1)
    print("Funciones postmortem insertadas.")
else:
    print("Funciones postmortem ya existían.")

old = '''    all_draws = load_all_draws(csv_path)
    draws, discarded = truncate_recent(all_draws, buffer_size)
    print(f"\nModo: {config.label}")
'''
new = '''    previous_results = load_previous_results_for_feedback(config.mode)
    all_draws = load_all_draws(csv_path)
    draws, discarded = truncate_recent(all_draws, buffer_size)
    print(f"\nModo: {config.label}")
'''
if "previous_results = load_previous_results_for_feedback(config.mode)" not in text:
    if old not in text:
        raise SystemExit("No encontré bloque de carga CSV para insertar previous_results.")
    text = text.replace(old, new, 1)
    print("Lectura de resultados.json anterior integrada.")
else:
    print("Lectura previous_results ya existía.")

old = '''    print("Pesos óptimos:")
    for k, v in sorted(weights.items(), key=lambda kv: kv[1], reverse=True):
        print(f"  {human_expert_name(k):28s}: {v:.2%}")

    print("\n[3/6] Auditando último sorteo conocido sin leakage...")
'''
new = '''    postmortem_feedback = audit_previous_results(previous_results, draws[-1], config.mode)
    if postmortem_feedback.get("applied"):
        print("\n[2.5/6] Retroalimentación post-mortem detectada...")
        print(postmortem_feedback.get("audit_log", ""))
        weights = apply_postmortem_feedback_to_weights(weights, postmortem_feedback)
        optuna_audit += " " + postmortem_feedback.get("audit_log", "")
    else:
        print(f"\n[2.5/6] Sin feedback post-mortem aplicable: {postmortem_feedback.get('reason')}")

    print("Pesos óptimos finales:")
    for k, v in sorted(weights.items(), key=lambda kv: kv[1], reverse=True):
        print(f"  {human_expert_name(k):28s}: {v:.2%}")

    print("\n[3/6] Auditando último sorteo conocido sin leakage...")
'''
if "postmortem_feedback = audit_previous_results" not in text:
    if old not in text:
        raise SystemExit("No encontré bloque de impresión de pesos para insertar feedback.")
    text = text.replace(old, new, 1)
    print("Aplicación de feedback postmortem integrada.")
else:
    print("Aplicación feedback ya existía.")

old = '''        "walk_forward": {
            "window_size": LSTM_WINDOW,
'''
new = '''        "postmortem_feedback": postmortem_feedback,
        "walk_forward": {
            "window_size": LSTM_WINDOW,
'''
if '"postmortem_feedback": postmortem_feedback' not in text:
    if old not in text:
        raise SystemExit("No encontré bloque walk_forward para exportar postmortem_feedback.")
    text = text.replace(old, new, 1)
    print("Export postmortem_feedback integrado.")
else:
    print("Export postmortem_feedback ya existía.")

TARGET.write_text(text, encoding="utf-8")
print("Parche post-mortem aplicado correctamente sobre local_cruncher_v3.py")
