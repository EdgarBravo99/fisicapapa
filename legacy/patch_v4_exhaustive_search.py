#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reemplaza Monte Carlo V4 por búsqueda exhaustiva determinística.

- Corrige mat() si sigue vulnerable al número 56.
- Agrega búsqueda exhaustiva con itertools.combinations.
- Usa batches para no saturar RAM/VRAM.
- Usa CuPy si está disponible para scoring vectorizado; fallback NumPy.
- Cambia run_pipeline para llamar exhaustive_search(score, audit['graph']).
"""
from __future__ import annotations

from pathlib import Path
import re

TARGET = Path("local_cruncher_v4_deep_stacking.py")
if not TARGET.exists():
    raise SystemExit("local_cruncher_v4_deep_stacking.py not found")

s = TARGET.read_text(encoding="utf-8")

# Imports.
if "from itertools import combinations, islice" not in s:
    s = s.replace("import gc\n", "import gc\nfrom itertools import combinations, islice\n", 1)

# Constants.
if "EXHAUSTIVE_TOTAL" not in s:
    s = s.replace(
        "MC_BATCH = env_int(\"MELATE_V4_MC_BATCH\", 150_000, 1_000, 1_000_000)\n",
        "MC_BATCH = env_int(\"MELATE_V4_MC_BATCH\", 150_000, 1_000, 1_000_000)\n"
        "EXHAUSTIVE_TOTAL = 32_468_436\n"
        "EXHAUSTIVE_BATCH = env_int(\"MELATE_V4_EXHAUSTIVE_BATCH\", 500_000, 25_000, 1_000_000)\n"
        "EXHAUSTIVE_KEEP_PER_BATCH = env_int(\"MELATE_V4_EXHAUSTIVE_KEEP\", 1000, 100, 5000)\n",
        1,
    )

# Robust mat fix.
if "col = n if indexed_with_zero_pad else n - 1" not in s:
    new_mat = '''def mat(draws: Sequence[Draw], width: int = MAX_NUMBER + 1):
    m = np.zeros((len(draws), width), dtype=np.float64)
    indexed_with_zero_pad = width == MAX_NUMBER + 1
    for i, d in enumerate(draws):
        for n in d.numbers:
            col = n if indexed_with_zero_pad else n - 1
            if 0 <= col < width:
                m[i, col] = 1.0
            else:
                raise IndexError(f"matrix width={width}, value={n}, col={col}")
    return m
'''
    s, count = re.subn(r"def mat\(draws: Sequence\[Draw\], width: int = MAX_NUMBER \+ 1\):\n(?:    .*\n)*?    return m\n", new_mat, s, count=1)
    if count != 1:
        raise SystemExit("Could not patch mat()")

new_functions = r'''

def batched_combinations(iterator, batch_size):
    while True:
        batch = list(islice(iterator, batch_size))
        if not batch:
            break
        yield batch


def structural_batch_xp(combos, xp):
    arr = combos.astype(xp.float32)
    evens = xp.sum((combos % 2) == 0, axis=1).astype(xp.float32)
    lows = xp.sum(combos <= 28, axis=1).astype(xp.float32)
    sums = xp.sum(arr, axis=1)
    decades = ((combos - 1) // 10).astype(xp.int32)
    decade_count = xp.zeros((combos.shape[0],), dtype=xp.float32)
    for d in range(6):
        decade_count += xp.any(decades == d, axis=1).astype(xp.float32)
    parity_score = 1 - xp.abs(evens - 3) / 3
    low_score = 1 - xp.abs(lows - 3) / 3
    decade_score = decade_count / 6
    sum_score = xp.where((sums >= 110) & (sums <= 240), 1.0, 0.55)
    return xp.clip(0.35 * parity_score + 0.30 * low_score + 0.20 * decade_score + 0.15 * sum_score, 0, 1)


def graph_bonus_batch_xp(combos, graph, xp):
    g = xp.asarray(graph, dtype=xp.float32)
    total = xp.zeros((combos.shape[0],), dtype=xp.float32)
    pairs = 0
    for i in range(PICK_COUNT):
        for j in range(i + 1, PICK_COUNT):
            total += g[combos[:, i], combos[:, j]]
            pairs += 1
    return xp.clip(total / max(1, pairs), 0, 1)


def exhaustive_search(score, graph, batch_size=EXHAUSTIVE_BATCH):
    """Evalúa el 100% del universo 6-de-56 sin duplicados.

    El modelo ya está entrenado; esta función solo rankea todo el espacio según
    el score V4 aprendido. Usa CuPy si está disponible; si no, NumPy CPU.
    """
    xp = cp if (cp is not None and GPU_ARRAYS) else np
    using_gpu = xp is not np
    combo_iter = combinations(range(1, MAX_NUMBER + 1), PICK_COUNT)
    total_batches = math.ceil(EXHAUSTIVE_TOTAL / batch_size)
    best: Dict[Tuple[int, ...], Dict] = {}
    processed = 0
    score_cpu = np.asarray(score, dtype=np.float32)
    graph_cpu = np.asarray(graph, dtype=np.float32)
    score_xp = xp.asarray(score_cpu, dtype=xp.float32)

    print(f"Exhaustive Search V4 activo: {EXHAUSTIVE_TOTAL:,} combinaciones | batch={batch_size:,} | {'GPU/CuPy' if using_gpu else 'CPU/NumPy'}")

    for batch_id, batch in enumerate(batched_combinations(combo_iter, batch_size), start=1):
        combos_cpu = np.asarray(batch, dtype=np.int16)
        combos = xp.asarray(combos_cpu, dtype=xp.int32) if using_gpu else combos_cpu.astype(np.int32, copy=False)
        base = xp.mean(score_xp[combos], axis=1)
        graph_part = graph_bonus_batch_xp(combos, graph_cpu, xp)
        struct_part = structural_batch_xp(combos, xp)
        vals = 0.82 * base + 0.12 * graph_part + 0.06 * struct_part
        keep = min(EXHAUSTIVE_KEEP_PER_BATCH, len(combos_cpu))
        top_idx = xp.argpartition(vals, -keep)[-keep:]
        if using_gpu:
            top_idx_cpu = cp.asnumpy(top_idx)
            vals_cpu = cp.asnumpy(vals[top_idx])
        else:
            top_idx_cpu = top_idx
            vals_cpu = vals[top_idx]
        for local_i, val in zip(top_idx_cpu, vals_cpu):
            key = tuple(int(x) for x in combos_cpu[int(local_i)])
            fval = float(val)
            if key not in best or fval > best[key]["net_score"]:
                best[key] = {"numbers": list(key), "net_score": fval, "source": "v4_deep_stacking_exhaustive_search"}
        if len(best) > 50_000:
            best = dict(sorted(best.items(), key=lambda kv: kv[1]["net_score"], reverse=True)[:15_000])
        processed += len(combos_cpu)
        print(f"Exhaustive Search V4 lote {batch_id}/{total_batches} · evaluadas {processed:,}/{EXHAUSTIVE_TOTAL:,}", end="\r")
        del combos_cpu, combos, vals, top_idx
        cleanup()
    print()
    return sorted(best.values(), key=lambda x: x["net_score"], reverse=True)
'''

if "def exhaustive_search(" not in s:
    marker = "\ndef explain_number(n, experts, audit, score):\n"
    if marker not in s:
        raise SystemExit("Could not find insertion marker before explain_number")
    s = s.replace(marker, new_functions + marker, 1)

s = s.replace("ranked = monte_carlo(score, audit[\"graph\"])", "ranked = exhaustive_search(score, audit[\"graph\"])")
s = s.replace('"total_mc_evaluated": MC_TOTAL,', '"total_mc_evaluated": EXHAUSTIVE_TOTAL,\n        "search_mode": "exhaustive_full_space",')

# Mantener compatibilidad V4/V3 si no se había alineado.
s = s.replace('''        "source": "local_cruncher_v4_deep_stacking",
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

TARGET.write_text(s, encoding="utf-8")
print("OK: V4 exhaustive search patch applied")
