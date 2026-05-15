#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import math
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from scipy.fft import rfft, rfftfreq
from sklearn.calibration import CalibratedClassifierCV
from xgboost import XGBClassifier

MAX_NUMBER = 56
PICK_COUNT = 6
WINDOW_SIZE = 120
DRIFT_WINDOW = 15
MC_COMBINATIONS = 1_000_000
CONFIDENCE_THRESHOLD = 70.0
DRIFT_KL_THRESHOLD = 0.18
RANDOM_SEED = 73073
BATCH_SIZE = 100_000
EPS = 1e-12

SIGMOID = {
    "L": 0.0,
    "K": 1.0,
    "r": 0.09,
    "n0": 35.0,
}

ENSEMBLE_WEIGHTS = {
    "fourier": 0.28,
    "bayes": 0.32,
    "xgboost": 0.40,
}


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
    fourier_period: np.ndarray
    bayes: np.ndarray
    xgb_raw: np.ndarray
    xgb_contrast: np.ndarray
    ensemble: np.ndarray
    drift_detected: bool
    kl_divergence: float
    entropy_recent: float
    entropy_window: float


def parse_int(value) -> Optional[int]:
    try:
        if pd.isna(value):
            return None
        return int(float(str(value).strip()))
    except Exception:
        return None


def minmax01(values: np.ndarray) -> np.ndarray:
    arr = np.asarray(values, dtype=np.float64)
    out = np.zeros_like(arr, dtype=np.float64)
    valid = np.nan_to_num(arr[1:], nan=0.0, posinf=0.0, neginf=0.0)
    lo = float(np.min(valid))
    hi = float(np.max(valid))
    out[1:] = 0.5 if hi - lo <= EPS else (valid - lo) / (hi - lo)
    return out


def sigmoid_wear(impacts: float) -> float:
    return SIGMOID["L"] + (SIGMOID["K"] - SIGMOID["L"]) / (
        1.0 + math.exp(-SIGMOID["r"] * (impacts - SIGMOID["n0"]))
    )


def detect_csv_columns(df: pd.DataFrame) -> Tuple[List[str], Optional[str], Optional[str], Optional[str]]:
    cols = list(df.columns)
    lower = {str(c).lower().strip(): c for c in cols}
    candidates = [
        ["n1", "n2", "n3", "n4", "n5", "n6"],
        ["num1", "num2", "num3", "num4", "num5", "num6"],
        ["numero1", "numero2", "numero3", "numero4", "numero5", "numero6"],
        ["bola1", "bola2", "bola3", "bola4", "bola5", "bola6"],
        ["b1", "b2", "b3", "b4", "b5", "b6"],
    ]
    natural_cols: List[str] = []
    for group in candidates:
        if all(c in lower for c in group):
            natural_cols = [lower[c] for c in group]
            break
    if not natural_cols:
        numeric_like = []
        for c in cols:
            parsed = pd.to_numeric(df[c], errors="coerce")
            if parsed.notna().mean() > 0.80 and parsed.between(1, MAX_NUMBER).mean() > 0.55:
                numeric_like.append(c)
        if len(numeric_like) < PICK_COUNT:
            raise ValueError("No pude detectar columnas de 6 números. Usa encabezados n1,n2,n3,n4,n5,n6.")
        natural_cols = numeric_like[:PICK_COUNT]

    additional_col = None
    for c in ["adicional", "additional", "bonus", "extra", "num_adicional", "numero_adicional"]:
        if c in lower:
            additional_col = lower[c]
            break

    draw_col = None
    for c in ["sorteo", "draw", "draw_id", "draw_number", "concurso", "id"]:
        if c in lower:
            draw_col = lower[c]
            break

    date_col = None
    for c in ["fecha", "date", "draw_date", "f_sorteo"]:
        if c in lower:
            date_col = lower[c]
            break

    return natural_cols, additional_col, draw_col, date_col


def sort_draws(draws: List[Draw]) -> List[Draw]:
    numeric_ids = [parse_int(d.draw_id) for d in draws]
    if all(x is not None for x in numeric_ids) and len(set(numeric_ids)) > 1:
        ordered = [d for _, d in sorted(zip(numeric_ids, draws), key=lambda x: x[0])]
    elif all(d.date for d in draws):
        dates = pd.to_datetime([d.date for d in draws], errors="coerce", dayfirst=True)
        ordered = [d for _, d in sorted(zip(dates, draws), key=lambda x: x[0])] if dates.notna().mean() > 0.8 else draws
    else:
        ordered = draws
    return [Draw(i, d.draw_id, d.date, d.numbers, d.additional) for i, d in enumerate(ordered)]


def load_historial(path: str = "historial.csv") -> List[Draw]:
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"No existe {csv_path.resolve()}")
    df = pd.read_csv(csv_path)
    natural_cols, additional_col, draw_col, date_col = detect_csv_columns(df)
    draws: List[Draw] = []
    for _, row in df.iterrows():
        nums = []
        for col in natural_cols:
            n = parse_int(row[col])
            if n is not None and 1 <= n <= MAX_NUMBER:
                nums.append(n)
        nums = sorted(set(nums))
        if len(nums) != PICK_COUNT:
            continue
        add = None
        if additional_col:
            add_val = parse_int(row[additional_col])
            if add_val is not None and 1 <= add_val <= MAX_NUMBER:
                add = add_val
        draw_id = str(row[draw_col]) if draw_col else str(len(draws))
        date = str(row[date_col]) if date_col else None
        draws.append(Draw(len(draws), draw_id, date, tuple(nums), add))
    draws = sort_draws(draws)
    if len(draws) < WINDOW_SIZE + 1:
        raise ValueError(f"Se requieren al menos {WINDOW_SIZE + 1} sorteos válidos; detectados: {len(draws)}")
    print(f"CSV leído: {len(draws)} sorteos válidos | columnas: {natural_cols}")
    return draws


def binary_matrix(draws: Sequence[Draw]) -> np.ndarray:
    mat = np.zeros((len(draws), MAX_NUMBER + 1), dtype=np.float64)
    for i, d in enumerate(draws):
        mat[i, list(d.numbers)] = 1.0
    return mat


def counts_from_draws(draws: Sequence[Draw]) -> np.ndarray:
    return np.sum(binary_matrix(draws), axis=0) if draws else np.zeros(MAX_NUMBER + 1, dtype=np.float64)


def probability_from_counts(counts: np.ndarray) -> np.ndarray:
    p = np.zeros(MAX_NUMBER + 1, dtype=np.float64)
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


def static_prior(draws: Sequence[Draw]) -> np.ndarray:
    return probability_from_counts(counts_from_draws(draws))


def fft_microcycle_scores(window: Sequence[Draw]) -> Tuple[np.ndarray, np.ndarray]:
    mat = binary_matrix(window)[:, 1:]
    centered = mat - np.mean(mat, axis=0, keepdims=True)
    spectrum = rfft(centered, axis=0)
    power = np.abs(spectrum) ** 2
    freqs = rfftfreq(mat.shape[0], d=1.0)
    scores = np.zeros(MAX_NUMBER + 1, dtype=np.float64)
    periods = np.zeros(MAX_NUMBER + 1, dtype=np.float64)
    if power.shape[0] <= 2:
        scores[1:] = 0.5
        return scores, periods
    usable_power = power[1:, :]
    usable_freqs = freqs[1:]
    dominant_idx = np.argmax(usable_power, axis=0)
    dominant_power = usable_power[dominant_idx, np.arange(MAX_NUMBER)]
    total_power = np.sum(usable_power, axis=0)
    raw = np.zeros(MAX_NUMBER + 1, dtype=np.float64)
    raw[1:] = np.log1p(dominant_power + total_power)
    scores = minmax01(raw)
    for i in range(MAX_NUMBER):
        f = float(usable_freqs[dominant_idx[i]])
        periods[i + 1] = 1.0 / f if f > EPS else 0.0
    return scores, periods


def bayesian_sigmoid_posterior(window: Sequence[Draw], prior: np.ndarray) -> np.ndarray:
    counts = counts_from_draws(window)
    wear = np.zeros(MAX_NUMBER + 1, dtype=np.float64)
    for n in range(1, MAX_NUMBER + 1):
        wear[n] = sigmoid_wear(float(counts[n]))
    wear_contrast = minmax01(wear)
    freq_contrast = minmax01(counts)
    posterior_raw = np.zeros(MAX_NUMBER + 1, dtype=np.float64)
    posterior_raw[1:] = prior[1:] * (1.0 + 2.4 * wear_contrast[1:]) * (1.0 + 1.15 * freq_contrast[1:])
    posterior = probability_from_counts(posterior_raw)
    return minmax01(posterior)


def drift_detection(window: Sequence[Draw]) -> Tuple[bool, float, float, float]:
    p_window = probability_from_counts(counts_from_draws(window))
    p_recent = probability_from_counts(counts_from_draws(window[-DRIFT_WINDOW:]))
    entropy_window = shannon_entropy(p_window)
    entropy_recent = shannon_entropy(p_recent)
    kl = kl_divergence(p_recent, p_window)
    return bool(kl >= DRIFT_KL_THRESHOLD), kl, entropy_recent, entropy_window


def last_seen_gaps(window: Sequence[Draw]) -> np.ndarray:
    gaps = np.full(MAX_NUMBER + 1, len(window) + 1, dtype=np.float64)
    for gap, d in enumerate(reversed(window)):
        for n in d.numbers:
            if gaps[n] == len(window) + 1:
                gaps[n] = float(gap)
    return gaps


def rolling_freq(mat: np.ndarray, k: int) -> np.ndarray:
    if mat.shape[0] == 0:
        return np.zeros(MAX_NUMBER + 1, dtype=np.float64)
    return np.mean(mat[-min(k, mat.shape[0]):], axis=0)


def feature_matrix(window: Sequence[Draw], prior: np.ndarray, fourier: np.ndarray, bayes: np.ndarray) -> np.ndarray:
    mat = binary_matrix(window)
    gaps = last_seen_gaps(window)
    nums = np.arange(1, MAX_NUMBER + 1, dtype=np.float64)
    odd = (nums % 2).astype(np.float64)
    decade = np.floor((nums - 1) / 10.0) / 5.0
    side = (nums > 28).astype(np.float64)
    gap_scaled = np.minimum(gaps[1:], WINDOW_SIZE) / WINDOW_SIZE
    recency = 1.0 / (1.0 + gaps[1:])
    return np.column_stack([
        nums / MAX_NUMBER,
        prior[1:],
        rolling_freq(mat, 15)[1:],
        rolling_freq(mat, 30)[1:],
        rolling_freq(mat, 60)[1:],
        rolling_freq(mat, WINDOW_SIZE)[1:],
        gap_scaled,
        recency,
        fourier[1:],
        bayes[1:],
        odd,
        decade,
        side,
    ]).astype(np.float32)


def build_training_dataset(draws: Sequence[Draw], prior: np.ndarray, end_idx: int) -> Tuple[np.ndarray, np.ndarray]:
    start_idx = max(1, end_idx - WINDOW_SIZE)
    X_parts = []
    y_parts = []
    for target_idx in range(start_idx, end_idx):
        window = draws[max(0, target_idx - WINDOW_SIZE):target_idx]
        if len(window) < 40:
            continue
        fourier, _ = fft_microcycle_scores(window)
        bayes = bayesian_sigmoid_posterior(window, prior)
        X_parts.append(feature_matrix(window, prior, fourier, bayes))
        y = np.zeros(MAX_NUMBER, dtype=np.int32)
        for n in draws[target_idx].numbers:
            y[n - 1] = 1
        y_parts.append(y)
    if not X_parts:
        raise ValueError("No se pudo construir dataset de entrenamiento con la ventana actual.")
    return np.vstack(X_parts), np.concatenate(y_parts)


def make_gpu_xgb() -> XGBClassifier:
    return XGBClassifier(
        n_estimators=220,
        max_depth=4,
        learning_rate=0.035,
        subsample=1.0,
        colsample_bytree=1.0,
        min_child_weight=1.0,
        reg_lambda=0.65,
        objective="binary:logistic",
        eval_metric="logloss",
        scale_pos_weight=(MAX_NUMBER - PICK_COUNT) / PICK_COUNT,
        tree_method="hist",
        device="cuda",
        random_state=RANDOM_SEED,
        n_jobs=0,
        verbosity=1,
    )


def make_calibrator(base_model: XGBClassifier) -> CalibratedClassifierCV:
    try:
        return CalibratedClassifierCV(estimator=base_model, method="sigmoid", cv=3)
    except TypeError:
        return CalibratedClassifierCV(base_estimator=base_model, method="sigmoid", cv=3)


def train_gpu_calibrated_xgb(draws: Sequence[Draw], prior: np.ndarray, end_idx: int) -> CalibratedClassifierCV:
    X, y = build_training_dataset(draws, prior, end_idx)
    positives = int(np.sum(y))
    if positives < 18:
        raise ValueError(f"Insuficientes positivos para calibración: {positives}")
    model = make_calibrator(make_gpu_xgb())
    print(f"Entrenando XGBoost CUDA calibrado | X={X.shape} | positivos={positives}")
    model.fit(X, y)
    return model


def build_component_state(window: Sequence[Draw], prior: np.ndarray, model: CalibratedClassifierCV) -> ComponentState:
    fourier, periods = fft_microcycle_scores(window)
    bayes = bayesian_sigmoid_posterior(window, prior)
    X_live = feature_matrix(window, prior, fourier, bayes)
    xgb_raw = np.zeros(MAX_NUMBER + 1, dtype=np.float64)
    xgb_raw[1:] = model.predict_proba(X_live)[:, 1]
    xgb_contrast = minmax01(xgb_raw)
    ensemble = np.zeros(MAX_NUMBER + 1, dtype=np.float64)
    ensemble[1:] = (
        ENSEMBLE_WEIGHTS["fourier"] * fourier[1:]
        + ENSEMBLE_WEIGHTS["bayes"] * bayes[1:]
        + ENSEMBLE_WEIGHTS["xgboost"] * xgb_contrast[1:]
    )
    ensemble = minmax01(ensemble)
    drift_detected, kl, entropy_recent, entropy_window = drift_detection(window)
    return ComponentState(fourier, periods, bayes, xgb_raw, xgb_contrast, ensemble, drift_detected, kl, entropy_recent, entropy_window)


def component_winner(state: ComponentState, n: int) -> Tuple[str, float]:
    comps = {
        "Fourier": float(state.fourier[n]),
        "Bayes": float(state.bayes[n]),
        "XGBoost": float(state.xgb_contrast[n]),
    }
    return max(comps.items(), key=lambda kv: kv[1])


def rank_of_number(scores: np.ndarray, n: int) -> int:
    order = np.argsort(scores[1:])[::-1] + 1
    pos = np.where(order == n)[0]
    return int(pos[0] + 1) if len(pos) else MAX_NUMBER


def hindsight_attribution(draws: Sequence[Draw], prior: np.ndarray) -> Tuple[str, ComponentState]:
    target = draws[-1]
    end_idx = len(draws) - 1
    model = train_gpu_calibrated_xgb(draws, prior, end_idx)
    window = draws[max(0, end_idx - WINDOW_SIZE):end_idx]
    state = build_component_state(window, prior, model)
    lines = [
        f"Auditoría inversa del sorteo {target.draw_id} ({target.date or 'sin fecha'})",
        f"Combinación real: {' '.join(map(str, target.numbers))}",
        f"Ventana usada antes del sorteo: {len(window)} sorteos",
        f"Drift detectado: {state.drift_detected} | KL={state.kl_divergence:.6f} | H15={state.entropy_recent:.4f} | H120={state.entropy_window:.4f}",
    ]
    tracked_scores = []
    for n in target.numbers:
        winner, winner_score = component_winner(state, n)
        rank = rank_of_number(state.ensemble, n)
        tracked = rank <= 12
        tracked_scores.append(float(state.ensemble[n]))
        period = state.fourier_period[n]
        lines.append(
            f"Número {n}: ganador_componente={winner}({winner_score:.4f}); "
            f"Fourier={state.fourier[n]:.4f}; Bayes={state.bayes[n]:.4f}; "
            f"XGBoostRaw={state.xgb_raw[n]:.6f}; XGBoostContrast={state.xgb_contrast[n]:.4f}; "
            f"Ensemble={state.ensemble[n]:.4f}; Rank={rank}/56; "
            f"PeriodoFFT={period:.2f}; Resultado={'RASTREADO' if tracked else 'NO_RASTREADO'}"
        )
    route_confidence = float(np.mean(tracked_scores) * 100.0)
    lines.append(f"Confianza de ruta inversa: {route_confidence:.2f}%")
    return "\n".join(lines), state


def generate_mc_combinations(state: ComponentState, total: int, batch_size: int) -> List[Dict[str, float | List[int]]]:
    rng = np.random.default_rng(RANDOM_SEED)
    numbers = np.arange(1, MAX_NUMBER + 1, dtype=np.int16)
    weights = np.maximum(state.ensemble[1:], EPS)
    weights = weights / np.sum(weights)
    log_weights = np.log(weights).reshape(1, -1)
    top_records: Dict[Tuple[int, ...], Dict[str, float | List[int]]] = {}
    generated = 0

    while generated < total:
        current = min(batch_size, total - generated)
        gumbel = rng.gumbel(loc=0.0, scale=1.0, size=(current, MAX_NUMBER)).astype(np.float32)
        keyed = gumbel + log_weights.astype(np.float32)
        chosen_idx = np.argpartition(keyed, -PICK_COUNT, axis=1)[:, -PICK_COUNT:]
        combos = np.sort(numbers[chosen_idx], axis=1).astype(np.int16)

        ens = np.mean(state.ensemble[combos], axis=1)
        fourier = np.mean(state.fourier[combos], axis=1)
        bayes = np.mean(state.bayes[combos], axis=1)
        xgb_raw = np.mean(state.xgb_raw[combos], axis=1)
        xgb_contrast = np.mean(state.xgb_contrast[combos], axis=1)
        span = (np.max(combos, axis=1) - np.min(combos, axis=1)) / 55.0
        parity_balance = 1.0 - np.abs(np.sum((combos % 2) == 0, axis=1) - 3.0) / 3.0
        confidence = (
            0.36 * ens
            + 0.27 * xgb_contrast
            + 0.16 * bayes
            + 0.12 * fourier
            + 0.05 * span
            + 0.04 * parity_balance
        ) * 100.0

        keep_n = min(200, current)
        idx = np.argpartition(confidence, -keep_n)[-keep_n:]
        for i in idx:
            key = tuple(int(x) for x in combos[i])
            item = {
                "numbers": list(key),
                "confidence": float(confidence[i]),
                "ensemble": float(ens[i]),
                "xgboost_raw_mean": float(xgb_raw[i]),
                "xgboost_contrast_mean": float(xgb_contrast[i]),
                "bayes_mean": float(bayes[i]),
                "fourier_mean": float(fourier[i]),
            }
            if key not in top_records or item["confidence"] > top_records[key]["confidence"]:
                top_records[key] = item
        if len(top_records) > 5000:
            top_records = dict(sorted(top_records.items(), key=lambda kv: kv[1]["confidence"], reverse=True)[:2000])
        generated += current
        print(f"Monte Carlo vectorizado: {generated:,}/{total:,}", end="\r")

    print()
    ranked = sorted(top_records.values(), key=lambda x: x["confidence"], reverse=True)
    return ranked


def run_final_prediction(draws: Sequence[Draw], prior: np.ndarray, total_mc: int, batch_size: int) -> Tuple[ComponentState, List[Dict[str, float | List[int]]], float]:
    model = train_gpu_calibrated_xgb(draws, prior, len(draws))
    window = draws[-WINDOW_SIZE:]
    state = build_component_state(window, prior, model)
    ranked = generate_mc_combinations(state, total_mc, batch_size)
    max_conf = float(ranked[0]["confidence"]) if ranked else 0.0
    top = [item for item in ranked if float(item["confidence"]) >= CONFIDENCE_THRESHOLD][:10]
    return state, top, max_conf


def write_resultados(result: Dict) -> None:
    Path("resultados.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


def auto_git_push() -> None:
    os.system("git add resultados.json")
    os.system('git commit -m "Update predictions"')
    os.system("git push origin main")


def crunch(historial_path: str, total_mc: int, batch_size: int, auto_git: bool) -> Dict:
    draws = load_historial(historial_path)
    prior = static_prior(draws)
    hindsight_log, _ = hindsight_attribution(draws, prior)
    final_state, top_combinations, max_confidence = run_final_prediction(draws, prior, total_mc, batch_size)
    result = {
        "last_update": datetime.now(timezone.utc).isoformat(),
        "drift_detected": bool(final_state.drift_detected),
        "hindsight_log": hindsight_log,
        "max_confidence_found": round(float(max_confidence), 4),
        "top_combinations": [
            {
                "numbers": item["numbers"],
                "confidence": round(float(item["confidence"]), 4),
                "xgboost_raw_mean": round(float(item["xgboost_raw_mean"]), 8),
                "xgboost_contrast_mean": round(float(item["xgboost_contrast_mean"]), 6),
                "bayes_mean": round(float(item["bayes_mean"]), 6),
                "fourier_mean": round(float(item["fourier_mean"]), 6),
            }
            for item in top_combinations
        ],
    }
    if not top_combinations:
        result["capital_preservation"] = True
        result["stop_loss_reason"] = f"No hubo combinaciones con confianza >= {CONFIDENCE_THRESHOLD:.0f}%"
    else:
        result["capital_preservation"] = False
    write_resultados(result)
    if auto_git:
        auto_git_push()
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Procesador local GPU para historial.csv")
    parser.add_argument("--csv", default="historial.csv", help="Ruta del CSV. Default: historial.csv")
    parser.add_argument("--mc", type=int, default=MC_COMBINATIONS, help="Combinaciones Monte Carlo. Default: 1,000,000")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE, help="Tamaño de lote NumPy. Default: 100,000")
    parser.add_argument("--no-git", action="store_true", help="Desactiva git add/commit/push automático")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = crunch(args.csv, args.mc, args.batch_size, auto_git=not args.no_git)
    print(json.dumps({
        "drift_detected": result["drift_detected"],
        "max_confidence_found": result["max_confidence_found"],
        "top_count": len(result["top_combinations"]),
        "capital_preservation": result["capital_preservation"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
