#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Aplica fixes de alineación V4 sobre local_cruncher_v4_deep_stacking.py.

Este patcher existe para mantener el PR #11 seguro cuando no conviene reemplazar
completo el archivo pesado desde la API.

Fixes:
- Corrige mat(draws, MAX_NUMBER) para mapear 1..56 a índices 0..55.
- Mantiene compatibilidad web: score_kind queda como optuna_weighted_net_score.
- Agrega model_version='V4' y v4_score_kind='v4_deep_stacking_meta_score'.
- Agrega game_label y best_numbers_by_decade.
- Agrega campos avg_hits_top10/top12 compatibles con paneles.
"""
from pathlib import Path

TARGET = Path("local_cruncher_v4_deep_stacking.py")
if not TARGET.exists():
    raise SystemExit("No existe local_cruncher_v4_deep_stacking.py")

text = TARGET.read_text(encoding="utf-8")

old = '''def mat(draws: Sequence[Draw], width: int = MAX_NUMBER + 1):
    m = np.zeros((len(draws), width), dtype=np.float64)
    for i, d in enumerate(draws):
        offset = 1 if width == MAX_NUMBER + 1 else 0
        for n in d.numbers:
            m[i, n - offset] = 1.0
    return m
'''
new = '''def mat(draws: Sequence[Draw], width: int = MAX_NUMBER + 1):
    """Binary matrix for draws.

    width=57 -> columns 1..56 are addressed directly and column 0 is unused.
    width=56 -> columns 0..55 represent numbers 1..56. This is used by the
    Transformer, so the number 56 must map to index 55, not 56.
    """
    m = np.zeros((len(draws), width), dtype=np.float64)
    indexed_with_zero_pad = width == MAX_NUMBER + 1
    for i, d in enumerate(draws):
        for n in d.numbers:
            col = n if indexed_with_zero_pad else n - 1
            if 0 <= col < width:
                m[i, col] = 1.0
            else:
                raise IndexError(f"Número fuera de rango para matriz width={width}: n={n}, col={col}")
    return m
'''
if old in text:
    text = text.replace(old, new, 1)
elif "indexed_with_zero_pad" not in text:
    raise SystemExit("No pude reemplazar mat(); estructura inesperada")

# Agregar helper de líderes por década antes de portfolio() si no existe.
insert_before = "def portfolio(pool): return [dict(x, portfolio_rank=i + 1, portfolio_method=\"v4_deep_stacking_diversified\") for i, x in enumerate(pool[:10])]\n"
helper = '''def best_numbers_by_decade(experts, audit, score):
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
            exp = explain_number(n, experts, audit, score)
            candidates.append({
                "decade": label,
                "number": int(n),
                "score": round(float(score[n] * 100), 6),
                "main_driver": exp["main_driver"],
                "main_driver_human": exp["main_driver_human"],
                "reason": exp["reason"],
                "expert_raw": exp["expert_raw"],
                "effective_weight": exp.get("effective_weight"),
                "physics_bonus": exp.get("physics_bonus"),
                "uses_in_window": exp.get("uses_in_window"),
            })
        candidates.sort(key=lambda x: x["score"], reverse=True)
        best = candidates[0]
        best["alternatives"] = candidates[1:4]
        rows.append(best)
    return rows


'''
if "def best_numbers_by_decade(" not in text:
    if insert_before not in text:
        raise SystemExit("No encontré punto para insertar best_numbers_by_decade")
    text = text.replace(insert_before, helper + insert_before, 1)

# Alinear score_kind raíz con bridges existentes y marcar V4 explícitamente.
text = text.replace('''        "source": "local_cruncher_v4_deep_stacking",
        "game_mode": mode,
        "csv_path": csv_path,
        "score_kind": "v4_deep_stacking_meta_score",
''', '''        "source": "local_cruncher_v4_deep_stacking",
        "model_version": "V4",
        "game_mode": mode,
        "game_label": "Melate" if mode == "melate" else "Revancha",
        "csv_path": csv_path,
        "score_kind": "optuna_weighted_net_score",
        "v4_score_kind": "v4_deep_stacking_meta_score",
''')

# Evitar que el bridge interprete que el stacking usa score_kind viejo dentro de deep_stacking.
text = text.replace('''"score_kind": "v4_deep_stacking_meta_score", "regularization"''', '''"score_kind": "v4_deep_stacking_meta_score", "compat_score_kind": "optuna_weighted_net_score", "regularization"''')

# Agregar métricas compatibles top10/top12 al walk_forward.
text = text.replace('''"walk_forward": {"window_size": TRANSFORMER_WINDOW, "steps": len(wf["rows"]), "avg_hits": round(wf["avg_hits"], 6), "avg_mse": round(wf["avg_mse"], 8), "metrics": {"hit_rate": wf["avg_hits"] / PICK_COUNT, "mean_meta_loss": meta_audit.get("best_val_loss"), "last3_error_variance": wf["last3_error_variance"]}, "rows": wf["rows"]},''', '''"walk_forward": {
            "window_size": TRANSFORMER_WINDOW,
            "steps": len(wf["rows"]),
            "avg_hits": round(wf["avg_hits"], 6),
            "avg_hits_top10": round(float(np.mean([r.get("hits_top10", 0) for r in wf["rows"]])) if wf["rows"] else 0.0, 6),
            "avg_hits_top12": round(float(np.mean([len(set(r.get("actual", [])).intersection(set(r.get("predicted_top10", [])))) for r in wf["rows"]])) if wf["rows"] else 0.0, 6),
            "avg_mse": round(wf["avg_mse"], 8),
            "metrics": {"hit_rate": wf["avg_hits"] / PICK_COUNT, "mean_meta_loss": meta_audit.get("best_val_loss"), "last3_error_variance": wf["last3_error_variance"]},
            "rows": wf["rows"]
        },''')

# Agregar best_numbers_by_decade al JSON.
text = text.replace('''        "model_portfolio": {"top10": portfolio(pool)},
        "generator_pool": pool,
''', '''        "model_portfolio": {"top10": portfolio(pool)},
        "best_numbers_by_decade": best_numbers_by_decade(experts, audit, score),
        "generator_pool": pool,
''')

TARGET.write_text(text, encoding="utf-8")
print("Fixes V4 aplicados correctamente a local_cruncher_v4_deep_stacking.py")
