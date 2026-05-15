#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
local_cruncher_v2.py

Motor local experimental para Melate Pro.

Cambios V2.1:
- Mantiene auto-instalación y XGBoost CUDA.
- Ejecuta Walk-Forward y usa sus resultados para optimizar pesos del ensemble.
- Genera futuro con el modelo final entrenado con TODO el histórico disponible hasta hoy.
- Monte Carlo ahora explora más: mínimo 5M combinaciones y hasta 25M.
- Usa muestreo multi-estrategia: ensemble, XGBoost, Bayes, Fourier y mezcla balanceada.
- Separa datos crudos de score operativo:
  raw_quality = score crudo del modelo.
  confidence = score operativo de selección, NO probabilidad real de ganar.
- Exporta explicaciones humanas para la web.

Uso:
  py .\local_cruncher_v2.py
"""

from __future__ import annotations

import importlib.util
import json
import math
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

REQUIRED_LIBS = [("pandas", "pandas"), ("numpy", "numpy"), ("xgboost", "xgboost"), ("sklearn", "scikit-learn"), ("scipy", "scipy")]

pd = None
np = None
rfft = None
rfftfreq = None
XGBClassifier = None
CalibratedClassifierCV = None

MAX_NUMBER = 56
PICK_COUNT = 6
WINDOW_SIZE = 120
DRIFT_WINDOW = 15
WALK_FORWARD_STEPS = 42
CONFIDENCE_THRESHOLD = 70.0
TARGET_OPERATIONAL_CONFIDENCE = 80.0
TARGET_OPERATIONAL_COMBOS = 10
TARGET_HIGH_CONF_COMBOS = 5
MIN_MC_COMBINATIONS = 5_000_000
MAX_MC_COMBINATIONS = 25_000_000
MC_BATCH_SIZE = 200_000
RANDOM_SEED = 73073
EPS = 1e-12
DRIFT_KL_THRESHOLD = 0.18
SIGMOID = {"L": 0.0, "K": 1.0, "r": 0.09, "n0": 35.0}
DEFAULT_WEIGHTS = {"fourier": 0.28, "bayes": 0.32, "xgboost": 0.40}
WEIGHT_CANDIDATES = [
    {"fourier": 0.28, "bayes": 0.32, "xgboost": 0.40},
    {"fourier": 0.22, "bayes": 0.28, "xgboost": 0.50},
    {"fourier": 0.36, "bayes": 0.24, "xgboost": 0.40},
    {"fourier": 0.24, "bayes": 0.42, "xgboost": 0.34},
    {"fourier": 0.34, "bayes": 0.34, "xgboost": 0.32},
    {"fourier": 0.18, "bayes": 0.36, "xgboost": 0.46},
    {"fourier": 0.42, "bayes": 0.22, "xgboost": 0.36},
]
SAMPLING_STRATEGIES = ["ensemble", "xgboost", "bayes", "fourier", "balanced"]
SAMPLING_TEMPERATURES = [0.70, 0.88, 1.00, 1.22, 1.55]


@dataclass(frozen=True)
class Draw:
    index: int
    draw_id: str
    date: Optional[str]
    numbers: Tuple[int, int, int, int, int, int]
    additional: Optional[int] = None


@dataclass
class Context:
    rows: Sequence[Draw]
    fourier: object
    periods: object
    bayes: object


@dataclass
class State:
    fourier: object
    periods: object
    bayes: object
    xgb_raw: object
    xgb: object
    ensemble: object
    weights: Dict[str, float]
    drift: bool
    kl: float
    h_recent: float
    h_window: float


def dep_exists(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def ensure_deps() -> None:
    missing = [(m, p) for m, p in REQUIRED_LIBS if not dep_exists(m)]
    if missing:
        print("Instalando dependencias necesarias para el hardware, por favor espere...")
    for _, pkg in missing:
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg, "--quiet", "--disable-pip-version-check"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    import_runtime()


def import_runtime() -> None:
    global pd, np, rfft, rfftfreq, XGBClassifier, CalibratedClassifierCV
    import pandas as _pd
    import numpy as _np
    from scipy.fft import rfft as _rfft, rfftfreq as _rfftfreq
    from xgboost import XGBClassifier as _XGBClassifier
    from sklearn.calibration import CalibratedClassifierCV as _CalibratedClassifierCV
    pd, np, rfft, rfftfreq, XGBClassifier, CalibratedClassifierCV = _pd, _np, _rfft, _rfftfreq, _XGBClassifier, _CalibratedClassifierCV


def clear() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def pause() -> None:
    input("\nENTER para continuar...")


def menu() -> None:
    clear()
    print("╔" + "═" * 86 + "╗")
    print("║  MELATE LOCAL CRUNCHER V2.1 · FUTURE FEEDBACK + MONTE CARLO PROFUNDO             ║")
    print("╠" + "═" * 86 + "╣")
    print("║  [1] Ejecutar pipeline completo                                                   ║")
    print("║  [2] Solo sincronizar resultados.json existente                                   ║")
    print("║  [3] Salir                                                                        ║")
    print("╚" + "═" * 86 + "╝")


def parse_int(v):
    try:
        if pd.isna(v):
            return None
        return int(float(str(v).strip()))
    except Exception:
        return None


def detect_columns(df):
    lower = {str(c).lower().strip(): c for c in df.columns}
    groups = [["n1", "n2", "n3", "n4", "n5", "n6"], ["num1", "num2", "num3", "num4", "num5", "num6"], ["numero1", "numero2", "numero3", "numero4", "numero5", "numero6"], ["bola1", "bola2", "bola3", "bola4", "bola5", "bola6"]]
    natural = []
    for group in groups:
        if all(x in lower for x in group):
            natural = [lower[x] for x in group]
            break
    if not natural:
        numeric = []
        for col in df.columns:
            s = pd.to_numeric(df[col], errors="coerce")
            if s.notna().mean() > 0.80 and s.between(1, MAX_NUMBER).mean() > 0.55:
                numeric.append(col)
        if len(numeric) < 6:
            raise ValueError("No pude detectar columnas. Usa n1,n2,n3,n4,n5,n6.")
        natural = numeric[:6]
    draw_col = next((lower[x] for x in ["sorteo", "draw", "draw_id", "concurso", "id"] if x in lower), None)
    date_col = next((lower[x] for x in ["fecha", "date", "draw_date"] if x in lower), None)
    add_col = next((lower[x] for x in ["adicional", "additional", "bonus", "extra"] if x in lower), None)
    return natural, add_col, draw_col, date_col


def load_draws(path="historial.csv"):
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"No existe {csv_path.resolve()}")
    df = pd.read_csv(csv_path)
    natural, add_col, draw_col, date_col = detect_columns(df)
    draws = []
    for _, row in df.iterrows():
        nums = sorted({n for n in (parse_int(row[c]) for c in natural) if n is not None and 1 <= n <= MAX_NUMBER})
        if len(nums) != 6:
            continue
        add = parse_int(row[add_col]) if add_col else None
        draw_id = str(row[draw_col]) if draw_col else str(len(draws))
        date = str(row[date_col]) if date_col else None
        draws.append(Draw(len(draws), draw_id, date, tuple(nums), add))
    ids = [parse_int(d.draw_id) for d in draws]
    if all(x is not None for x in ids) and len(set(ids)) > 1:
        draws = [d for _, d in sorted(zip(ids, draws), key=lambda x: x[0])]
    draws = [Draw(i, d.draw_id, d.date, d.numbers, d.additional) for i, d in enumerate(draws)]
    if len(draws) < WINDOW_SIZE + 1:
        raise ValueError(f"Se requieren mínimo {WINDOW_SIZE + 1} sorteos; hay {len(draws)}")
    print(f"Historial cargado: {len(draws)} sorteos")
    return draws


def mat(draws):
    m = np.zeros((len(draws), MAX_NUMBER + 1), dtype=np.float64)
    for i, d in enumerate(draws):
        m[i, list(d.numbers)] = 1.0
    return m


def counts(draws):
    return np.sum(mat(draws), axis=0) if draws else np.zeros(MAX_NUMBER + 1)


def probs_from_counts(c):
    p = np.zeros(MAX_NUMBER + 1)
    total = float(np.sum(c[1:]))
    if total > 0:
        p[1:] = c[1:] / total
    return p


def minmax(v):
    v = np.asarray(v, dtype=np.float64)
    out = np.zeros_like(v)
    x = np.nan_to_num(v[1:], nan=0, posinf=0, neginf=0)
    lo, hi = float(np.min(x)), float(np.max(x))
    out[1:] = 0.5 if hi - lo <= 1e-12 else (x - lo) / (hi - lo)
    return out


def prior(draws):
    return probs_from_counts(counts(draws))


def wear_sigmoid(n):
    return SIGMOID["L"] + (SIGMOID["K"] - SIGMOID["L"]) / (1 + math.exp(-SIGMOID["r"] * (n - SIGMOID["n0"])))


def fourier_scores(window):
    x = mat(window)[:, 1:]
    x = x - np.mean(x, axis=0, keepdims=True)
    spectrum = rfft(x, axis=0)
    power = np.abs(spectrum) ** 2
    freqs = rfftfreq(x.shape[0], d=1.0)
    scores = np.zeros(MAX_NUMBER + 1)
    periods = np.zeros(MAX_NUMBER + 1)
    if power.shape[0] <= 2:
        scores[1:] = 0.5
        return scores, periods
    usable = power[1:, :]
    uf = freqs[1:]
    idx = np.argmax(usable, axis=0)
    dom = usable[idx, np.arange(MAX_NUMBER)]
    raw = np.zeros(MAX_NUMBER + 1)
    raw[1:] = np.log1p(dom + np.sum(usable, axis=0))
    scores = minmax(raw)
    for i in range(MAX_NUMBER):
        f = float(uf[idx[i]])
        periods[i + 1] = 1 / f if f > EPS else 0
    return scores, periods


def bayes_posterior(window, p0):
    c = counts(window)
    wear = np.zeros(MAX_NUMBER + 1)
    for n in range(1, MAX_NUMBER + 1):
        wear[n] = wear_sigmoid(float(c[n]))
    raw = np.zeros(MAX_NUMBER + 1)
    raw[1:] = p0[1:] * (1 + 2.4 * minmax(wear)[1:]) * (1 + 1.15 * minmax(c)[1:])
    return minmax(probs_from_counts(raw))


def entropy(p):
    q = p[1:]
    q = q[q > 0]
    return float(-np.sum(q * np.log2(q))) if len(q) else 0.0


def kl(p, q):
    pp, qq = p[1:], q[1:]
    mask = pp > 0
    return float(np.sum(pp[mask] * np.log(pp[mask] / np.maximum(qq[mask], EPS)))) if np.any(mask) else 0.0


def drift(window):
    pw = probs_from_counts(counts(window))
    pr = probs_from_counts(counts(window[-DRIFT_WINDOW:]))
    k = kl(pr, pw)
    return bool(k >= DRIFT_KL_THRESHOLD), k, entropy(pr), entropy(pw)


def context(draws, p0, end_idx):
    rows = draws[max(0, end_idx - WINDOW_SIZE):end_idx]
    f, per = fourier_scores(rows)
    b = bayes_posterior(rows, p0)
    return Context(rows, f, per, b)


def last_gaps(window):
    g = np.full(MAX_NUMBER + 1, len(window) + 1, dtype=np.float64)
    for gap, d in enumerate(reversed(window)):
        for n in d.numbers:
            if g[n] == len(window) + 1:
                g[n] = gap
    return g


def rollfreq(m, k):
    return np.mean(m[-min(k, len(m)):], axis=0) if len(m) else np.zeros(MAX_NUMBER + 1)


def features(window, p0, f, b):
    m = mat(window)
    gaps = last_gaps(window)
    nums = np.arange(1, MAX_NUMBER + 1, dtype=np.float64)
    return np.column_stack([nums / MAX_NUMBER, p0[1:], rollfreq(m, 15)[1:], rollfreq(m, 30)[1:], rollfreq(m, 60)[1:], rollfreq(m, WINDOW_SIZE)[1:], np.minimum(gaps[1:], WINDOW_SIZE) / WINDOW_SIZE, 1 / (1 + gaps[1:]), f[1:], b[1:], (nums % 2).astype(float), np.floor((nums - 1) / 10) / 5, (nums > 28).astype(float)]).astype(np.float32)


def training_data(draws, p0, end_idx):
    X, Y = [], []
    for i in range(max(1, end_idx - WINDOW_SIZE), end_idx):
        w = draws[max(0, i - WINDOW_SIZE):i]
        if len(w) < 40:
            continue
        f, _ = fourier_scores(w)
        b = bayes_posterior(w, p0)
        X.append(features(w, p0, f, b))
        y = np.zeros(MAX_NUMBER, dtype=np.int32)
        for n in draws[i].numbers:
            y[n - 1] = 1
        Y.append(y)
    if not X:
        raise ValueError("Dataset insuficiente para entrenar")
    return np.vstack(X), np.concatenate(Y)


def gpu_model():
    return XGBClassifier(n_estimators=260, max_depth=4, learning_rate=0.032, subsample=1.0, colsample_bytree=1.0, min_child_weight=1.0, reg_lambda=0.70, objective="binary:logistic", eval_metric="logloss", scale_pos_weight=(MAX_NUMBER - PICK_COUNT) / PICK_COUNT, tree_method="hist", device="cuda", random_state=RANDOM_SEED, n_jobs=0, verbosity=1)


def calibrator(base):
    try:
        return CalibratedClassifierCV(estimator=base, method="sigmoid", cv=3)
    except TypeError:
        return CalibratedClassifierCV(base_estimator=base, method="sigmoid", cv=3)


def train_model(draws, p0, end_idx):
    X, y = training_data(draws, p0, end_idx)
    print(f"Entrenando XGBoost CUDA calibrado | X={X.shape} | positivos={int(np.sum(y))}")
    model = calibrator(gpu_model())
    model.fit(X, y)
    return model


def combine_components(fourier, bayes, xgb, weights):
    ens = np.zeros(MAX_NUMBER + 1)
    ens[1:] = weights["fourier"] * fourier[1:] + weights["bayes"] * bayes[1:] + weights["xgboost"] * xgb[1:]
    return minmax(ens)


def state_from_context(ctx, p0, model, weights=None):
    weights = weights or DEFAULT_WEIGHTS
    X = features(ctx.rows, p0, ctx.fourier, ctx.bayes)
    xraw = np.zeros(MAX_NUMBER + 1)
    xraw[1:] = model.predict_proba(X)[:, 1]
    xgb = minmax(xraw)
    ens = combine_components(ctx.fourier, ctx.bayes, xgb, weights)
    d, k, hr, hw = drift(ctx.rows)
    return State(ctx.fourier, ctx.periods, ctx.bayes, xraw, xgb, ens, weights, d, k, hr, hw)


def component_winner(st, n):
    comps = {"Fourier": float(st.fourier[n]), "Bayes": float(st.bayes[n]), "XGBoost": float(st.xgb[n])}
    return max(comps.items(), key=lambda kv: kv[1])


def eval_weight_candidate(fourier, bayes, xgb, actual, weights):
    ens = combine_components(fourier, bayes, xgb, weights)
    top6 = set(map(int, np.argsort(ens[1:])[::-1][:6] + 1))
    top10 = set(map(int, np.argsort(ens[1:])[::-1][:10] + 1))
    top12 = set(map(int, np.argsort(ens[1:])[::-1][:12] + 1))
    actual_set = set(actual)
    y = np.zeros(MAX_NUMBER + 1)
    for n in actual_set:
        y[n] = 1.0
    mse = float(np.mean((y[1:] - ens[1:]) ** 2))
    return {"hits6": len(actual_set.intersection(top6)), "hits10": len(actual_set.intersection(top10)), "hits12": len(actual_set.intersection(top12)), "mse": mse, "top6": list(sorted(top6)), "top10": list(sorted(top10))}


def walk_forward_factor(wf, drift_detected):
    avg_top10 = float(wf.get("avg_hits_top10", 0) or 0)
    avg_top12 = float(wf.get("avg_hits_top12", 0) or 0)
    avg_mse = float(wf.get("avg_mse", 0) or 0)
    hit_lift = (0.65 * avg_top10 + 0.35 * avg_top12) / 1.25 if (avg_top10 or avg_top12) else 0.75
    mse_penalty = max(0.82, min(1.08, 1 - max(0, avg_mse - 0.20) * 0.35))
    factor = max(0.82, min(1.20, 0.88 + 0.20 * hit_lift)) * mse_penalty
    if drift_detected:
        factor *= 0.93
    return round(float(max(0.76, min(1.20, factor))), 4)


def walk_forward(draws, p0):
    start = max(WINDOW_SIZE, len(draws) - WALK_FORWARD_STEPS)
    rows, component_cache = [], []
    candidate_stats = {i: {"utility": 0.0, "hits6": [], "hits10": [], "hits12": [], "mse": []} for i in range(len(WEIGHT_CANDIDATES))}
    for idx in range(start, len(draws)):
        ctx = context(draws, p0, idx)
        try:
            model = train_model(draws, p0, idx)
            base_state = state_from_context(ctx, p0, model, DEFAULT_WEIGHTS)
        except Exception as exc:
            rows.append({"draw_id": draws[idx].draw_id, "error": str(exc)})
            continue
        component_cache.append((idx, ctx.fourier, ctx.bayes, base_state.xgb, draws[idx].numbers, base_state.kl, base_state.drift))
        for cand_idx, weights in enumerate(WEIGHT_CANDIDATES):
            ev = eval_weight_candidate(ctx.fourier, ctx.bayes, base_state.xgb, draws[idx].numbers, weights)
            candidate_stats[cand_idx]["hits6"].append(ev["hits6"])
            candidate_stats[cand_idx]["hits10"].append(ev["hits10"])
            candidate_stats[cand_idx]["hits12"].append(ev["hits12"])
            candidate_stats[cand_idx]["mse"].append(ev["mse"])
            candidate_stats[cand_idx]["utility"] += ev["hits6"] * 2.4 + ev["hits10"] * 1.0 + ev["hits12"] * 0.45 - ev["mse"] * 1.8
        print(f"Walk-Forward base {idx-start+1}/{len(draws)-start}: KL={base_state.kl:.5f}")
    if not component_cache:
        return {"window_size": WINDOW_SIZE, "steps": 0, "avg_hits": 0, "avg_hits_top10": 0, "avg_hits_top12": 0, "avg_mse": 0, "optimized_weights": DEFAULT_WEIGHTS, "rows": rows}
    best_idx = max(candidate_stats, key=lambda i: candidate_stats[i]["utility"])
    best_weights = WEIGHT_CANDIDATES[best_idx]
    hits6, hits10, hits12, mses, rows = [], [], [], [], []
    for idx, f, b, xgb, actual, kld, dflag in component_cache:
        ev = eval_weight_candidate(f, b, xgb, actual, best_weights)
        hits6.append(ev["hits6"]); hits10.append(ev["hits10"]); hits12.append(ev["hits12"]); mses.append(ev["mse"])
        rows.append({"draw_id": draws[idx].draw_id, "date": draws[idx].date, "actual": list(draws[idx].numbers), "predicted_top6": ev["top6"], "predicted_top10": ev["top10"], "hits": ev["hits6"], "hits_top10": ev["hits10"], "hits_top12": ev["hits12"], "mse": round(ev["mse"], 6), "kl": round(float(kld), 6), "drift_detected": bool(dflag)})
    scorecards = []
    for idx, weights in enumerate(WEIGHT_CANDIDATES):
        st = candidate_stats[idx]
        scorecards.append({"weights": weights, "utility": round(float(st["utility"]), 6), "avg_hits": round(float(np.mean(st["hits6"])) if st["hits6"] else 0, 4), "avg_hits_top10": round(float(np.mean(st["hits10"])) if st["hits10"] else 0, 4), "avg_hits_top12": round(float(np.mean(st["hits12"])) if st["hits12"] else 0, 4), "avg_mse": round(float(np.mean(st["mse"])) if st["mse"] else 0, 6)})
    scorecards = sorted(scorecards, key=lambda x: x["utility"], reverse=True)
    wf = {"window_size": WINDOW_SIZE, "steps": len(rows), "avg_hits": round(float(np.mean(hits6)) if hits6 else 0, 4), "avg_hits_top10": round(float(np.mean(hits10)) if hits10 else 0, 4), "avg_hits_top12": round(float(np.mean(hits12)) if hits12 else 0, 4), "avg_mse": round(float(np.mean(mses)) if mses else 0, 6), "optimized_weights": best_weights, "weight_scorecards": scorecards, "rows": rows}
    wf["walk_forward_factor"] = walk_forward_factor(wf, any(r.get("drift_detected") for r in rows))
    print(f"Pesos optimizados por Walk-Forward: {best_weights} | avg_top10={wf['avg_hits_top10']} | avg_top12={wf['avg_hits_top12']}")
    return wf


def structure_score(combos):
    combos = np.asarray(combos, dtype=np.float64)
    evens = np.sum((combos % 2) == 0, axis=1)
    lows = np.sum(combos <= 28, axis=1)
    sums = np.sum(combos, axis=1)
    span = (np.max(combos, axis=1) - np.min(combos, axis=1)) / 55
    consec = np.sum(np.diff(combos, axis=1) == 1, axis=1)
    decades = np.array([len(set(((r - 1) // 10).astype(int))) for r in combos], dtype=np.float64)
    return np.clip((1 - np.abs(evens - 3) / 3) * 0.22 + (1 - np.abs(lows - 3) / 3) * 0.20 + (decades / 6) * 0.20 + (1 - np.minimum(consec, 4) / 4) * 0.13 + np.where((sums >= 110) & (sums <= 240), 1, 0.55) * 0.15 + span * 0.10, 0, 1)


def score_batch(st, combos):
    e = np.mean(st.ensemble[combos], axis=1)
    f = np.mean(st.fourier[combos], axis=1)
    b = np.mean(st.bayes[combos], axis=1)
    xr = np.mean(st.xgb_raw[combos], axis=1)
    x = np.mean(st.xgb[combos], axis=1)
    s = structure_score(combos)
    raw = (0.36 * e + 0.25 * x + 0.17 * b + 0.13 * f + 0.09 * s) * 100
    consensus = np.clip(100 * (1 - np.std(np.vstack([x, b, f, s]), axis=0)), 0, 100)
    return raw, consensus, e, xr, x, b, f, s


def sampling_weights(st, strategy, temperature):
    if strategy == "xgboost": base = st.xgb[1:]
    elif strategy == "bayes": base = st.bayes[1:]
    elif strategy == "fourier": base = st.fourier[1:]
    elif strategy == "balanced": base = 0.30 * st.ensemble[1:] + 0.22 * st.xgb[1:] + 0.18 * st.bayes[1:] + 0.18 * st.fourier[1:] + 0.12 * np.linspace(0.65, 1.0, MAX_NUMBER)
    else: base = st.ensemble[1:]
    base = np.maximum(base, EPS)
    base = np.power(base, 1.0 / max(0.20, temperature))
    base = base / np.sum(base)
    return np.log(base).reshape(1, -1).astype(np.float32)


def apply_operational_conf(records, wf_factor, drift_detected):
    raw = np.array([r["raw_quality"] for r in records], dtype=np.float64)
    order = np.argsort(raw)
    ranks = np.empty_like(order, dtype=np.float64)
    ranks[order] = np.arange(len(raw), dtype=np.float64)
    pct = 100 * ranks / max(1, len(raw) - 1)
    drift_penalty = 5 if drift_detected else 0
    for i, r in enumerate(records):
        conf = (0.44 * pct[i] + 0.34 * r["raw_quality"] + 0.22 * r["consensus_score"]) * wf_factor - drift_penalty
        conf = float(max(0, min(96, conf)))
        r["rank_percentile"] = round(float(pct[i]), 6)
        r["confidence"] = conf
        r["operational_confidence"] = conf
        r["confidence_kind"] = "operational_score_not_win_probability"
    return sorted(records, key=lambda x: x["confidence"], reverse=True)


def monte_carlo(st, wf):
    rng = np.random.default_rng(RANDOM_SEED)
    nums = np.arange(1, MAX_NUMBER + 1, dtype=np.int16)
    records = {}
    generated = 0
    wf_factor = float(wf.get("walk_forward_factor") or walk_forward_factor(wf, st.drift))
    round_id = 0
    while generated < MAX_MC_COMBINATIONS:
        strategy = SAMPLING_STRATEGIES[round_id % len(SAMPLING_STRATEGIES)]
        temperature = SAMPLING_TEMPERATURES[(round_id // len(SAMPLING_STRATEGIES)) % len(SAMPLING_TEMPERATURES)]
        logw = sampling_weights(st, strategy, temperature)
        cur = min(MC_BATCH_SIZE, MAX_MC_COMBINATIONS - generated)
        g = rng.gumbel(0, 1, size=(cur, MAX_NUMBER)).astype(np.float32)
        idx = np.argpartition(g + logw, -PICK_COUNT, axis=1)[:, -PICK_COUNT:]
        combos = np.sort(nums[idx], axis=1).astype(np.int16)
        raw, cons, e, xr, x, b, f, s = score_batch(st, combos)
        keep = np.argpartition(raw, -min(1400, cur))[-min(1400, cur):]
        for i in keep:
            key = tuple(int(v) for v in combos[i])
            item = {"numbers": list(key), "raw_quality": float(raw[i]), "consensus_score": float(cons[i]), "ensemble": float(e[i]), "xgboost_raw_mean": float(xr[i]), "xgboost_contrast_mean": float(x[i]), "bayes_mean": float(b[i]), "fourier_mean": float(f[i]), "structure_mean": float(s[i]), "sampling_strategy": strategy, "sampling_temperature": float(temperature), "source": "python_gpu_montecarlo"}
            if key not in records or item["raw_quality"] > records[key]["raw_quality"]:
                records[key] = item
        if len(records) > 25000:
            tmp = apply_operational_conf(list(records.values()), wf_factor, st.drift)
            records = {tuple(x["numbers"]): x for x in tmp[:10000]}
        generated += cur
        round_id += 1
        ranked = apply_operational_conf(list(records.values()), wf_factor, st.drift)
        op70 = sum(1 for r in ranked if r["confidence"] >= CONFIDENCE_THRESHOLD)
        op80 = sum(1 for r in ranked if r["confidence"] >= TARGET_OPERATIONAL_CONFIDENCE)
        print(f"MC: {generated:,}/{MAX_MC_COMBINATIONS:,} | >=70 {op70}/{TARGET_OPERATIONAL_COMBOS} | >=80 {op80}/{TARGET_HIGH_CONF_COMBOS} | {strategy}@{temperature} | WF={wf_factor}", end="\r")
        if generated >= MIN_MC_COMBINATIONS and op70 >= TARGET_OPERATIONAL_COMBOS and op80 >= TARGET_HIGH_CONF_COMBOS:
            break
    print()
    return apply_operational_conf(list(records.values()), wf_factor, st.drift), generated, wf_factor


def human_driver_name(component):
    return {"Fourier": "ciclo reciente", "Bayes": "frecuencia/desgaste reciente", "XGBoost": "patrón aprendido por el modelo"}.get(component, component)


def explain_number(st, n):
    winner, score = component_winner(st, int(n))
    if winner == "Fourier": reason = f"tiene un ciclo reciente visible; periodo estimado {st.periods[int(n)]:.1f} sorteos"
    elif winner == "Bayes": reason = "viene favorecido por frecuencia reciente y desgaste acumulado en ventana corta"
    else: reason = "el modelo lo reconoce como compatible con patrones recientes del histórico"
    return {"number": int(n), "driver": winner, "driver_human": human_driver_name(winner), "driver_score": round(float(score), 6), "reason": reason}


def human_combo_summary(item, st):
    explanations = [explain_number(st, n) for n in item["numbers"]]
    counts_by_driver = {}
    for exp in explanations:
        counts_by_driver[exp["driver_human"]] = counts_by_driver.get(exp["driver_human"], 0) + 1
    dominant = sorted(counts_by_driver.items(), key=lambda kv: kv[1], reverse=True)
    dominant_txt = ", ".join(f"{count} por {name}" for name, count in dominant)
    return f"Esta combinación fue elegida porque el motor encontró una mezcla fuerte y balanceada: {dominant_txt}. Su score crudo fue {item.get('raw_quality', 0):.1f}/100, el consenso entre modelos fue {item.get('consensus_score', 0):.1f}/100 y el score operativo quedó en {item.get('confidence', 0):.1f}/100. El score operativo sirve para ordenar combinaciones; no es probabilidad real de ganar."


def explain_combo(item, st):
    exps = [explain_number(st, n) for n in item["numbers"]]
    route = " | ".join(f"{e['number']}: {e['driver_human']}" for e in exps)
    return {"human_summary": human_combo_summary(item, st), "plain_route": route, "number_explanations": exps, "technical_summary": f"raw_quality={item.get('raw_quality', 0):.2f}; percentil={item.get('rank_percentile', 0):.2f}; consenso={item.get('consensus_score', 0):.2f}; XGB={item.get('xgboost_contrast_mean', 0):.3f}; Bayes={item.get('bayes_mean', 0):.3f}; Fourier={item.get('fourier_mean', 0):.3f}; Estructura={item.get('structure_mean', 0):.3f}."}


def hindsight(draws, p0, weights):
    target = draws[-1]
    ctx = context(draws, p0, len(draws) - 1)
    model = train_model(draws, p0, len(draws) - 1)
    st = state_from_context(ctx, p0, model, weights)
    lines = [f"Auditoría inversa del sorteo {target.draw_id} ({target.date or 'sin fecha'})", f"Combinación real: {' '.join(map(str, target.numbers))}", f"Ventana usada antes del sorteo: {len(ctx.rows)}", f"Pesos aprendidos por Walk-Forward: Fourier={weights['fourier']:.2f}, Bayes={weights['bayes']:.2f}, XGBoost={weights['xgboost']:.2f}", f"Drift={st.drift} KL={st.kl:.6f} H15={st.h_recent:.4f} H120={st.h_window:.4f}"]
    for n in target.numbers:
        exp = explain_number(st, n)
        rank = int(np.where((np.argsort(st.ensemble[1:])[::-1] + 1) == n)[0][0] + 1)
        lines.append(f"Número {n}: explicación={exp['driver_human']}; detalle={exp['reason']}; rank={rank}/56")
    return "\n".join(lines)


def manual_seed(st):
    out = []
    for n in range(1, MAX_NUMBER + 1):
        exp = explain_number(st, n)
        out.append({"number": n, "score": round(float(st.ensemble[n] * 100), 4), "winner_component": exp["driver"], "winner_component_human": exp["driver_human"], "winner_component_score": round(float(exp["driver_score"]), 6), "reason": exp["reason"], "fourier": round(float(st.fourier[n]), 6), "bayes": round(float(st.bayes[n]), 6), "xgboost": round(float(st.xgb[n]), 6), "xgboost_raw": round(float(st.xgb_raw[n]), 8), "period_fft": round(float(st.periods[n]), 4)})
    return sorted(out, key=lambda x: x["score"], reverse=True)


def run_pipeline():
    started = time.perf_counter()
    draws = load_draws("historial.csv")
    p0 = prior(draws)
    print("\n[1/5] Walk-Forward + selección de pesos...")
    wf = walk_forward(draws, p0)
    weights = wf.get("optimized_weights") or DEFAULT_WEIGHTS
    print("\n[2/5] Hindsight humano...")
    hlog = hindsight(draws, p0, weights)
    print(hlog)
    print("\n[3/5] Modelo final CUDA entrenado con histórico completo...")
    ctx = context(draws, p0, len(draws))
    model = train_model(draws, p0, len(draws))
    st = state_from_context(ctx, p0, model, weights)
    print("\n[4/5] Monte Carlo profundo multi-estrategia...")
    ranked, total, wf_factor = monte_carlo(st, wf)
    top = [r for r in ranked if r["confidence"] >= CONFIDENCE_THRESHOLD][:TARGET_OPERATIONAL_COMBOS]
    pool = []
    for i, record in enumerate(ranked[:160], start=1):
        x = dict(record)
        x["rank"] = i
        explanation = explain_combo(x, st)
        x["procedure"] = explanation["human_summary"]
        x["human_explanation"] = explanation["human_summary"]
        x["plain_route"] = explanation["plain_route"]
        x["number_explanations"] = explanation["number_explanations"]
        x["technical_summary"] = explanation["technical_summary"]
        pool.append(x)
    top_enriched = []
    for record in top:
        x = dict(record)
        explanation = explain_combo(x, st)
        x["procedure"] = explanation["human_summary"]
        x["human_explanation"] = explanation["human_summary"]
        x["plain_route"] = explanation["plain_route"]
        x["number_explanations"] = explanation["number_explanations"]
        x["technical_summary"] = explanation["technical_summary"]
        top_enriched.append(x)
    result = {"last_update": datetime.now(timezone.utc).isoformat(), "source": "local_cruncher_v2_1_python_gpu", "confidence_kind": "operational_score_not_win_probability", "target_operational_confidence": TARGET_OPERATIONAL_CONFIDENCE, "drift_detected": bool(st.drift), "hindsight_log": hlog, "procedure_log": f"Se validaron {wf['steps']} pasos Walk-Forward. El motor eligió pesos futuros: Fourier={weights['fourier']:.2f}, Bayes={weights['bayes']:.2f}, XGBoost={weights['xgboost']:.2f}. Luego entrenó el modelo final con todo el histórico disponible y evaluó {total:,} combinaciones por Monte Carlo multi-estrategia. El score operativo combina percentil, score crudo, consenso entre modelos y factor Walk-Forward={wf_factor}. Es un ranking informativo para ordenar combinaciones futuras; no es probabilidad real de ganar.", "max_confidence_found": round(float(ranked[0]["confidence"] if ranked else 0), 4), "max_raw_quality_found": round(float(ranked[0]["raw_quality"] if ranked else 0), 4), "total_mc_evaluated": int(total), "optimized_weights": weights, "number_scores": {str(n): round(float(st.ensemble[n] * 100), 4) for n in range(1, MAX_NUMBER + 1)}, "manual_suggestion_seed": manual_seed(st), "walk_forward": wf, "generator_pool": pool, "top_combinations": top_enriched, "capital_preservation": not bool(top_enriched)}
    if not top_enriched:
        result["stop_loss_reason"] = f"No hubo combinaciones con score operativo >= {CONFIDENCE_THRESHOLD:.0f} tras {total:,} evaluaciones."
    Path("resultados.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nresultados.json generado. Max score operativo={result['max_confidence_found']} raw={result['max_raw_quality_found']} total={total:,}")
    print(f"Tiempo total: {time.perf_counter() - started:.2f}s")
    return result


def find_git():
    g = shutil.which("git")
    if g:
        return g
    for p in [r"C:\Program Files\Git\cmd\git.exe", r"C:\Program Files\Git\bin\git.exe", str(Path.home() / r"AppData\Local\Programs\Git\cmd\git.exe")]:
        if Path(p).exists():
            return p
    return None


def git_sync():
    g = find_git()
    if not g:
        print("Git no encontrado. resultados.json ya fue generado.")
        return
    subprocess.run([g, "add", "resultados.json"], check=False)
    subprocess.run([g, "commit", "-m", "Update predictions"], check=False)
    subprocess.run([g, "push", "origin", "main"], check=False)


def main():
    while True:
        menu()
        op = input("\nSelecciona una opción: ").strip()
        try:
            if op == "1":
                run_pipeline()
                git_sync()
                pause()
            elif op == "2":
                if Path("resultados.json").exists():
                    git_sync()
                else:
                    print("No existe resultados.json")
                pause()
            elif op == "3":
                break
            else:
                print("Opción inválida")
                pause()
        except KeyboardInterrupt:
            print("Interrumpido")
            pause()
        except Exception as exc:
            print("ERROR:", exc)
            pause()


if __name__ == "__main__":
    ensure_deps()
    main()
