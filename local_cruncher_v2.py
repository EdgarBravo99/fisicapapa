#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
local_cruncher_v2.py

Versión experimental segura del cruncher local.
Mantiene el enfoque del local_cruncher.py actual, pero agrega:
- Walk-Forward con avg_hits_top10.
- Score operativo separado de raw_quality.
- Calibración por percentil de Monte Carlo + consenso de componentes + factor Walk-Forward.
- Objetivo de combinaciones >=70 y algunas >=80 como score operativo, sin presentarlo como probabilidad real.

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
WALK_FORWARD_STEPS = 24
CONFIDENCE_THRESHOLD = 70.0
TARGET_OPERATIONAL_CONFIDENCE = 80.0
TARGET_OPERATIONAL_COMBOS = 10
TARGET_HIGH_CONF_COMBOS = 3
INITIAL_MC_COMBINATIONS = 1_000_000
MAX_MC_COMBINATIONS = 10_000_000
MC_BATCH_SIZE = 100_000
RANDOM_SEED = 73073
EPS = 1e-12
DRIFT_KL_THRESHOLD = 0.18
SIGMOID = {"L": 0.0, "K": 1.0, "r": 0.09, "n0": 35.0}
ENSEMBLE_WEIGHTS = {"fourier": 0.28, "bayes": 0.32, "xgboost": 0.40}


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


def clear():
    os.system("cls" if os.name == "nt" else "clear")


def pause():
    input("\nENTER para continuar...")


def menu():
    clear()
    print("╔" + "═" * 78 + "╗")
    print("║  MELATE LOCAL CRUNCHER V2 · WALK-FORWARD + SCORE OPERATIVO 80              ║")
    print("╠" + "═" * 78 + "╣")
    print("║  [1] Ejecutar pipeline completo                                             ║")
    print("║  [2] Solo exportar último resultados.json si ya existe                      ║")
    print("║  [3] Salir                                                                  ║")
    print("╚" + "═" * 78 + "╝")


def parse_int(v):
    try:
        if pd.isna(v):
            return None
        return int(float(str(v).strip()))
    except Exception:
        return None


def detect_columns(df):
    lower = {str(c).lower().strip(): c for c in df.columns}
    groups = [["n1","n2","n3","n4","n5","n6"],["num1","num2","num3","num4","num5","num6"],["numero1","numero2","numero3","numero4","numero5","numero6"],["bola1","bola2","bola3","bola4","bola5","bola6"]]
    natural = []
    for g in groups:
        if all(x in lower for x in g):
            natural = [lower[x] for x in g]
            break
    if not natural:
        numeric = []
        for c in df.columns:
            s = pd.to_numeric(df[c], errors="coerce")
            if s.notna().mean() > .8 and s.between(1, MAX_NUMBER).mean() > .55:
                numeric.append(c)
        if len(numeric) < 6:
            raise ValueError("No pude detectar columnas. Usa n1,n2,n3,n4,n5,n6.")
        natural = numeric[:6]
    draw_col = next((lower[x] for x in ["sorteo","draw","draw_id","concurso","id"] if x in lower), None)
    date_col = next((lower[x] for x in ["fecha","date","draw_date"] if x in lower), None)
    add_col = next((lower[x] for x in ["adicional","additional","bonus","extra"] if x in lower), None)
    return natural, add_col, draw_col, date_col


def load_draws(path="historial.csv"):
    if not Path(path).exists():
        raise FileNotFoundError(f"No existe {Path(path).resolve()}")
    df = pd.read_csv(path)
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
    out[1:] = .5 if hi - lo <= EPS else (x - lo) / (hi - lo)
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
        scores[1:] = .5
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
    return np.column_stack([
        nums / MAX_NUMBER,
        p0[1:],
        rollfreq(m, 15)[1:],
        rollfreq(m, 30)[1:],
        rollfreq(m, 60)[1:],
        rollfreq(m, WINDOW_SIZE)[1:],
        np.minimum(gaps[1:], WINDOW_SIZE) / WINDOW_SIZE,
        1 / (1 + gaps[1:]),
        f[1:],
        b[1:],
        (nums % 2).astype(float),
        np.floor((nums - 1) / 10) / 5,
        (nums > 28).astype(float),
    ]).astype(np.float32)


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
    return XGBClassifier(
        n_estimators=220,
        max_depth=4,
        learning_rate=.035,
        subsample=1.0,
        colsample_bytree=1.0,
        min_child_weight=1.0,
        reg_lambda=.65,
        objective="binary:logistic",
        eval_metric="logloss",
        scale_pos_weight=(MAX_NUMBER - PICK_COUNT) / PICK_COUNT,
        tree_method="hist",
        device="cuda",
        random_state=RANDOM_SEED,
        n_jobs=0,
        verbosity=1,
    )


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


def state_from_context(ctx, p0, model):
    X = features(ctx.rows, p0, ctx.fourier, ctx.bayes)
    xraw = np.zeros(MAX_NUMBER + 1)
    xraw[1:] = model.predict_proba(X)[:, 1]
    xgb = minmax(xraw)
    ens = np.zeros(MAX_NUMBER + 1)
    ens[1:] = ENSEMBLE_WEIGHTS["fourier"] * ctx.fourier[1:] + ENSEMBLE_WEIGHTS["bayes"] * ctx.bayes[1:] + ENSEMBLE_WEIGHTS["xgboost"] * xgb[1:]
    ens = minmax(ens)
    d, k, hr, hw = drift(ctx.rows)
    return State(ctx.fourier, ctx.periods, ctx.bayes, xraw, xgb, ens, d, k, hr, hw)


def component_winner(st, n):
    comps = {"Fourier": float(st.fourier[n]), "Bayes": float(st.bayes[n]), "XGBoost": float(st.xgb[n])}
    return max(comps.items(), key=lambda kv: kv[1])


def walk_forward_factor(wf, drift_detected):
    if not wf:
        return 1.0
    avg_top10 = float(wf.get("avg_hits_top10", 0) or 0)
    avg_mse = float(wf.get("avg_mse", 0) or 0)
    hit_lift = avg_top10 / 1.07 if avg_top10 > 0 else .75
    mse_penalty = max(.84, min(1.06, 1 - max(0, avg_mse - .20) * .35))
    factor = max(.82, min(1.16, .88 + .18 * hit_lift)) * mse_penalty
    if drift_detected:
        factor *= .94
    return round(float(max(.78, min(1.18, factor))), 4)


def walk_forward(draws, p0):
    start = max(WINDOW_SIZE, len(draws) - WALK_FORWARD_STEPS)
    rows, hits6, hits10s, mses = [], [], [], []
    for idx in range(start, len(draws)):
        ctx = context(draws, p0, idx)
        try:
            model = train_model(draws, p0, idx)
            st = state_from_context(ctx, p0, model)
        except Exception as exc:
            rows.append({"draw_id": draws[idx].draw_id, "error": str(exc)})
            continue
        top6 = list(map(int, np.argsort(st.ensemble[1:])[::-1][:6] + 1))
        top10 = list(map(int, np.argsort(st.ensemble[1:])[::-1][:10] + 1))
        actual = set(draws[idx].numbers)
        h6 = len(actual.intersection(top6))
        h10 = len(actual.intersection(top10))
        y = np.zeros(MAX_NUMBER + 1)
        for n in actual:
            y[n] = 1
        mse = float(np.mean((y[1:] - st.ensemble[1:]) ** 2))
        hits6.append(h6); hits10s.append(h10); mses.append(mse)
        rows.append({"draw_id": draws[idx].draw_id, "date": draws[idx].date, "actual": list(draws[idx].numbers), "predicted_top6": top6, "predicted_top10": top10, "hits": h6, "hits_top10": h10, "mse": round(mse, 6), "kl": round(st.kl, 6), "drift_detected": bool(st.drift)})
        print(f"Walk-Forward {idx-start+1}/{len(draws)-start}: hits={h6}/6 top10={h10}/6 mse={mse:.5f}")
    wf = {"window_size": WINDOW_SIZE, "steps": len(rows), "avg_hits": round(float(np.mean(hits6)) if hits6 else 0, 4), "avg_hits_top10": round(float(np.mean(hits10s)) if hits10s else 0, 4), "avg_mse": round(float(np.mean(mses)) if mses else 0, 6), "rows": rows}
    wf["walk_forward_factor"] = walk_forward_factor(wf, any(r.get("drift_detected") for r in rows if isinstance(r, dict)))
    return wf


def structure_score(combos):
    combos = np.asarray(combos, dtype=np.float64)
    evens = np.sum((combos % 2) == 0, axis=1)
    lows = np.sum(combos <= 28, axis=1)
    sums = np.sum(combos, axis=1)
    span = (np.max(combos, axis=1) - np.min(combos, axis=1)) / 55
    consec = np.sum(np.diff(combos, axis=1) == 1, axis=1)
    decades = np.array([len(set(((r - 1) // 10).astype(int))) for r in combos], dtype=np.float64)
    return np.clip((1 - np.abs(evens - 3) / 3) * .22 + (1 - np.abs(lows - 3) / 3) * .20 + (decades / 6) * .20 + (1 - np.minimum(consec, 4) / 4) * .13 + np.where((sums >= 110) & (sums <= 240), 1, .55) * .15 + span * .10, 0, 1)


def score_batch(st, combos):
    e = np.mean(st.ensemble[combos], axis=1)
    f = np.mean(st.fourier[combos], axis=1)
    b = np.mean(st.bayes[combos], axis=1)
    xr = np.mean(st.xgb_raw[combos], axis=1)
    x = np.mean(st.xgb[combos], axis=1)
    s = structure_score(combos)
    raw = (0.34 * e + 0.28 * x + 0.17 * b + 0.12 * f + 0.09 * s) * 100
    consensus = np.clip(100 * (1 - np.std(np.vstack([x, b, f, s]), axis=0)), 0, 100)
    return raw, consensus, e, xr, x, b, f, s


def apply_operational_conf(records, wf_factor, drift_detected):
    raw = np.array([r["raw_quality"] for r in records], dtype=np.float64)
    order = np.argsort(raw)
    ranks = np.empty_like(order, dtype=np.float64)
    ranks[order] = np.arange(len(raw), dtype=np.float64)
    pct = 100 * ranks / max(1, len(raw) - 1)
    drift_penalty = 5 if drift_detected else 0
    for i, r in enumerate(records):
        conf = (0.46 * pct[i] + 0.34 * r["raw_quality"] + 0.20 * r["consensus_score"]) * wf_factor - drift_penalty
        conf = float(max(0, min(95, conf)))
        r["rank_percentile"] = round(float(pct[i]), 6)
        r["confidence"] = conf
        r["operational_confidence"] = conf
        r["confidence_kind"] = "operational_score_not_win_probability"
    return sorted(records, key=lambda x: x["confidence"], reverse=True)


def monte_carlo(st, wf):
    rng = np.random.default_rng(RANDOM_SEED)
    nums = np.arange(1, MAX_NUMBER + 1, dtype=np.int16)
    weights = np.maximum(st.ensemble[1:], EPS)
    weights /= np.sum(weights)
    logw = np.log(weights).reshape(1, -1).astype(np.float32)
    records = {}
    generated = 0
    wf_factor = walk_forward_factor(wf, st.drift)
    while generated < MAX_MC_COMBINATIONS:
        cur = min(MC_BATCH_SIZE, MAX_MC_COMBINATIONS - generated)
        g = rng.gumbel(0, 1, size=(cur, MAX_NUMBER)).astype(np.float32)
        idx = np.argpartition(g + logw, -PICK_COUNT, axis=1)[:, -PICK_COUNT:]
        combos = np.sort(nums[idx], axis=1).astype(np.int16)
        raw, cons, e, xr, x, b, f, s = score_batch(st, combos)
        keep = np.argpartition(raw, -min(900, cur))[-min(900, cur):]
        for i in keep:
            key = tuple(int(v) for v in combos[i])
            item = {"numbers": list(key), "raw_quality": float(raw[i]), "consensus_score": float(cons[i]), "ensemble": float(e[i]), "xgboost_raw_mean": float(xr[i]), "xgboost_contrast_mean": float(x[i]), "bayes_mean": float(b[i]), "fourier_mean": float(f[i]), "structure_mean": float(s[i]), "source": "python_gpu_montecarlo"}
            if key not in records or item["raw_quality"] > records[key]["raw_quality"]:
                records[key] = item
        if len(records) > 15000:
            tmp = apply_operational_conf(list(records.values()), wf_factor, st.drift)
            records = {tuple(x["numbers"]): x for x in tmp[:6000]}
        generated += cur
        ranked = apply_operational_conf(list(records.values()), wf_factor, st.drift)
        op70 = sum(1 for r in ranked if r["confidence"] >= CONFIDENCE_THRESHOLD)
        op80 = sum(1 for r in ranked if r["confidence"] >= TARGET_OPERATIONAL_CONFIDENCE)
        print(f"MC: {generated:,}/{MAX_MC_COMBINATIONS:,} | >=70 {op70}/{TARGET_OPERATIONAL_COMBOS} | >=80 {op80}/{TARGET_HIGH_CONF_COMBOS} | WF={wf_factor}", end="\r")
        if generated >= INITIAL_MC_COMBINATIONS and op70 >= TARGET_OPERATIONAL_COMBOS and op80 >= TARGET_HIGH_CONF_COMBOS:
            break
    print()
    return apply_operational_conf(list(records.values()), wf_factor, st.drift), generated, wf_factor


def explain_combo(item, st):
    route = []
    for n in item["numbers"]:
        w, sc = component_winner(st, int(n))
        route.append(f"{n}:{w}({sc:.2f})")
    return f"Combo {item['numbers']} priorizado por score operativo. Confianza operativa={item['confidence']:.2f}%, raw_quality={item['raw_quality']:.2f}, percentil={item['rank_percentile']:.2f}, consenso={item['consensus_score']:.2f}. Ruta: {' | '.join(route)}."


def hindsight(draws, p0):
    target = draws[-1]
    ctx = context(draws, p0, len(draws) - 1)
    model = train_model(draws, p0, len(draws) - 1)
    st = state_from_context(ctx, p0, model)
    lines = [f"Auditoría inversa del sorteo {target.draw_id} ({target.date or 'sin fecha'})", f"Combinación real: {' '.join(map(str, target.numbers))}", f"Ventana usada antes del sorteo: {len(ctx.rows)}", f"Drift={st.drift} KL={st.kl:.6f} H15={st.h_recent:.4f} H120={st.h_window:.4f}"]
    for n in target.numbers:
        w, sc = component_winner(st, n)
        rank = int(np.where((np.argsort(st.ensemble[1:])[::-1] + 1) == n)[0][0] + 1)
        lines.append(f"Número {n}: componente={w}({sc:.4f}); Fourier={st.fourier[n]:.4f}; Bayes={st.bayes[n]:.4f}; XGB={st.xgb[n]:.4f}; Ensemble={st.ensemble[n]:.4f}; Rank={rank}/56")
    return "\n".join(lines)


def manual_seed(st):
    out = []
    for n in range(1, MAX_NUMBER + 1):
        w, sc = component_winner(st, n)
        out.append({"number": n, "score": round(float(st.ensemble[n] * 100), 4), "winner_component": w, "winner_component_score": round(float(sc), 6), "fourier": round(float(st.fourier[n]), 6), "bayes": round(float(st.bayes[n]), 6), "xgboost": round(float(st.xgb[n]), 6), "xgboost_raw": round(float(st.xgb_raw[n]), 8), "period_fft": round(float(st.periods[n]), 4)})
    return sorted(out, key=lambda x: x["score"], reverse=True)


def run_pipeline():
    started = time.perf_counter()
    draws = load_draws("historial.csv")
    p0 = prior(draws)
    print("\n[1/5] Walk-Forward...")
    wf = walk_forward(draws, p0)
    print("\n[2/5] Hindsight...")
    hlog = hindsight(draws, p0)
    print(hlog)
    print("\n[3/5] Modelo final CUDA...")
    ctx = context(draws, p0, len(draws))
    model = train_model(draws, p0, len(draws))
    st = state_from_context(ctx, p0, model)
    print("\n[4/5] Monte Carlo extendido...")
    ranked, total, wf_factor = monte_carlo(st, wf)
    top = [r for r in ranked if r["confidence"] >= CONFIDENCE_THRESHOLD][:TARGET_OPERATIONAL_COMBOS]
    pool = []
    for i, r in enumerate(ranked[:120], start=1):
        x = dict(r)
        x["rank"] = i
        x["procedure"] = explain_combo(x, st)
        pool.append(x)
    result = {
        "last_update": datetime.now(timezone.utc).isoformat(),
        "source": "local_cruncher_v2_python_gpu",
        "confidence_kind": "operational_score_not_win_probability",
        "target_operational_confidence": TARGET_OPERATIONAL_CONFIDENCE,
        "drift_detected": bool(st.drift),
        "hindsight_log": hlog,
        "procedure_log": f"Walk-Forward {wf['steps']} pasos, avg_hits={wf['avg_hits']}, avg_hits_top10={wf['avg_hits_top10']}, avg_mse={wf['avg_mse']}. Monte Carlo evaluó {total:,}. Score operativo = percentil + raw_quality + consenso + factor Walk-Forward={wf_factor}. No es probabilidad real de ganar.",
        "max_confidence_found": round(float(ranked[0]["confidence"] if ranked else 0), 4),
        "max_raw_quality_found": round(float(ranked[0]["raw_quality"] if ranked else 0), 4),
        "total_mc_evaluated": int(total),
        "number_scores": {str(n): round(float(st.ensemble[n] * 100), 4) for n in range(1, MAX_NUMBER + 1)},
        "manual_suggestion_seed": manual_seed(st),
        "walk_forward": wf,
        "generator_pool": pool,
        "top_combinations": [{**r, "procedure": explain_combo(r, st)} for r in top],
        "capital_preservation": not bool(top),
    }
    Path("resultados.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nresultados.json generado. Max conf_op={result['max_confidence_found']} raw={result['max_raw_quality_found']} total={total:,}")
    print(f"Tiempo total: {time.perf_counter() - started:.2f}s")
    return result


def find_git():
    g = shutil.which("git")
    if g: return g
    for p in [r"C:\Program Files\Git\cmd\git.exe", r"C:\Program Files\Git\bin\git.exe", str(Path.home() / r"AppData\Local\Programs\Git\cmd\git.exe")]:
        if Path(p).exists(): return p
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
                run_pipeline(); git_sync(); pause()
            elif op == "2":
                if Path("resultados.json").exists(): git_sync()
                else: print("No existe resultados.json")
                pause()
            elif op == "3":
                break
            else:
                print("Opción inválida"); pause()
        except KeyboardInterrupt:
            print("Interrumpido"); pause()
        except Exception as exc:
            print("ERROR:", exc); pause()


if __name__ == "__main__":
    ensure_deps()
    main()
