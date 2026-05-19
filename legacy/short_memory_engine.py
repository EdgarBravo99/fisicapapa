#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
short_memory_engine.py

Motor cuantitativo determinista para análisis de ventana móvil.
Lee CSV, calcula STFT, posterior bayesiano con desgaste sigmoide, Drift KL,
XGBoost calibrado y búsqueda combinatoria vectorizada sin Monte Carlo aleatorio.
"""

from __future__ import annotations

import argparse
import itertools
import math
import os
import sys
import time
import warnings
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

try:
    from xgboost import XGBClassifier
except Exception as exc:
    raise RuntimeError("Instala xgboost con: pip install xgboost") from exc

try:
    from sklearn.calibration import CalibratedClassifierCV
    from sklearn.metrics import mean_squared_error
except Exception as exc:
    raise RuntimeError("Instala scikit-learn con: pip install scikit-learn") from exc

MAX_NUMBER = 56
PICK_COUNT = 6
WINDOW_SIZE = 120
DRIFT_WINDOW = 15
CONFIDENCE_THRESHOLD = 70.0
DRIFT_KL_THRESHOLD = 0.18
EPS = 1e-12

DEFAULT_CANDIDATE_POOL = 26
DEFAULT_BATCH_SIZE = 50000
DEFAULT_RETRAIN_EVERY = 1

SIGMOID = {"L": 0.0, "K": 1.0, "r": 0.09, "n0": 35.0}
ENSEMBLE_WEIGHTS = {"fourier": 0.27, "bayes": 0.33, "xgb": 0.40}


@dataclass(frozen=True)
class Draw:
    index: int
    draw_id: str
    date: Optional[str]
    numbers: Tuple[int, int, int, int, int, int]
    additional: Optional[int] = None


@dataclass
class ComponentState:
    fourier: np.ndarray
    fourier_periods: np.ndarray
    bayes: np.ndarray
    xgb: np.ndarray
    ensemble: np.ndarray
    drift_detected: bool
    kl_divergence: float
    entropy_recent: float
    entropy_window: float
    confidence_penalty: float


@dataclass
class WalkForwardResult:
    draw_id: str
    date: Optional[str]
    actual: Tuple[int, int, int, int, int, int]
    predicted_top6: List[int]
    hits_top6: int
    hits_top10: int
    mse: float
    route_confidence: float
    drift_detected: bool
    kl_divergence: float


def sigmoid_wear(impacts: float) -> float:
    return SIGMOID["L"] + (SIGMOID["K"] - SIGMOID["L"]) / (
        1.0 + math.exp(-SIGMOID["r"] * (impacts - SIGMOID["n0"]))
    )


def minmax01(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    out = np.zeros_like(values, dtype=float)
    valid = np.nan_to_num(values[1:], nan=0.0, posinf=0.0, neginf=0.0)
    lo = float(np.min(valid))
    hi = float(np.max(valid))
    if hi - lo <= EPS:
        out[1:] = 0.5
    else:
        out[1:] = (valid - lo) / (hi - lo)
    return out


def probability_from_counts(counts: np.ndarray) -> np.ndarray:
    p = np.zeros(MAX_NUMBER + 1, dtype=float)
    total = float(np.sum(counts[1:]))
    if total > 0:
        p[1:] = counts[1:] / total
    return p


def shannon_entropy(prob: np.ndarray) -> float:
    p = prob[1:]
    p = p[p > 0]
    return float(-np.sum(p * np.log2(p))) if len(p) else 0.0


def kl_divergence(p: np.ndarray, q: np.ndarray) -> float:
    pp = p[1:]
    qq = q[1:]
    mask = pp > 0
    if not np.any(mask):
        return 0.0
    return float(np.sum(pp[mask] * np.log(pp[mask] / np.maximum(qq[mask], EPS))))


def parse_int(value) -> Optional[int]:
    try:
        if pd.isna(value):
            return None
        return int(float(str(value).strip()))
    except Exception:
        return None


def detect_csv_columns(df: pd.DataFrame, natural_cols, additional_col, draw_col, date_col):
    cols = list(df.columns)
    lower = {str(c).lower().strip(): c for c in cols}
    if natural_cols:
        missing = [c for c in natural_cols if c not in df.columns]
        if missing:
            raise ValueError(f"Columnas naturales faltantes: {missing}")
        nums = natural_cols
    else:
        candidates = [
            ["n1", "n2", "n3", "n4", "n5", "n6"],
            ["num1", "num2", "num3", "num4", "num5", "num6"],
            ["numero1", "numero2", "numero3", "numero4", "numero5", "numero6"],
            ["bola1", "bola2", "bola3", "bola4", "bola5", "bola6"],
            ["b1", "b2", "b3", "b4", "b5", "b6"],
        ]
        nums = []
        for group in candidates:
            if all(c in lower for c in group):
                nums = [lower[c] for c in group]
                break
        if not nums:
            numeric_like = []
            for c in cols:
                parsed = pd.to_numeric(df[c], errors="coerce")
                if parsed.notna().mean() > 0.80 and parsed.between(1, MAX_NUMBER).mean() > 0.55:
                    numeric_like.append(c)
            if len(numeric_like) < 6:
                raise ValueError("No pude detectar 6 columnas naturales. Usa --natural-cols n1 n2 n3 n4 n5 n6")
            nums = numeric_like[:6]
    if additional_col and additional_col not in df.columns:
        raise ValueError(f"No existe la columna adicional: {additional_col}")
    if not additional_col:
        for c in ["adicional", "additional", "bonus", "extra", "num_adicional", "numero_adicional"]:
            if c in lower:
                additional_col = lower[c]
                break
    if draw_col and draw_col not in df.columns:
        raise ValueError(f"No existe la columna de sorteo: {draw_col}")
    if not draw_col:
        for c in ["sorteo", "draw", "draw_id", "draw_number", "concurso", "id"]:
            if c in lower:
                draw_col = lower[c]
                break
    if date_col and date_col not in df.columns:
        raise ValueError(f"No existe la columna de fecha: {date_col}")
    if not date_col:
        for c in ["fecha", "date", "draw_date", "f_sorteo"]:
            if c in lower:
                date_col = lower[c]
                break
    return nums, additional_col, draw_col, date_col


def sort_draws(draws: List[Draw]) -> List[Draw]:
    numeric_ids = [parse_int(d.draw_id) for d in draws]
    if all(x is not None for x in numeric_ids) and len(set(numeric_ids)) > 1:
        ordered = [d for _, d in sorted(zip(numeric_ids, draws), key=lambda x: x[0])]
    elif all(d.date for d in draws):
        dates = pd.to_datetime([d.date for d in draws], errors="coerce", dayfirst=True)
        if dates.notna().mean() > 0.8:
            ordered = [d for _, d in sorted(zip(dates, draws), key=lambda x: x[0])]
        else:
            ordered = draws
    else:
        ordered = draws
    return [Draw(i, d.draw_id, d.date, d.numbers, d.additional) for i, d in enumerate(ordered)]


def load_draws_from_csv(csv_path, natural_cols=None, additional_col=None, draw_col=None, date_col=None) -> List[Draw]:
    if not os.path.exists(csv_path):
        raise FileNotFoundError(csv_path)
    df = pd.read_csv(csv_path)
    natural_cols, additional_col, draw_col, date_col = detect_csv_columns(df, natural_cols, additional_col, draw_col, date_col)
    draws = []
    for _, row in df.iterrows():
        nums = []
        for c in natural_cols:
            n = parse_int(row[c])
            if n is not None and 1 <= n <= MAX_NUMBER:
                nums.append(n)
        nums = sorted(set(nums))
        if len(nums) != PICK_COUNT:
            continue
        add = None
        if additional_col:
            a = parse_int(row[additional_col])
            if a is not None and 1 <= a <= MAX_NUMBER:
                add = a
        draw_id = str(row[draw_col]) if draw_col else str(len(draws))
        date = str(row[date_col]) if date_col else None
        draws.append(Draw(len(draws), draw_id, date, tuple(nums), add))
    draws = sort_draws(draws)
    print(f"CSV cargado: {len(draws)} sorteos válidos")
    print(f"Columnas naturales: {natural_cols}")
    print(f"Adicional: {additional_col or 'N/A'} | Sorteo: {draw_col or 'N/A'} | Fecha: {date_col or 'N/A'}")
    return draws


def binary_matrix(draws: Sequence[Draw]) -> np.ndarray:
    mat = np.zeros((len(draws), MAX_NUMBER + 1), dtype=float)
    for i, d in enumerate(draws):
        mat[i, list(d.numbers)] = 1.0
    return mat


def counts_from_draws(draws: Sequence[Draw]) -> np.ndarray:
    if not draws:
        return np.zeros(MAX_NUMBER + 1, dtype=float)
    return np.sum(binary_matrix(draws), axis=0)


def static_prior(draws: Sequence[Draw]) -> np.ndarray:
    return probability_from_counts(counts_from_draws(draws))


def drift_state(active_window: Sequence[Draw]):
    if len(active_window) < DRIFT_WINDOW:
        return False, 0.0, 0.0, 0.0, 1.0
    p_window = probability_from_counts(counts_from_draws(active_window))
    p_recent = probability_from_counts(counts_from_draws(active_window[-DRIFT_WINDOW:]))
    h_window = shannon_entropy(p_window)
    h_recent = shannon_entropy(p_recent)
    kl = kl_divergence(p_recent, p_window)
    detected = kl >= DRIFT_KL_THRESHOLD
    penalty = 0.70 if detected else 1.0
    return detected, kl, h_recent, h_window, penalty


def stft_scores(active_window: Sequence[Draw]):
    scores = np.zeros(MAX_NUMBER + 1, dtype=float)
    periods = np.zeros(MAX_NUMBER + 1, dtype=float)
    n_rows = len(active_window)
    if n_rows < 12:
        scores[1:] = 0.5
        return scores, periods
    mat = binary_matrix(active_window)[:, 1:]
    segment = min(32, max(12, n_rows // 2))
    hop = max(3, segment // 4)
    starts = list(range(0, max(1, n_rows - segment + 1), hop))
    last_start = max(0, n_rows - segment)
    if starts[-1] != last_start:
        starts.append(last_start)
    window = np.hanning(segment).reshape(-1, 1)
    power_acc = np.zeros(MAX_NUMBER, dtype=float)
    bin_acc = np.zeros(MAX_NUMBER, dtype=float)
    votes = np.zeros(MAX_NUMBER, dtype=float)
    for s in starts:
        chunk = mat[s:s + segment, :]
        if chunk.shape[0] != segment:
            continue
        centered = chunk - np.mean(chunk, axis=0, keepdims=True)
        spectrum = np.fft.rfft(centered * window, axis=0)
        power = np.abs(spectrum) ** 2
        usable = power[1:, :]
        total_power = np.sum(usable, axis=0)
        dom_idx = np.argmax(usable, axis=0)
        dom_power = usable[dom_idx, np.arange(MAX_NUMBER)]
        active = total_power > 0
        power_acc[active] += np.log1p(dom_power[active] + 0.25 * total_power[active])
        bin_acc[active] += dom_idx[active] + 1
        votes[active] += 1
    raw = np.zeros(MAX_NUMBER + 1, dtype=float)
    raw[1:] = power_acc
    scores = minmax01(raw)
    for i in range(MAX_NUMBER):
        if votes[i] > 0:
            periods[i + 1] = segment / max(bin_acc[i] / votes[i], 1.0)
    return scores, periods


def bayes_sigmoid_posterior(active_window: Sequence[Draw], prior: np.ndarray) -> np.ndarray:
    counts = counts_from_draws(active_window)
    wear = np.zeros(MAX_NUMBER + 1, dtype=float)
    for n in range(1, MAX_NUMBER + 1):
        wear[n] = sigmoid_wear(counts[n])
    wear_norm = minmax01(wear)
    freq_norm = minmax01(counts)
    raw = np.zeros(MAX_NUMBER + 1, dtype=float)
    raw[1:] = prior[1:] * (1.0 + 2.2 * wear_norm[1:]) * (1.0 + 0.85 * freq_norm[1:])
    posterior = probability_from_counts(raw)
    return minmax01(posterior)


def last_seen_gaps(active_window: Sequence[Draw]) -> np.ndarray:
    gaps = np.full(MAX_NUMBER + 1, len(active_window) + 1, dtype=float)
    for gap, d in enumerate(reversed(active_window)):
        for n in d.numbers:
            if gaps[n] == len(active_window) + 1:
                gaps[n] = gap
    return gaps


def rolling_freqs(mat: np.ndarray, k: int) -> np.ndarray:
    if len(mat) == 0:
        return np.zeros(MAX_NUMBER + 1, dtype=float)
    subset = mat[-min(k, len(mat)):]
    return np.mean(subset, axis=0)


def feature_matrix_for_context(active_window: Sequence[Draw], prior: np.ndarray, fourier: np.ndarray, bayes: np.ndarray) -> np.ndarray:
    mat = binary_matrix(active_window)
    gaps = last_seen_gaps(active_window)
    f15 = rolling_freqs(mat, 15)
    f30 = rolling_freqs(mat, 30)
    f120 = rolling_freqs(mat, min(WINDOW_SIZE, len(active_window)))
    nums = np.arange(1, MAX_NUMBER + 1, dtype=float)
    odd = (nums % 2).astype(float)
    decade = np.floor((nums - 1) / 10) / 5.0
    side = (nums > 28).astype(float)
    gap_scaled = np.minimum(gaps[1:], WINDOW_SIZE) / WINDOW_SIZE
    recency = 1.0 / (1.0 + gaps[1:])
    return np.column_stack([nums / MAX_NUMBER, prior[1:], f15[1:], f30[1:], f120[1:], gap_scaled, recency, fourier[1:], bayes[1:], odd, decade, side]).astype(float)


def build_training_dataset(draws: Sequence[Draw], prior: np.ndarray, start_idx: int, end_idx: int):
    X_parts = []
    y_parts = []
    for target_idx in range(start_idx, end_idx):
        context = draws[max(0, target_idx - WINDOW_SIZE):target_idx]
        if len(context) < 20:
            continue
        fourier, _ = stft_scores(context)
        bayes = bayes_sigmoid_posterior(context, prior)
        X_parts.append(feature_matrix_for_context(context, prior, fourier, bayes))
        y = np.zeros(MAX_NUMBER, dtype=int)
        for n in draws[target_idx].numbers:
            y[n - 1] = 1
        y_parts.append(y)
    if not X_parts:
        return np.empty((0, 12), dtype=float), np.empty((0,), dtype=int)
    return np.vstack(X_parts), np.concatenate(y_parts)


def calibrated_xgb_model() -> CalibratedClassifierCV:
    base = XGBClassifier(n_estimators=90, max_depth=3, learning_rate=0.055, subsample=0.92, colsample_bytree=0.92, min_child_weight=2.0, reg_lambda=1.15, objective="binary:logistic", eval_metric="logloss", n_jobs=-1, random_state=73, verbosity=0)
    try:
        return CalibratedClassifierCV(estimator=base, method="sigmoid", cv=3)
    except TypeError:
        return CalibratedClassifierCV(base_estimator=base, method="sigmoid", cv=3)


def train_xgb(draws: Sequence[Draw], prior: np.ndarray, prediction_idx: int):
    start_idx = max(1, prediction_idx - WINDOW_SIZE)
    X, y = build_training_dataset(draws, prior, start_idx, prediction_idx)
    if len(y) < 500 or int(np.sum(y)) < 18:
        return None
    model = calibrated_xgb_model()
    model.fit(X, y)
    return model


def component_scores(active_window: Sequence[Draw], prior: np.ndarray, model) -> ComponentState:
    fourier, periods = stft_scores(active_window)
    bayes = bayes_sigmoid_posterior(active_window, prior)
    if model is None:
        xgb = np.zeros(MAX_NUMBER + 1, dtype=float)
        xgb[1:] = bayes[1:]
    else:
        X_live = feature_matrix_for_context(active_window, prior, fourier, bayes)
        probs = model.predict_proba(X_live)[:, 1]
        xgb = np.zeros(MAX_NUMBER + 1, dtype=float)
        xgb[1:] = probs
        xgb = minmax01(xgb)
    drift, kl, h_recent, h_window, penalty = drift_state(active_window)
    ensemble = np.zeros(MAX_NUMBER + 1, dtype=float)
    ensemble[1:] = ENSEMBLE_WEIGHTS["fourier"] * fourier[1:] + ENSEMBLE_WEIGHTS["bayes"] * bayes[1:] + ENSEMBLE_WEIGHTS["xgb"] * xgb[1:]
    if drift:
        ensemble[1:] = 0.5 + (ensemble[1:] - 0.5) * penalty
    ensemble = minmax01(ensemble)
    return ComponentState(fourier, periods, bayes, xgb, ensemble, drift, kl, h_recent, h_window, penalty)


def top_numbers(scores: np.ndarray, k: int) -> List[int]:
    return list(np.argsort(scores[1:])[::-1][:k] + 1)


def component_route(state: ComponentState, n: int):
    comps = {"Fourier": float(state.fourier[n]), "Bayes": float(state.bayes[n]), "XGBoost": float(state.xgb[n])}
    winner, score = max(comps.items(), key=lambda kv: kv[1])
    if winner == "Fourier":
        period = state.fourier_periods[n]
        reason = f"Detectado por Fourier (Ciclo corto p≈{period:.1f})" if period > 0 else "Detectado por Fourier"
    elif winner == "Bayes":
        reason = "Anomalía Bayesiana con desgaste sigmoide"
    else:
        reason = "XGBoost calibrado"
    return winner, score, reason


def hindsight_audit(draw: Draw, state: ComponentState) -> float:
    explanations = []
    confs = []
    for n in draw.numbers:
        _, score, reason = component_route(state, n)
        confs.append(score)
        explanations.append(f"Número {n}: {reason}")
    route_conf = float(np.mean(confs) * 100.0)
    if state.drift_detected:
        route_conf *= state.confidence_penalty
    route_conf = max(0.0, min(99.9, route_conf))
    print(f"Sorteo {draw.draw_id} Explicado -> " + ". ".join(explanations) + f". Confianza de la ruta: {route_conf:.1f}% | KL={state.kl_divergence:.4f}")
    return route_conf


def evaluate_prediction(draw: Draw, state: ComponentState):
    pred6 = top_numbers(state.ensemble, 6)
    pred10 = top_numbers(state.ensemble, 10)
    actual = set(draw.numbers)
    y = np.zeros(MAX_NUMBER + 1, dtype=float)
    for n in draw.numbers:
        y[n] = 1.0
    return pred6, len(actual.intersection(pred6)), len(actual.intersection(pred10)), float(mean_squared_error(y[1:], state.ensemble[1:]))


def walk_forward(draws: Sequence[Draw], prior: np.ndarray, retrain_every: int) -> List[WalkForwardResult]:
    start = max(20, len(draws) - WINDOW_SIZE)
    results = []
    model = None
    last_train_idx = -10**9
    print("\n═══════════════════════════════════════════════════════")
    print(f"WALK-FORWARD SHORT MEMORY | {len(draws) - start} sorteos")
    print("═══════════════════════════════════════════════════════")
    for idx in range(start, len(draws)):
        active = draws[max(0, idx - WINDOW_SIZE):idx]
        if len(active) < 20:
            continue
        if model is None or idx - last_train_idx >= max(1, retrain_every):
            model = train_xgb(draws, prior, idx)
            last_train_idx = idx
        state = component_scores(active, prior, model)
        route = hindsight_audit(draws[idx], state)
        pred6, hits6, hits10, mse = evaluate_prediction(draws[idx], state)
        results.append(WalkForwardResult(draws[idx].draw_id, draws[idx].date, draws[idx].numbers, pred6, hits6, hits10, mse, route, state.drift_detected, state.kl_divergence))
    return results


def structure_score(combos: np.ndarray) -> np.ndarray:
    combos = np.asarray(combos, dtype=float)
    pares = np.sum((combos % 2) == 0, axis=1)
    low = np.sum(combos <= 28, axis=1)
    sums = np.sum(combos, axis=1)
    consec = np.sum(np.diff(combos, axis=1) == 1, axis=1)
    decades = np.array([len(set(((row - 1) // 10).astype(int))) for row in combos], dtype=float)
    score = (1.0 - np.abs(pares - 3) / 3.0) * 0.26 + (1.0 - np.abs(low - 3) / 3.0) * 0.20 + (decades / 6.0) * 0.20 + (1.0 - np.minimum(consec, 4) / 4.0) * 0.14 + np.where((sums >= 110) & (sums <= 240), 1.0, 0.55) * 0.20
    return np.clip(score, 0.0, 1.0)


def deterministic_combo_search(state: ComponentState, candidate_pool: int, batch_size: int) -> List[Dict[str, object]]:
    pool = top_numbers(state.ensemble, min(candidate_pool, MAX_NUMBER))
    records = []
    combo_iter = itertools.combinations(pool, PICK_COUNT)
    while True:
        batch = list(itertools.islice(combo_iter, batch_size))
        if not batch:
            break
        arr = np.asarray(batch, dtype=int)
        ens = np.mean(state.ensemble[arr], axis=1)
        xgb = np.mean(state.xgb[arr], axis=1)
        bayes = np.mean(state.bayes[arr], axis=1)
        fourier = np.mean(state.fourier[arr], axis=1)
        dispersion = np.std(arr, axis=1) / 20.0
        struct = structure_score(arr)
        confidence = (0.40 * ens + 0.28 * xgb + 0.16 * bayes + 0.08 * fourier + 0.05 * struct + 0.03 * np.clip(dispersion, 0.0, 1.0)) * 100.0
        if state.drift_detected:
            confidence *= state.confidence_penalty
        order = np.argsort(confidence)[::-1][:40]
        for i in order:
            records.append({"combo": list(map(int, arr[i])), "confidence": float(confidence[i]), "ensemble": float(ens[i]), "xgb": float(xgb[i]), "bayes": float(bayes[i]), "fourier": float(fourier[i]), "structure": float(struct[i])})
        records = sorted(records, key=lambda r: r["confidence"], reverse=True)[:80]
    return sorted(records, key=lambda r: r["confidence"], reverse=True)


def final_prediction(draws: Sequence[Draw], prior: np.ndarray, candidate_pool: int, batch_size: int) -> None:
    active = draws[-WINDOW_SIZE:]
    model = train_xgb(draws, prior, len(draws))
    state = component_scores(active, prior, model)
    ranked = deterministic_combo_search(state, candidate_pool, batch_size)
    print("\n═══════════════════════════════════════════════════════")
    print("PREDICCIÓN DETERMINISTA SHORT MEMORY")
    print("═══════════════════════════════════════════════════════")
    print(f"Ventana activa: {len(active)} sorteos")
    print(f"Drift detectado: {state.drift_detected} | KL={state.kl_divergence:.6f}")
    print(f"Entropía últimos 15: {state.entropy_recent:.4f} | Entropía ventana: {state.entropy_window:.4f}")
    print(f"Búsqueda combinatoria: C({min(candidate_pool, MAX_NUMBER)}, 6)")
    if not ranked:
        print("No se generaron combinaciones candidatas.")
        return
    top = ranked[0]
    if float(top["confidence"]) < CONFIDENCE_THRESHOLD:
        print(f"OPERACIÓN ABORTADA: Confianza máxima del {top['confidence']:.1f}% por debajo del umbral del {CONFIDENCE_THRESHOLD:.0f}%.")
        print(f"Mejor combinación no operativa: {top['combo']}")
        return
    print(f"Confianza máxima calibrada: {top['confidence']:.1f}%")
    for i, item in enumerate(ranked[:10], start=1):
        print(f"{i:02d}. {item['combo']} | Conf={item['confidence']:.1f}% | XGB={item['xgb']:.3f} Bayes={item['bayes']:.3f} Fourier={item['fourier']:.3f} Struct={item['structure']:.3f}")


def summarize(results: Sequence[WalkForwardResult]) -> None:
    if not results:
        return
    print("\n═══════════════════════════════════════════════════════")
    print("RESUMEN WALK-FORWARD")
    print("═══════════════════════════════════════════════════════")
    print(f"Sorteos auditados: {len(results)}")
    print(f"Hits promedio Top-6: {np.mean([r.hits_top6 for r in results]):.2f}/6")
    print(f"Hits promedio Top-10: {np.mean([r.hits_top10 for r in results]):.2f}/6")
    print(f"MSE promedio: {np.mean([r.mse for r in results]):.5f}")
    print(f"Confianza de ruta promedio: {np.mean([r.route_confidence for r in results]):.1f}%")
    print(f"Drift rate: {np.mean([1.0 if r.drift_detected else 0.0 for r in results]) * 100:.1f}%")


def save_audit(results: Sequence[WalkForwardResult], path: str) -> None:
    if not results:
        return
    rows = []
    for r in results:
        rows.append({"draw_id": r.draw_id, "date": r.date, "actual": " ".join(map(str, r.actual)), "predicted_top6": " ".join(map(str, r.predicted_top6)), "hits_top6": r.hits_top6, "hits_top10": r.hits_top10, "mse": r.mse, "route_confidence": r.route_confidence, "drift_detected": r.drift_detected, "kl_divergence": r.kl_divergence})
    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8-sig")
    print(f"Auditoría guardada: {path}")


def parse_args():
    p = argparse.ArgumentParser(description="Motor Short Memory determinista y acelerado")
    p.add_argument("--csv", required=True, help="Ruta al CSV histórico")
    p.add_argument("--natural-cols", nargs=6, default=None, help="Columnas de los 6 números naturales")
    p.add_argument("--additional-col", default=None, help="Columna del adicional")
    p.add_argument("--draw-col", default=None, help="Columna de sorteo")
    p.add_argument("--date-col", default=None, help="Columna de fecha")
    p.add_argument("--audit-output", default="short_memory_audit.csv", help="CSV de auditoría")
    p.add_argument("--skip-walk-forward", action="store_true", help="Solo genera predicción final")
    p.add_argument("--candidate-pool", type=int, default=DEFAULT_CANDIDATE_POOL, help="Top números usados para enumerar combinaciones")
    p.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE, help="Tamaño de lote vectorizado")
    p.add_argument("--retrain-every", type=int, default=DEFAULT_RETRAIN_EVERY, help="Reentrenar XGBoost cada N pasos")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    t0 = time.perf_counter()
    draws = load_draws_from_csv(args.csv, args.natural_cols, args.additional_col, args.draw_col, args.date_col)
    if len(draws) < 30:
        print("ERROR: se necesitan al menos 30 sorteos válidos")
        sys.exit(1)
    prior = static_prior(draws)
    print(f"Prior estático: histórico completo ({len(draws)} sorteos)")
    print(f"Ventana móvil: WINDOW_SIZE={WINDOW_SIZE}")
    if not args.skip_walk_forward:
        results = walk_forward(draws, prior, args.retrain_every)
        summarize(results)
        save_audit(results, args.audit_output)
    final_prediction(draws, prior, args.candidate_pool, args.batch_size)
    print(f"\nTiempo total: {time.perf_counter() - t0:.2f}s")


if __name__ == "__main__":
    main()
