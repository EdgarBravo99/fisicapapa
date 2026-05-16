#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Integra una cartera informativa V3 en local_cruncher_v3.py.

Uso:
  py -X utf8 .\fix_v3_model_portfolio.py
  py -X utf8 .\local_cruncher_v3.py

Exporta en resultados.json:
- model_portfolio.top10
- best_numbers_by_decade
"""
from pathlib import Path

TARGET = Path("local_cruncher_v3.py")
if not TARGET.exists():
    raise SystemExit(f"No existe {TARGET.resolve()}")

text = TARGET.read_text(encoding="utf-8")

if "TOP_MODEL_PORTFOLIO = 10" not in text:
    text = text.replace("TOP_FINAL = 10\n", "TOP_FINAL = 10\nTOP_MODEL_PORTFOLIO = 10\n", 1)

anchor = "def hindsight_log(draws: Sequence[Draw], config: GameConfig, weights: Dict[str, float]):\n"
insert = r'''
def build_best_numbers_by_decade(final_experts: Dict[str, object], weights: Dict[str, float], bundle: ExpertBundle) -> List[Dict]:
    net = weighted_net_score(final_experts, weights)
    groups = [
        ("1-9", range(1, 10)),
        ("10-19", range(10, 20)),
        ("20-29", range(20, 30)),
        ("30-39", range(30, 40)),
        ("40-49", range(40, 50)),
        ("50-56", range(50, 57)),
    ]
    rows = []
    for label, values in groups:
        candidates = []
        for n in values:
            exp = explain_number(n, final_experts, weights, bundle)
            candidates.append({
                "decade": label,
                "number": int(n),
                "score": round(float(net[n] * 100), 6),
                "main_driver": exp["main_driver"],
                "main_driver_human": exp["main_driver_human"],
                "reason": exp["reason"],
                "expert_raw": exp["expert_raw"],
                "effective_weight": round(float(bundle.physics["effective"][n]), 4),
                "physics_bonus": round(float(bundle.physics["bonus"][n]), 4),
                "uses_in_window": int(bundle.physics["uses"][n]),
            })
        candidates.sort(key=lambda x: x["score"], reverse=True)
        best = candidates[0]
        best["alternatives"] = candidates[1:4]
        rows.append(best)
    return rows


def _portfolio_signature(nums: Sequence[int]) -> Tuple[int, int, int, int]:
    values = sorted(int(n) for n in nums)
    evens = sum(1 for n in values if n % 2 == 0)
    lows = sum(1 for n in values if n <= 28)
    decades = len(set((n - 1) // 10 for n in values))
    sum_bucket = sum(values) // 20
    return evens, lows, decades, sum_bucket


def select_model_portfolio_top10(enriched_pool: Sequence[Dict]) -> List[Dict]:
    selected: List[Dict] = []
    used_keys = set()
    used_signatures = set()
    elite = [x for x in enriched_pool[:min(120, len(enriched_pool))] if isinstance(x, dict) and isinstance(x.get("numbers"), list)]

    def clone(item: Dict, source_rank: int, method: str) -> Dict:
        out = dict(item)
        out["portfolio_rank"] = len(selected) + 1
        out["pool_rank"] = source_rank
        out["portfolio_method"] = method
        out["portfolio_reason"] = (
            f"Candidata informativa derivada del pool optimizado V3. "
            f"Pool rank={source_rank}, score neto={float(item.get('score_percent', item.get('net_score', 0) * 100)):.2f}/100. "
            f"La cartera aplica diversidad estructural suave para evitar variantes casi idénticas."
        )
        return out

    for rank, item in enumerate(elite, start=1):
        if len(selected) >= TOP_MODEL_PORTFOLIO:
            break
        nums = tuple(sorted(int(n) for n in item["numbers"]))
        if nums in used_keys:
            continue
        sig = _portfolio_signature(nums)
        if sig in used_signatures:
            continue
        max_overlap = max((len(set(nums).intersection(set(s["numbers"]))) for s in selected), default=0)
        if max_overlap > 4:
            continue
        selected.append(clone(item, rank, "elite_diversified"))
        used_keys.add(nums)
        used_signatures.add(sig)

    for rank, item in enumerate(elite, start=1):
        if len(selected) >= TOP_MODEL_PORTFOLIO:
            break
        nums = tuple(sorted(int(n) for n in item["numbers"]))
        if nums in used_keys:
            continue
        selected.append(clone(item, rank, "elite_score_fill"))
        used_keys.add(nums)

    return selected[:TOP_MODEL_PORTFOLIO]


'''
if "def build_best_numbers_by_decade" not in text:
    if anchor not in text:
        raise SystemExit("No encontré el punto de inserción para funciones de cartera.")
    text = text.replace(anchor, insert + anchor, 1)

old_pool = '''    enriched_pool = [enrich_combo(item, final_bundle.experts, weights, final_bundle, config) for item in ranked[:TOP_EXPORT]]
    top_combos = enriched_pool[:TOP_FINAL]
    physics = final_bundle.physics
    result = {
'''
new_pool = '''    enriched_pool = [enrich_combo(item, final_bundle.experts, weights, final_bundle, config) for item in ranked[:TOP_EXPORT]]
    top_combos = enriched_pool[:TOP_FINAL]
    model_portfolio_top10 = select_model_portfolio_top10(enriched_pool)
    best_decades = build_best_numbers_by_decade(final_bundle.experts, weights, final_bundle)
    physics = final_bundle.physics
    result = {
'''
if "model_portfolio_top10 = select_model_portfolio_top10(enriched_pool)" not in text:
    if old_pool not in text:
        raise SystemExit("No encontré bloque enriched_pool/top_combos.")
    text = text.replace(old_pool, new_pool, 1)

old_export = '''        "max_net_score_found": round(float(top_combos[0]["net_score"] if top_combos else 0), 8),
        "generator_pool": enriched_pool,
        "top_combinations": top_combos,
    }
'''
new_export = '''        "max_net_score_found": round(float(top_combos[0]["net_score"] if top_combos else 0), 8),
        "model_portfolio": {
            "method": "fixed_top10_from_optimized_v3_pool",
            "description": "Cartera informativa de 10 combinaciones derivadas del pool optimizado V3 y diversificadas estructuralmente.",
            "top10": model_portfolio_top10,
        },
        "best_numbers_by_decade": best_decades,
        "generator_pool": enriched_pool,
        "top_combinations": top_combos,
    }
'''
if '"model_portfolio": {' not in text:
    if old_export not in text:
        raise SystemExit("No encontré bloque de exportación JSON.")
    text = text.replace(old_export, new_export, 1)

TARGET.write_text(text, encoding="utf-8")
print("Cartera informativa V3 integrada en local_cruncher_v3.py")
