#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
local_cruncher_v2.py

Motor local experimental para Melate Pro.

V2.2 integra las reglas que ya existen en la web:
- Selector de juego: Melate o Revancha.
- Pesos físicos separados por juego, portados desde engine.js.
- Bonus físico por peso medido, desgaste sigmoide y uso reciente.
- Expertos equivalentes al motor web: physical, structural, temporal, entropy.
- Expertos cuantitativos: Fourier, Bayes y XGBoost CUDA calibrado.
- Walk-Forward retroalimenta pesos del ensemble antes de generar futuro.
- Monte Carlo multi-estrategia con mínimo 5M y máximo 25M combinaciones.
- Exporta resultados.json para que la web asimile, explique y sugiera.

Nota: confidence / operational_confidence es un score operativo para ordenar combinaciones,
no una probabilidad real de ganar.
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

REQUIRED_LIBS = [
    ("pandas", "pandas"),
    ("numpy", "numpy"),
    ("xgboost", "xgboost"),
    ("sklearn", "scikit-learn"),
    ("scipy", "scipy"),
]

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

WEIGHT_MIN = 4.25
WEIGHT_MAX = 5.25
WEIGHT_DIFF_MAX = 0.30
BASE_WEIGHT = 4.75
WEB_WEAR = {"L": 0.0, "K": 0.085, "r": 0.055, "n0": 60.0}
BAYES_WEAR = {"L": 0.0, "K": 1.0, "r": 0.09, "n0": 35.0}

DEFAULT_BALL_WEIGHTS_REVANCHA = [
    0,
    4.35, 4.33, 4.36, 4.31, 4.35, 4.39, 4.33, 4.37, 4.34, 4.37,
    4.36, 4.32, 4.35, 4.32, 4.35, 4.33, 4.31, 4.33, 4.31, 4.39,
    4.37, 4.33, 4.34, 4.31, 4.31, 4.38, 4.31, 4.34, 4.36, 4.34,
    4.35, 4.35, 4.36, 4.34, 4.37, 4.34, 4.39, 4.32, 4.32, 4.33,
    4.37, 4.39, 4.34, 4.35, 4.32, 4.36, 4.40, 4.30, 4.31, 4.32,
    4.30, 4.29, 4.29, 4.43, 4.42, 4.44,
]

DEFAULT_BALL_WEIGHTS_MELATE = [
    0,
    4.53, 4.56, 4.53, 4.54, 4.53, 4.52, 4.52, 4.55, 4.54, 4.59,
    4.51, 4.60, 4.54, 4.58, 4.60, 4.53, 4.55, 4.55, 4.51, 4.58,
    4.57, 4.51, 4.58, 4.50, 4.53, 4.51, 4.50, 4.55, 4.51, 4.54,
    4.51, 4.54, 4.52, 4.53, 4.52, 4.59, 4.59, 4.58, 4.52, 4.59,
    4.53, 4.53, 4.58, 4.59, 4.51, 4.58, 4.58, 4.58, 4.55, 4.58,
    4.59, 4.56, 4.61, 4.58, 4.59, 4.54,
]

DEFAULT_WEIGHTS = {
    "physical": 0.18,
    "temporal": 0.18,
    "entropy": 0.08,
    "fourier": 0.18,
    "bayes": 0.16,
    "xgboost": 0.22,
}

WEIGHT_CANDIDATES = [
    DEFAULT_WEIGHTS,
    {"physical": 0.22, "temporal": 0.18, "entropy": 0.08, "fourier": 0.16, "bayes": 0.16, "xgboost": 0.20},
    {"physical": 0.14, "temporal": 0.16, "entropy": 0.08, "fourier": 0.20, "bayes": 0.16, "xgboost": 0.26},
    {"physical": 0.16, "temporal": 0.22, "entropy": 0.08, "fourier": 0.16, "bayes": 0.18, "xgboost": 0.20},
    {"physical": 0.12, "temporal": 0.14, "entropy": 0.08, "fourier": 0.24, "bayes": 0.16, "xgboost": 0.26},
    {"physical": 0.20, "temporal": 0.16, "entropy": 0.08, "fourier": 0.14, "bayes": 0.22, "xgboost": 0.20},
    {"physical": 0.13, "temporal": 0.15, "entropy": 0.07, "fourier": 0.18, "bayes": 0.17, "xgboost": 0.30},
]

SAMPLING_STRATEGIES = ["ensemble", "physical", "temporal", "xgboost", "bayes", "fourier", "balanced"]
SAMPLING_TEMPERATURES = [0.70, 0.88, 1.00, 1.22, 1.55]


@dataclass(frozen=True)
class Draw:
    index: int
    draw_id: str
    date: Optional[str]
    numbers: Tuple[int, int, int, int, int, int]
    additional: Optional[int] = None


@dataclass
class GameConfig:
    mode: str
    label: str
    csv_candidates: List[str]
    ball_weights: List[float]


@dataclass
class Context:
    rows: Sequence[Draw]
    fourier: object
    periods: object
    bayes: object
    physics: Dict
    temporal: object
    entropy_score: object


@dataclass
class State:
    fourier: object
    periods: object
    bayes: object
    physical: object
    temporal: object
    entropy_score: object
    xgb_raw: object
    xgb: object
    ensemble: object
    weights: Dict[str, float]
    physics: Dict
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
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", pkg, "--quiet", "--disable-pip-version-check"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
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


def print_header() -> None:
    clear()
    print("╔" + "═" * 92 + "╗")
    print("║  MELATE LOCAL CRUNCHER V2.2 · MODOS MELATE/REVANCHA + FÍSICA WEB                 ║")
    print("╠" + "═" * 92 + "╣")
    print("║  [1] Ejecutar pipeline completo                                                   ║")
    print("║  [2] Solo sincronizar resultados.json existente                                   ║")
    print("║  [3] Salir                                                                        ║")
    print("╚" + "═" * 92 + "╝")


def choose_game_config() -> GameConfig:
    print("\nSelecciona juego a simular:")
    print("  [1] Revancha  · pesos ligeros de Revancha")
    print("  [2] Melate    · pesos físicos de Melate")
    choice = input("Opción [1]: ").strip() or "1"
    if choice == "2":
        return GameConfig("melate", "Melate", ["historial_melate.csv", "melate.csv", "historial.csv"], DEFAULT_BALL_WEIGHTS_MELATE)
    return GameConfig("revancha", "Revancha", ["historial_revancha.csv", "revancha.csv", "historial.csv"], DEFAULT_BALL_WEIGHTS_REVANCHA)


def resolve_csv_path(config: GameConfig) -> str:
    for candidate in config.csv_candidates:
        if Path(candidate).exists():
            return candidate
    return config.csv_candidates[-1]


def parse_int(v):
    try:
        if pd.isna(v):
            return None
        return int(float(str(v).strip()))
    except Exception:
        return None


def detect_columns(df):
    lower = {str(c).lower().strip(): c for c in df.columns}
    groups = [
        ["n1", "n2", "n3", "n4", "n5", "n6"],
        ["num1", "num2", "num3", "num4", "num5", "num6"],
        ["numero1", "numero2", "numero3", "numero4", "numero5", "numero6"],
        ["bola1", "bola2", "bola3", "bola4", "bola5", "bola6"],
    ]
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


def load_draws(path: str):
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
    print(f"Historial cargado: {len(draws)} sorteos desde {path}")
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
    out[1:] = 0.5 if hi - lo <= EPS else (x - lo) / (hi - lo)
    return out


def prior(draws):
    return probs_from_counts(counts(draws))


def sigmoid_loss(n, params):
    return params["L"] + (params["K"] - params["L"]) / (1 + math.exp(-params["r"] * (n - params["n0"])))


def build_physics(draws, config: GameConfig):
    uses = counts(draws)
    effective = np.zeros(MAX_NUMBER + 1)
    for n in range(1, MAX_NUMBER + 1):
        measured = config.ball_weights[n] if n < len(config.ball_weights) else BASE_WEIGHT
        effective[n] = measured - sigmoid_loss(float(uses[n]), WEB_WEAR)
    avg_effective = float(np.mean(effective[1:]))
    bonus = np.zeros(MAX_NUMBER + 1)
    for n in range(1, MAX_NUMBER + 1):
        measured = config.ball_weights[n] if n < len(config.ball_weights) else BASE_WEIGHT
        delta = effective[n] - avg_effective
        b = -(delta / 0.05) * 6
        use_rate = uses[n] / max(1, len(draws))
        if use_rate > 0.40:
            b += 10
        elif use_rate > 0.30:
            b += 5
        if measured > BASE_WEIGHT + 0.15:
            b -= 5
        bonus[n] = max(-15, min(20, b))
    score = np.zeros(MAX_NUMBER + 1)
    score[1:] = np.clip(50 + bonus[1:] * 1.5, 0, 100)
    weights = np.array(config.ball_weights, dtype=np.float64)
    valid = weights[1:]
    return {
        "uses": uses,
        "effective": effective,
        "avg_effective": avg_effective,
        "bonus": bonus,
        "score": score,
        "min_weight": float(np.min(valid)),
        "max_weight": float(np.max(valid)),
        "diff_weight": float(np.max(valid) - np.min(valid)),
        "regulatory_ok": bool(np.min(valid) >= WEIGHT_MIN and np.max(valid) <= WEIGHT_MAX and (np.max(valid) - np.min(valid)) <= WEIGHT_DIFF_MAX),
    }


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
        wear[n] = sigmoid_loss(float(c[n]), BAYES_WEAR)
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


def temporal_scores(window):
    m = mat(window)
    total = len(window)
    freq = np.sum(m, axis=0)
    freq30 = np.sum(m[-min(30, total):], axis=0)
    last_seen = np.full(MAX_NUMBER + 1, total, dtype=np.float64)
    for gap, draw in enumerate(reversed(window)):
        for n in draw.numbers:
            if last_seen[n] == total:
                last_seen[n] = gap
    expected = 6 / 56
    score = np.zeros(MAX_NUMBER + 1)
    for n in range(1, MAX_NUMBER + 1):
        f = freq[n] / max(1, total)
        ret = last_seen[n]
        f30 = freq30[n]
        s = 50
        if f30 >= 3:
            s += 20
        if ret <= 3:
            s += 15
        if f > expected:
            s += 10
        if ret > 15:
            s += 15
        if ret > 25:
            s += 10
        if ret == 0 and f30 < 2:
            s -= 10
        score[n] = max(0, min(100, s))
    return minmax(score)


def entropy_number_scores(window):
    hist = probs_from_counts(counts(window))
    recent = probs_from_counts(counts(window[-DRIFT_WINDOW:]))
    score = np.zeros(MAX_NUMBER + 1)
    for n in range(1, MAX_NUMBER + 1):
        ratio = recent[n] / max(hist[n], EPS)
        score[n] = max(0, min(100, 70 - abs(math.log(ratio or 1)) * 18))
    return minmax(score)


def context(draws, p0, end_idx, config: GameConfig):
    rows = draws[max(0, end_idx - WINDOW_SIZE):end_idx]
    f, per = fourier_scores(rows)
    b = bayes_posterior(rows, p0)
    phys = build_physics(rows, config)
    temp = temporal_scores(rows)
    ent = entropy_number_scores(rows)
    return Context(rows, f, per, b, phys, temp, ent)


def last_gaps(window):
    g = np.full(MAX_NUMBER + 1, len(window) + 1, dtype=np.float64)
    for gap, d in enumerate(reversed(window)):
        for n in d.numbers:
            if g[n] == len(window) + 1:
                g[n] = gap
    return g


def rollfreq(m, k):
    return np.mean(m[-min(k, len(m)):], axis=0) if len(m) else np.zeros(MAX_NUMBER + 1)


def features(window, p0, ctx: Context, config: GameConfig):
    m = mat(window)
    gaps = last_gaps(window)
    nums = np.arange(1, MAX_NUMBER + 1, dtype=np.float64)
    weights = np.array(config.ball_weights, dtype=np.float64)
    return np.column_stack([
        nums / MAX_NUMBER,
        p0[1:],
        rollfreq(m, 15)[1:],
        rollfreq(m, 30)[1:],
        rollfreq(m, 60)[1:],
        rollfreq(m, WINDOW_SIZE)[1:],
        np.minimum(gaps[1:], WINDOW_SIZE) / WINDOW_SIZE,
        1 / (1 + gaps[1:]),
        ctx.fourier[1:],
        ctx.bayes[1:],
        ctx.physics["score"][1:] / 100,
        ctx.physics["bonus"][1:] / 20,
        ctx.physics["effective"][1:] / BASE_WEIGHT,
        weights[1:] / BASE_WEIGHT,
        ctx.temporal[1:],
        ctx.entropy_score[1:],
        (nums % 2).astype(float),
        np.floor((nums - 1) / 10) / 5,
        (nums > 28).astype(float),
    ]).astype(np.float32)


def training_data(draws, p0, end_idx, config: GameConfig):
    X, Y = [], []
    for i in range(max(1, end_idx - WINDOW_SIZE), end_idx):
        w = draws[max(0, i - WINDOW_SIZE):i]
        if len(w) < 40:
            continue
        ctx = context(draws, p0, i, config)
        X.append(features(w, p0, ctx, config))
        y = np.zeros(MAX_NUMBER, dtype=np.int32)
        for n in draws[i].numbers:
            y[n - 1] = 1
        Y.append(y)
    if not X:
        raise ValueError("Dataset insuficiente para entrenar")
    return np.vstack(X), np.concatenate(Y)


def gpu_model():
    return XGBClassifier(
        n_estimators=260,
        max_depth=4,
        learning_rate=0.032,
        subsample=1.0,
        colsample_bytree=1.0,
        min_child_weight=1.0,
        reg_lambda=0.70,
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


def train_model(draws, p0, end_idx, config: GameConfig):
    X, y = training_data(draws, p0, end_idx, config)
    print(f"Entrenando XGBoost CUDA calibrado | X={X.shape} | positivos={int(np.sum(y))}")
    model = calibrator(gpu_model())
    model.fit(X, y)
    return model


def normalize_weights(w):
    clean = {k: max(0.01, float(v)) for k, v in w.items()}
    total = sum(clean.values()) or 1
    return {k: v / total for k, v in clean.items()}


def combine_experts(ctx: Context, xgb, weights):
    weights = normalize_weights(weights)
    ens = np.zeros(MAX_NUMBER + 1)
    ens[1:] = (
        weights["physical"] * minmax(ctx.physics["score"])[1:]
        + weights["temporal"] * ctx.temporal[1:]
        + weights["entropy"] * ctx.entropy_score[1:]
        + weights["fourier"] * ctx.fourier[1:]
        + weights["bayes"] * ctx.bayes[1:]
        + weights["xgboost"] * xgb[1:]
    )
    return minmax(ens)


def state_from_context(ctx: Context, p0, model, config: GameConfig, weights=None):
    weights = normalize_weights(weights or DEFAULT_WEIGHTS)
    X = features(ctx.rows, p0, ctx, config)
    xraw = np.zeros(MAX_NUMBER + 1)
    xraw[1:] = model.predict_proba(X)[:, 1]
    xgb = minmax(xraw)
    ens = combine_experts(ctx, xgb, weights)
    d, k, hr, hw = drift(ctx.rows)
    return State(ctx.fourier, ctx.periods, ctx.bayes, minmax(ctx.physics["score"]), ctx.temporal, ctx.entropy_score, xraw, xgb, ens, weights, ctx.physics, d, k, hr, hw)


def expert_values(st: State, n: int):
    return {
        "physical": float(st.physical[n]),
        "temporal": float(st.temporal[n]),
        "entropy": float(st.entropy_score[n]),
        "fourier": float(st.fourier[n]),
        "bayes": float(st.bayes[n]),
        "xgboost": float(st.xgb[n]),
    }


def component_winner(st: State, n: int):
    comps = expert_values(st, n)
    return max(comps.items(), key=lambda kv: kv[1])


def eval_weight_candidate(ctx: Context, xgb, actual, weights):
    ens = combine_experts(ctx, xgb, weights)
    top6 = set(map(int, np.argsort(ens[1:])[::-1][:6] + 1))
    top10 = set(map(int, np.argsort(ens[1:])[::-1][:10] + 1))
    top12 = set(map(int, np.argsort(ens[1:])[::-1][:12] + 1))
    actual_set = set(actual)
    y = np.zeros(MAX_NUMBER + 1)
    for n in actual_set:
        y[n] = 1.0
    mse = float(np.mean((y[1:] - ens[1:]) ** 2))
    return {
        "hits6": len(actual_set.intersection(top6)),
        "hits10": len(actual_set.intersection(top10)),
        "hits12": len(actual_set.intersection(top12)),
        "mse": mse,
        "top6": list(sorted(top6)),
        "top10": list(sorted(top10)),
    }


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


def walk_forward(draws, p0, config: GameConfig):
    start = max(WINDOW_SIZE, len(draws) - WALK_FORWARD_STEPS)
    rows, cache = [], []
    candidate_stats = {i: {"utility": 0.0, "hits6": [], "hits10": [], "hits12": [], "mse": []} for i in range(len(WEIGHT_CANDIDATES))}
    for idx in range(start, len(draws)):
        ctx = context(draws, p0, idx, config)
        try:
            model = train_model(draws, p0, idx, config)
            base_state = state_from_context(ctx, p0, model, config, DEFAULT_WEIGHTS)
        except Exception as exc:
            rows.append({"draw_id": draws[idx].draw_id, "error": str(exc)})
            continue
        cache.append((idx, ctx, base_state.xgb, draws[idx].numbers, base_state.kl, base_state.drift))
        for cand_idx, weights in enumerate(WEIGHT_CANDIDATES):
            ev = eval_weight_candidate(ctx, base_state.xgb, draws[idx].numbers, weights)
            candidate_stats[cand_idx]["hits6"].append(ev["hits6"])
            candidate_stats[cand_idx]["hits10"].append(ev["hits10"])
            candidate_stats[cand_idx]["hits12"].append(ev["hits12"])
            candidate_stats[cand_idx]["mse"].append(ev["mse"])
            candidate_stats[cand_idx]["utility"] += ev["hits6"] * 2.4 + ev["hits10"] * 1.0 + ev["hits12"] * 0.45 - ev["mse"] * 1.8
        print(f"Walk-Forward {idx-start+1}/{len(draws)-start}: {config.label} | KL={base_state.kl:.5f}")
    if not cache:
        return {"window_size": WINDOW_SIZE, "steps": 0, "avg_hits": 0, "avg_hits_top10": 0, "avg_hits_top12": 0, "avg_mse": 0, "optimized_weights": DEFAULT_WEIGHTS, "rows": rows}
    best_idx = max(candidate_stats, key=lambda i: candidate_stats[i]["utility"])
    best_weights = normalize_weights(WEIGHT_CANDIDATES[best_idx])
    hits6, hits10, hits12, mses, rows = [], [], [], [], []
    for idx, ctx, xgb, actual, kld, dflag in cache:
        ev = eval_weight_candidate(ctx, xgb, actual, best_weights)
        hits6.append(ev["hits6"])
        hits10.append(ev["hits10"])
        hits12.append(ev["hits12"])
        mses.append(ev["mse"])
        rows.append({
            "draw_id": draws[idx].draw_id,
            "date": draws[idx].date,
            "actual": list(draws[idx].numbers),
            "predicted_top6": ev["top6"],
            "predicted_top10": ev["top10"],
            "hits": ev["hits6"],
            "hits_top10": ev["hits10"],
            "hits_top12": ev["hits12"],
            "mse": round(ev["mse"], 6),
            "kl": round(float(kld), 6),
            "drift_detected": bool(dflag),
        })
    scorecards = []
    for idx, weights in enumerate(WEIGHT_CANDIDATES):
        st = candidate_stats[idx]
        scorecards.append({
            "weights": normalize_weights(weights),
            "utility": round(float(st["utility"]), 6),
            "avg_hits": round(float(np.mean(st["hits6"])) if st["hits6"] else 0, 4),
            "avg_hits_top10": round(float(np.mean(st["hits10"])) if st["hits10"] else 0, 4),
            "avg_hits_top12": round(float(np.mean(st["hits12"])) if st["hits12"] else 0, 4),
            "avg_mse": round(float(np.mean(st["mse"])) if st["mse"] else 0, 6),
        })
    scorecards = sorted(scorecards, key=lambda x: x["utility"], reverse=True)
    wf = {
        "window_size": WINDOW_SIZE,
        "steps": len(rows),
        "game_mode": config.mode,
        "avg_hits": round(float(np.mean(hits6)) if hits6 else 0, 4),
        "avg_hits_top10": round(float(np.mean(hits10)) if hits10 else 0, 4),
        "avg_hits_top12": round(float(np.mean(hits12)) if hits12 else 0, 4),
        "avg_mse": round(float(np.mean(mses)) if mses else 0, 6),
        "optimized_weights": best_weights,
        "weight_scorecards": scorecards,
        "rows": rows,
    }
    wf["walk_forward_factor"] = walk_forward_factor(wf, any(r.get("drift_detected") for r in rows))
    print(f"Pesos optimizados {config.label}: {best_weights}")
    return wf


def pair_score(draws, nums):
    pairs = {}
    for draw in draws:
        row = list(draw.numbers)
        for i in range(len(row)):
            for j in range(i + 1, len(row)):
                key = tuple(sorted((row[i], row[j])))
                pairs[key] = pairs.get(key, 0) + 1
    count = 0
    for i in range(len(nums)):
        for j in range(i + 1, len(nums)):
            if pairs.get(tuple(sorted((int(nums[i]), int(nums[j])))), 0) >= 2:
                count += 1
    return min(100, 30 + count * 15)


def structure_score(combos, draws=None):
    combos = np.asarray(combos, dtype=np.float64)
    evens = np.sum((combos % 2) == 0, axis=1)
    lows = np.sum(combos <= 28, axis=1)
    sums = np.sum(combos, axis=1)
    span = (np.max(combos, axis=1) - np.min(combos, axis=1)) / 55
    consec = np.sum(np.diff(combos, axis=1) == 1, axis=1)
    decades = np.array([len(set(((r - 1) // 10).astype(int))) for r in combos], dtype=np.float64)
    if draws:
        all_sums = np.array([sum(d.numbers) for d in draws], dtype=np.float64)
        mean = float(np.mean(all_sums))
        std = float(np.std(all_sums)) or 1.0
        sum_score = 1 - np.minimum(0.50, np.abs((sums - mean) / std) * 0.15)
    else:
        sum_score = np.where((sums >= 110) & (sums <= 240), 1.0, 0.55)
    return np.clip(
        (1 - np.abs(evens - 3) / 3) * 0.22
        + (1 - np.abs(lows - 3) / 3) * 0.20
        + (decades / 6) * 0.20
        + (1 - np.minimum(consec, 4) / 4) * 0.13
        + sum_score * 0.15
        + span * 0.10,
        0,
        1,
    )


def score_batch(st: State, combos, draws):
    e = np.mean(st.ensemble[combos], axis=1)
    physical = np.mean(st.physical[combos], axis=1)
    temporal = np.mean(st.temporal[combos], axis=1)
    entropy_s = np.mean(st.entropy_score[combos], axis=1)
    f = np.mean(st.fourier[combos], axis=1)
    b = np.mean(st.bayes[combos], axis=1)
    xr = np.mean(st.xgb_raw[combos], axis=1)
    x = np.mean(st.xgb[combos], axis=1)
    s = structure_score(combos, draws)
    raw = (0.26 * e + 0.14 * physical + 0.10 * temporal + 0.08 * entropy_s + 0.16 * x + 0.10 * b + 0.08 * f + 0.08 * s) * 100
    consensus = np.clip(100 * (1 - np.std(np.vstack([physical, temporal, entropy_s, x, b, f, s]), axis=0)), 0, 100)
    return raw, consensus, e, physical, temporal, entropy_s, xr, x, b, f, s


def sampling_weights(st: State, strategy, temperature):
    if strategy == "physical":
        base = st.physical[1:]
    elif strategy == "temporal":
        base = st.temporal[1:]
    elif strategy == "xgboost":
        base = st.xgb[1:]
    elif strategy == "bayes":
        base = st.bayes[1:]
    elif strategy == "fourier":
        base = st.fourier[1:]
    elif strategy == "balanced":
        base = 0.24 * st.ensemble[1:] + 0.18 * st.physical[1:] + 0.15 * st.temporal[1:] + 0.14 * st.xgb[1:] + 0.12 * st.bayes[1:] + 0.12 * st.fourier[1:] + 0.05 * st.entropy_score[1:]
    else:
        base = st.ensemble[1:]
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


def monte_carlo(st: State, wf, draws, config: GameConfig):
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
        raw, cons, e, physical, temporal, entropy_s, xr, x, b, f, s = score_batch(st, combos, draws)
        keep = np.argpartition(raw, -min(1400, cur))[-min(1400, cur):]
        for i in keep:
            key = tuple(int(v) for v in combos[i])
            item = {
                "numbers": list(key),
                "game_mode": config.mode,
                "game_label": config.label,
                "raw_quality": float(raw[i]),
                "consensus_score": float(cons[i]),
                "ensemble": float(e[i]),
                "physical_mean": float(physical[i]),
                "temporal_mean": float(temporal[i]),
                "entropy_mean": float(entropy_s[i]),
                "xgboost_raw_mean": float(xr[i]),
                "xgboost_contrast_mean": float(x[i]),
                "bayes_mean": float(b[i]),
                "fourier_mean": float(f[i]),
                "structure_mean": float(s[i]),
                "sampling_strategy": strategy,
                "sampling_temperature": float(temperature),
                "source": "python_gpu_montecarlo_with_web_rules",
            }
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
        print(f"MC {config.label}: {generated:,}/{MAX_MC_COMBINATIONS:,} | >=70 {op70}/{TARGET_OPERATIONAL_COMBOS} | >=80 {op80}/{TARGET_HIGH_CONF_COMBOS} | {strategy}@{temperature} | WF={wf_factor}", end="\r")
        if generated >= MIN_MC_COMBINATIONS and op70 >= TARGET_OPERATIONAL_COMBOS and op80 >= TARGET_HIGH_CONF_COMBOS:
            break
    print()
    return apply_operational_conf(list(records.values()), wf_factor, st.drift), generated, wf_factor


def expert_human_name(component):
    return {
        "physical": "ventaja física de esfera",
        "temporal": "racha/retraso temporal",
        "entropy": "estabilidad de patrón",
        "fourier": "ciclo reciente",
        "bayes": "frecuencia y desgaste reciente",
        "xgboost": "patrón aprendido por IA",
    }.get(component, component)


def explain_number(st: State, n: int):
    winner, score = component_winner(st, int(n))
    if winner == "physical":
        measured_bonus = st.physics["bonus"][int(n)]
        effective = st.physics["effective"][int(n)]
        reason = f"su peso efectivo ({effective:.4f}g) le da bonus físico {measured_bonus:.1f}"
    elif winner == "temporal":
        reason = "su comportamiento reciente combina racha, retraso o rebote temporal"
    elif winner == "entropy":
        reason = "se mantiene estable contra la distribución reciente/histórica"
    elif winner == "fourier":
        reason = f"tiene ciclo reciente visible; periodo estimado {st.periods[int(n)]:.1f} sorteos"
    elif winner == "bayes":
        reason = "sale favorecido por frecuencia reciente y desgaste acumulado"
    else:
        reason = "XGBoost lo considera compatible con patrones recientes del histórico"
    return {
        "number": int(n),
        "driver": winner,
        "driver_human": expert_human_name(winner),
        "driver_score": round(float(score), 6),
        "reason": reason,
        "effective_weight": round(float(st.physics["effective"][int(n)]), 4),
        "physics_bonus": round(float(st.physics["bonus"][int(n)]), 4),
        "uses_in_window": int(st.physics["uses"][int(n)]),
    }


def human_combo_summary(item, st: State):
    explanations = [explain_number(st, n) for n in item["numbers"]]
    counts_by_driver = {}
    for exp in explanations:
        counts_by_driver[exp["driver_human"]] = counts_by_driver.get(exp["driver_human"], 0) + 1
    dominant = sorted(counts_by_driver.items(), key=lambda kv: kv[1], reverse=True)
    dominant_txt = ", ".join(f"{count} por {name}" for name, count in dominant)
    return (
        f"Esta combinación de {item.get('game_label', 'juego')} fue elegida porque mezcla reglas de la web y modelo local: {dominant_txt}. "
        f"Score crudo {item.get('raw_quality', 0):.1f}/100, consenso entre expertos {item.get('consensus_score', 0):.1f}/100 y score operativo {item.get('confidence', 0):.1f}/100. "
        "El score operativo ordena combinaciones informativas; no es probabilidad real de ganar."
    )


def explain_combo(item, st: State):
    exps = [explain_number(st, n) for n in item["numbers"]]
    route = " | ".join(f"{e['number']}: {e['driver_human']}" for e in exps)
    return {
        "human_summary": human_combo_summary(item, st),
        "plain_route": route,
        "number_explanations": exps,
        "technical_summary": (
            f"raw_quality={item.get('raw_quality', 0):.2f}; percentil={item.get('rank_percentile', 0):.2f}; "
            f"consenso={item.get('consensus_score', 0):.2f}; físico={item.get('physical_mean', 0):.3f}; temporal={item.get('temporal_mean', 0):.3f}; "
            f"entropía={item.get('entropy_mean', 0):.3f}; XGB={item.get('xgboost_contrast_mean', 0):.3f}; "
            f"Bayes={item.get('bayes_mean', 0):.3f}; Fourier={item.get('fourier_mean', 0):.3f}; estructura={item.get('structure_mean', 0):.3f}."
        ),
    }


def hindsight(draws, p0, config: GameConfig, weights):
    target = draws[-1]
    ctx = context(draws, p0, len(draws) - 1, config)
    model = train_model(draws, p0, len(draws) - 1, config)
    st = state_from_context(ctx, p0, model, config, weights)
    lines = [
        f"Auditoría inversa del sorteo {target.draw_id} ({target.date or 'sin fecha'}) · {config.label}",
        f"Combinación real: {' '.join(map(str, target.numbers))}",
        f"Ventana usada antes del sorteo: {len(ctx.rows)}",
        f"Pesos aprendidos: físico={weights['physical']:.2f}, temporal={weights['temporal']:.2f}, entropía={weights['entropy']:.2f}, Fourier={weights['fourier']:.2f}, Bayes={weights['bayes']:.2f}, XGBoost={weights['xgboost']:.2f}",
        f"Rango físico {config.label}: min={st.physics['min_weight']:.2f}g max={st.physics['max_weight']:.2f}g diff={st.physics['diff_weight']:.2f}g reglamento_ok={st.physics['regulatory_ok']}",
        f"Drift={st.drift} KL={st.kl:.6f} H15={st.h_recent:.4f} H120={st.h_window:.4f}",
    ]
    for n in target.numbers:
        exp = explain_number(st, n)
        rank = int(np.where((np.argsort(st.ensemble[1:])[::-1] + 1) == n)[0][0] + 1)
        lines.append(f"Número {n}: {exp['driver_human']}; {exp['reason']}; rank={rank}/56")
    return "\n".join(lines)


def manual_seed(st: State):
    out = []
    for n in range(1, MAX_NUMBER + 1):
        exp = explain_number(st, n)
        values = expert_values(st, n)
        out.append({
            "number": n,
            "score": round(float(st.ensemble[n] * 100), 4),
            "winner_component": exp["driver"],
            "winner_component_human": exp["driver_human"],
            "winner_component_score": round(float(exp["driver_score"]), 6),
            "reason": exp["reason"],
            "effective_weight": exp["effective_weight"],
            "physics_bonus": exp["physics_bonus"],
            "uses_in_window": exp["uses_in_window"],
            "experts": {k: round(float(v), 6) for k, v in values.items()},
            "period_fft": round(float(st.periods[n]), 4),
        })
    return sorted(out, key=lambda x: x["score"], reverse=True)


def run_pipeline():
    started = time.perf_counter()
    config = choose_game_config()
    csv_path = resolve_csv_path(config)
    draws = load_draws(csv_path)
    p0 = prior(draws)

    print(f"\n[1/5] Walk-Forward + selección de pesos para {config.label}...")
    wf = walk_forward(draws, p0, config)
    weights = wf.get("optimized_weights") or DEFAULT_WEIGHTS

    print("\n[2/5] Hindsight humano con reglas web...")
    hlog = hindsight(draws, p0, config, weights)
    print(hlog)

    print("\n[3/5] Modelo final CUDA entrenado con histórico completo...")
    ctx = context(draws, p0, len(draws), config)
    model = train_model(draws, p0, len(draws), config)
    st = state_from_context(ctx, p0, model, config, weights)

    print("\n[4/5] Monte Carlo profundo multi-estrategia con física web...")
    ranked, total, wf_factor = monte_carlo(st, wf, draws, config)
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

    result = {
        "last_update": datetime.now(timezone.utc).isoformat(),
        "source": "local_cruncher_v2_2_python_gpu_web_rules",
        "game_mode": config.mode,
        "game_label": config.label,
        "csv_path": csv_path,
        "confidence_kind": "operational_score_not_win_probability",
        "target_operational_confidence": TARGET_OPERATIONAL_CONFIDENCE,
        "drift_detected": bool(st.drift),
        "hindsight_log": hlog,
        "procedure_log": (
            f"Simulación seleccionada: {config.label}. Se cargó {csv_path}. "
            f"Se aplicaron pesos físicos separados de {config.label}, desgaste sigmoide y reglas web de físico/temporal/entropía. "
            f"Walk-Forward validó {wf['steps']} pasos y eligió pesos: físico={weights['physical']:.2f}, temporal={weights['temporal']:.2f}, entropía={weights['entropy']:.2f}, Fourier={weights['fourier']:.2f}, Bayes={weights['bayes']:.2f}, XGBoost={weights['xgboost']:.2f}. "
            f"Luego el modelo final entrenó con todo el histórico disponible y evaluó {total:,} combinaciones. "
            f"Score operativo = percentil + score crudo + consenso + factor Walk-Forward={wf_factor}; no es probabilidad real de ganar."
        ),
        "max_confidence_found": round(float(ranked[0]["confidence"] if ranked else 0), 4),
        "max_raw_quality_found": round(float(ranked[0]["raw_quality"] if ranked else 0), 4),
        "total_mc_evaluated": int(total),
        "optimized_weights": weights,
        "physics_summary": {
            "min_weight": round(float(st.physics["min_weight"]), 4),
            "max_weight": round(float(st.physics["max_weight"]), 4),
            "diff_weight": round(float(st.physics["diff_weight"]), 4),
            "regulatory_ok": bool(st.physics["regulatory_ok"]),
            "avg_effective_weight": round(float(st.physics["avg_effective"]), 4),
        },
        "number_scores": {str(n): round(float(st.ensemble[n] * 100), 4) for n in range(1, MAX_NUMBER + 1)},
        "manual_suggestion_seed": manual_seed(st),
        "walk_forward": wf,
        "generator_pool": pool,
        "top_combinations": top_enriched,
        "capital_preservation": not bool(top_enriched),
    }
    if not top_enriched:
        result["stop_loss_reason"] = f"No hubo combinaciones con score operativo >= {CONFIDENCE_THRESHOLD:.0f} tras {total:,} evaluaciones."

    Path("resultados.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nresultados.json generado para {config.label}. Max score operativo={result['max_confidence_found']} raw={result['max_raw_quality_found']} total={total:,}")
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
        print_header()
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
