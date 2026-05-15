#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
local_cruncher.py

Sistema local interactivo para generar resultados.json desde historial.csv.
Diseñado para ejecución en Windows/PowerShell con Python local, RAM disponible y GPU NVIDIA.
La web de Vercel solo consume resultados.json como archivo estático.
"""

from __future__ import annotations

import importlib.util
import json
import math
import os
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
mean_squared_error = None

MAX_NUMBER = 56
PICK_COUNT = 6
WINDOW_SIZE = 120
DRIFT_WINDOW = 15
MC_COMBINATIONS = 1_000_000
BATCH_SIZE = 100_000
CONFIDENCE_THRESHOLD = 70.0
DRIFT_KL_THRESHOLD = 0.18
RANDOM_SEED = 73073
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
    fourier: object
    fourier_period: object
    bayes: object
    xgb_raw: object
    xgb_contrast: object
    ensemble: object
    drift_detected: bool
    kl_divergence: float
    entropy_recent: float
    entropy_window: float


@dataclass
class CrunchSession:
    draws: Optional[List[Draw]] = None
    prior: Optional[object] = None
    hindsight_log: str = ""
    final_state: Optional[ComponentState] = None
    top_combinations: Optional[List[Dict]] = None
    max_confidence_found: float = 0.0


def dependency_exists(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def ensure_dependencies() -> None:
    missing = [
        (module_name, package_name)
        for module_name, package_name in REQUIRED_LIBS
        if not dependency_exists(module_name)
    ]

    if missing:
        print("Instalando dependencias necesarias para el hardware, por favor espere...")

    for _, package_name in missing:
        subprocess.check_call(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                package_name,
                "--quiet",
                "--disable-pip-version-check",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    import_runtime_libraries()


def import_runtime_libraries() -> None:
    global pd, np, rfft, rfftfreq, XGBClassifier, CalibratedClassifierCV, mean_squared_error

    import pandas as _pd
    import numpy as _np
    from scipy.fft import rfft as _rfft
    from scipy.fft import rfftfreq as _rfftfreq
    from sklearn.calibration import CalibratedClassifierCV as _CalibratedClassifierCV
    from sklearn.metrics import mean_squared_error as _mean_squared_error
    from xgboost import XGBClassifier as _XGBClassifier

    pd = _pd
    np = _np
    rfft = _rfft
    rfftfreq = _rfftfreq
    XGBClassifier = _XGBClassifier
    CalibratedClassifierCV = _CalibratedClassifierCV
    mean_squared_error = _mean_squared_error


def clear_screen() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def pause() -> None:
    input("\nPresiona ENTER para continuar...")


def print_box(lines: Sequence[str]) -> None:
    width = max(len(line) for line in lines) + 4
    print("╔" + "═" * width + "╗")
    for line in lines:
        print("║  " + line.ljust(width - 2) + "║")
    print("╚" + "═" * width + "╝")


def print_menu() -> None:
    clear_screen()
    print_box(
        [
            "MELATE LOCAL CRUNCHER · CUDA RTX 4060",
            "Fourier + Bayes Sigmoide + XGBoost + Monte Carlo",
            "",
            "[1] Cargar Historial y Ejecutar Ingeniería Inversa",
            "[2] Lanzar Simulación Monte Carlo (1,000,000 combinaciones)",
            "[3] Exportar a la Web y Sincronizar con Vercel",
            "[4] Salir del Sistema",
        ]
    )


def format_percent(value: float) -> str:
    return f"{value:.2f}%"


def parse_int(value) -> Optional[int]:
    try:
        if pd.isna(value):
            return None
        return int(float(str(value).strip()))
    except Exception:
        return None


def detect_csv_columns(df) -> Tuple[List[str], Optional[str], Optional[str], Optional[str]]:
    cols = list(df.columns)
    lower = {str(col).lower().strip(): col for col in cols}

    candidate_groups = [
        ["n1", "n2", "n3", "n4", "n5", "n6"],
        ["num1", "num2", "num3", "num4", "num5", "num6"],
        ["numero1", "numero2", "numero3", "numero4", "numero5", "numero6"],
        ["bola1", "bola2", "bola3", "bola4", "bola5", "bola6"],
        ["b1", "b2", "b3", "b4", "b5", "b6"],
    ]

    natural_cols: List[str] = []

    for group in candidate_groups:
        if all(name in lower for name in group):
            natural_cols = [lower[name] for name in group]
            break

    if not natural_cols:
        numeric_like = []
        for col in cols:
            parsed = pd.to_numeric(df[col], errors="coerce")
            valid_ratio = parsed.notna().mean()
            in_range_ratio = parsed.between(1, MAX_NUMBER).mean()
            if valid_ratio > 0.80 and in_range_ratio > 0.55:
                numeric_like.append(col)

        if len(numeric_like) < PICK_COUNT:
            raise ValueError(
                "No pude detectar las 6 columnas de números. "
                "Usa encabezados como n1,n2,n3,n4,n5,n6."
            )

        natural_cols = numeric_like[:PICK_COUNT]

    additional_col = None
    for name in ["adicional", "additional", "bonus", "extra", "num_adicional", "numero_adicional"]:
        if name in lower:
            additional_col = lower[name]
            break

    draw_col = None
    for name in ["sorteo", "draw", "draw_id", "draw_number", "concurso", "id"]:
        if name in lower:
            draw_col = lower[name]
            break

    date_col = None
    for name in ["fecha", "date", "draw_date", "f_sorteo"]:
        if name in lower:
            date_col = lower[name]
            break

    return natural_cols, additional_col, draw_col, date_col


def sort_draws(draws: List[Draw]) -> List[Draw]:
    numeric_ids = [parse_int(draw.draw_id) for draw in draws]

    if all(item is not None for item in numeric_ids) and len(set(numeric_ids)) > 1:
        ordered = [draw for _, draw in sorted(zip(numeric_ids, draws), key=lambda x: x[0])]
    elif all(draw.date for draw in draws):
        dates = pd.to_datetime([draw.date for draw in draws], errors="coerce", dayfirst=True)
        if dates.notna().mean() > 0.8:
            ordered = [draw for _, draw in sorted(zip(dates, draws), key=lambda x: x[0])]
        else:
            ordered = draws
    else:
        ordered = draws

    return [
        Draw(
            index=i,
            draw_id=draw.draw_id,
            date=draw.date,
            numbers=draw.numbers,
            additional=draw.additional,
        )
        for i, draw in enumerate(ordered)
    ]


def load_historial(path: str = "historial.csv") -> List[Draw]:
    csv_path = Path(path)

    if not csv_path.exists():
        raise FileNotFoundError(f"No existe el archivo: {csv_path.resolve()}")

    df = pd.read_csv(csv_path)
    natural_cols, additional_col, draw_col, date_col = detect_csv_columns(df)

    draws: List[Draw] = []

    for _, row in df.iterrows():
        nums = []

        for col in natural_cols:
            number = parse_int(row[col])
            if number is not None and 1 <= number <= MAX_NUMBER:
                nums.append(number)

        nums = sorted(set(nums))

        if len(nums) != PICK_COUNT:
            continue

        additional = None
        if additional_col:
            add = parse_int(row[additional_col])
            if add is not None and 1 <= add <= MAX_NUMBER:
                additional = add

        draw_id = str(row[draw_col]) if draw_col else str(len(draws))
        date = str(row[date_col]) if date_col else None

        draws.append(
            Draw(
                index=len(draws),
                draw_id=draw_id,
                date=date,
                numbers=tuple(nums),
                additional=additional,
            )
        )

    draws = sort_draws(draws)

    if len(draws) < WINDOW_SIZE + 1:
        raise ValueError(
            f"Se requieren al menos {WINDOW_SIZE + 1} sorteos válidos. Detectados: {len(draws)}"
        )

    print(f"\nHistorial cargado correctamente: {len(draws)} sorteos válidos.")
    print(f"Columnas naturales detectadas: {natural_cols}")

    return draws


def binary_matrix(draws: Sequence[Draw]):
    matrix = np.zeros((len(draws), MAX_NUMBER + 1), dtype=np.float64)

    for i, draw in enumerate(draws):
        matrix[i, list(draw.numbers)] = 1.0

    return matrix


def counts_from_draws(draws: Sequence[Draw]):
    if not draws:
        return np.zeros(MAX_NUMBER + 1, dtype=np.float64)
    return np.sum(binary_matrix(draws), axis=0)


def probability_from_counts(counts):
    probabilities = np.zeros(MAX_NUMBER + 1, dtype=np.float64)
    total = float(np.sum(counts[1:]))
    if total > 0:
        probabilities[1:] = counts[1:] / total
    return probabilities


def static_prior(draws: Sequence[Draw]):
    return probability_from_counts(counts_from_draws(draws))


def minmax01(values):
    arr = np.asarray(values, dtype=np.float64)
    out = np.zeros_like(arr, dtype=np.float64)
    valid = np.nan_to_num(arr[1:], nan=0.0, posinf=0.0, neginf=0.0)
    low = float(np.min(valid))
    high = float(np.max(valid))
    out[1:] = 0.5 if high - low <= EPS else (valid - low) / (high - low)
    return out


def sigmoid_wear(impacts: float) -> float:
    return SIGMOID["L"] + (SIGMOID["K"] - SIGMOID["L"]) / (
        1.0 + math.exp(-SIGMOID["r"] * (impacts - SIGMOID["n0"]))
    )


def fft_microcycle_scores(window: Sequence[Draw]):
    matrix = binary_matrix(window)[:, 1:]
    centered = matrix - np.mean(matrix, axis=0, keepdims=True)

    spectrum = rfft(centered, axis=0)
    power = np.abs(spectrum) ** 2
    freqs = rfftfreq(matrix.shape[0], d=1.0)

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
        frequency = float(usable_freqs[dominant_idx[i]])
        periods[i + 1] = 1.0 / frequency if frequency > EPS else 0.0

    return scores, periods


def bayesian_sigmoid_posterior(window: Sequence[Draw], prior):
    counts = counts_from_draws(window)
    wear = np.zeros(MAX_NUMBER + 1, dtype=np.float64)

    for number in range(1, MAX_NUMBER + 1):
        wear[number] = sigmoid_wear(float(counts[number]))

    wear_contrast = minmax01(wear)
    freq_contrast = minmax01(counts)

    posterior_raw = np.zeros(MAX_NUMBER + 1, dtype=np.float64)
    posterior_raw[1:] = (
        prior[1:]
        * (1.0 + 2.4 * wear_contrast[1:])
        * (1.0 + 1.15 * freq_contrast[1:])
    )

    posterior = probability_from_counts(posterior_raw)
    return minmax01(posterior)


def shannon_entropy(probabilities) -> float:
    p = probabilities[1:]
    p = p[p > 0]
    if len(p) == 0:
        return 0.0
    return float(-np.sum(p * np.log2(p)))


def kl_divergence(p, q) -> float:
    pp = p[1:]
    qq = q[1:]
    mask = pp > 0
    if not np.any(mask):
        return 0.0
    return float(np.sum(pp[mask] * np.log(pp[mask] / np.maximum(qq[mask], EPS))))


def drift_detection(window: Sequence[Draw]):
    p_window = probability_from_counts(counts_from_draws(window))
    p_recent = probability_from_counts(counts_from_draws(window[-DRIFT_WINDOW:]))
    entropy_window = shannon_entropy(p_window)
    entropy_recent = shannon_entropy(p_recent)
    kl = kl_divergence(p_recent, p_window)
    return bool(kl >= DRIFT_KL_THRESHOLD), kl, entropy_recent, entropy_window


def last_seen_gaps(window: Sequence[Draw]):
    gaps = np.full(MAX_NUMBER + 1, len(window) + 1, dtype=np.float64)
    for gap, draw in enumerate(reversed(window)):
        for number in draw.numbers:
            if gaps[number] == len(window) + 1:
                gaps[number] = float(gap)
    return gaps


def rolling_freq(matrix, k: int):
    if matrix.shape[0] == 0:
        return np.zeros(MAX_NUMBER + 1, dtype=np.float64)
    return np.mean(matrix[-min(k, matrix.shape[0]) :], axis=0)


def feature_matrix(window: Sequence[Draw], prior, fourier, bayes):
    matrix = binary_matrix(window)
    gaps = last_seen_gaps(window)
    numbers = np.arange(1, MAX_NUMBER + 1, dtype=np.float64)

    odd = (numbers % 2).astype(np.float64)
    decade = np.floor((numbers - 1) / 10.0) / 5.0
    side = (numbers > 28).astype(np.float64)
    gap_scaled = np.minimum(gaps[1:], WINDOW_SIZE) / WINDOW_SIZE
    recency = 1.0 / (1.0 + gaps[1:])

    return np.column_stack(
        [
            numbers / MAX_NUMBER,
            prior[1:],
            rolling_freq(matrix, 15)[1:],
            rolling_freq(matrix, 30)[1:],
            rolling_freq(matrix, 60)[1:],
            rolling_freq(matrix, WINDOW_SIZE)[1:],
            gap_scaled,
            recency,
            fourier[1:],
            bayes[1:],
            odd,
            decade,
            side,
        ]
    ).astype(np.float32)


def build_training_dataset(draws: Sequence[Draw], prior, end_idx: int):
    start_idx = max(1, end_idx - WINDOW_SIZE)
    x_parts = []
    y_parts = []

    for target_idx in range(start_idx, end_idx):
        window = draws[max(0, target_idx - WINDOW_SIZE) : target_idx]
        if len(window) < 40:
            continue

        fourier, _ = fft_microcycle_scores(window)
        bayes = bayesian_sigmoid_posterior(window, prior)
        x_parts.append(feature_matrix(window, prior, fourier, bayes))

        y = np.zeros(MAX_NUMBER, dtype=np.int32)
        for number in draws[target_idx].numbers:
            y[number - 1] = 1
        y_parts.append(y)

    if not x_parts:
        raise ValueError("No se pudo construir dataset de entrenamiento con la ventana actual.")

    return np.vstack(x_parts), np.concatenate(y_parts)


def make_gpu_xgb():
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


def make_calibrator(base_model):
    try:
        return CalibratedClassifierCV(estimator=base_model, method="sigmoid", cv=3)
    except TypeError:
        return CalibratedClassifierCV(base_estimator=base_model, method="sigmoid", cv=3)


def train_gpu_calibrated_xgb(draws: Sequence[Draw], prior, end_idx: int):
    x, y = build_training_dataset(draws, prior, end_idx)
    positives = int(np.sum(y))
    if positives < 18:
        raise ValueError(f"Insuficientes positivos para calibración: {positives}")

    print("\nEntrenando XGBoost CUDA calibrado...")
    print(f"Matriz X: {x.shape} | Positivos: {positives}")

    model = make_calibrator(make_gpu_xgb())
    model.fit(x, y)
    return model


def build_component_state(window: Sequence[Draw], prior, model) -> ComponentState:
    fourier, periods = fft_microcycle_scores(window)
    bayes = bayesian_sigmoid_posterior(window, prior)
    x_live = feature_matrix(window, prior, fourier, bayes)

    xgb_raw = np.zeros(MAX_NUMBER + 1, dtype=np.float64)
    xgb_raw[1:] = model.predict_proba(x_live)[:, 1]
    xgb_contrast = minmax01(xgb_raw)

    ensemble = np.zeros(MAX_NUMBER + 1, dtype=np.float64)
    ensemble[1:] = (
        ENSEMBLE_WEIGHTS["fourier"] * fourier[1:]
        + ENSEMBLE_WEIGHTS["bayes"] * bayes[1:]
        + ENSEMBLE_WEIGHTS["xgboost"] * xgb_contrast[1:]
    )
    ensemble = minmax01(ensemble)

    drift_detected, kl, entropy_recent, entropy_window = drift_detection(window)

    return ComponentState(
        fourier=fourier,
        fourier_period=periods,
        bayes=bayes,
        xgb_raw=xgb_raw,
        xgb_contrast=xgb_contrast,
        ensemble=ensemble,
        drift_detected=drift_detected,
        kl_divergence=kl,
        entropy_recent=entropy_recent,
        entropy_window=entropy_window,
    )


def component_winner(state: ComponentState, number: int):
    components = {
        "Fourier": float(state.fourier[number]),
        "Bayes": float(state.bayes[number]),
        "XGBoost": float(state.xgb_contrast[number]),
    }
    return max(components.items(), key=lambda item: item[1])


def rank_of_number(scores, number: int) -> int:
    order = np.argsort(scores[1:])[::-1] + 1
    position = np.where(order == number)[0]
    return int(position[0] + 1) if len(position) else MAX_NUMBER


def hindsight_attribution(draws: Sequence[Draw], prior):
    target = draws[-1]
    end_idx = len(draws) - 1
    model = train_gpu_calibrated_xgb(draws, prior, end_idx)
    window = draws[max(0, end_idx - WINDOW_SIZE) : end_idx]
    state = build_component_state(window, prior, model)

    lines = [
        f"Auditoría inversa del sorteo {target.draw_id} ({target.date or 'sin fecha'})",
        f"Combinación real: {' '.join(map(str, target.numbers))}",
        f"Ventana usada antes del sorteo: {len(window)} sorteos",
        f"Drift detectado: {state.drift_detected} | KL={state.kl_divergence:.6f} | H15={state.entropy_recent:.4f} | H120={state.entropy_window:.4f}",
    ]

    tracked_scores = []

    for number in target.numbers:
        winner, winner_score = component_winner(state, number)
        rank = rank_of_number(state.ensemble, number)
        tracked = rank <= 12
        tracked_scores.append(float(state.ensemble[number]))
        lines.append(
            f"Número {number}: ganador_componente={winner}({winner_score:.4f}); "
            f"Fourier={state.fourier[number]:.4f}; "
            f"Bayes={state.bayes[number]:.4f}; "
            f"XGBoostRaw={state.xgb_raw[number]:.6f}; "
            f"XGBoostContrast={state.xgb_contrast[number]:.4f}; "
            f"Ensemble={state.ensemble[number]:.4f}; "
            f"Rank={rank}/56; "
            f"PeriodoFFT={state.fourier_period[number]:.2f}; "
            f"Resultado={'RASTREADO' if tracked else 'NO_RASTREADO'}"
        )

    route_confidence = float(np.mean(tracked_scores) * 100.0)
    lines.append(f"Confianza de ruta inversa: {route_confidence:.2f}%")
    return "\n".join(lines), state


def structure_score(combos):
    combos = np.asarray(combos, dtype=np.float64)
    even_count = np.sum((combos % 2) == 0, axis=1)
    low_count = np.sum(combos <= 28, axis=1)
    sums = np.sum(combos, axis=1)
    span = (np.max(combos, axis=1) - np.min(combos, axis=1)) / 55.0
    consecutive = np.sum(np.diff(combos, axis=1) == 1, axis=1)
    decades = np.array([len(set(((row - 1) // 10).astype(int))) for row in combos], dtype=np.float64)

    score = (
        (1.0 - np.abs(even_count - 3) / 3.0) * 0.22
        + (1.0 - np.abs(low_count - 3) / 3.0) * 0.20
        + (decades / 6.0) * 0.20
        + (1.0 - np.minimum(consecutive, 4) / 4.0) * 0.13
        + np.where((sums >= 110) & (sums <= 240), 1.0, 0.55) * 0.15
        + span * 0.10
    )

    return np.clip(score, 0.0, 1.0)


def generate_mc_combinations(state: ComponentState, total: int = MC_COMBINATIONS, batch_size: int = BATCH_SIZE):
    rng = np.random.default_rng(RANDOM_SEED)
    numbers = np.arange(1, MAX_NUMBER + 1, dtype=np.int16)
    weights = np.maximum(state.ensemble[1:], EPS)
    weights = weights / np.sum(weights)
    log_weights = np.log(weights).reshape(1, -1).astype(np.float32)

    top_records: Dict[Tuple[int, ...], Dict] = {}
    generated = 0

    while generated < total:
        current = min(batch_size, total - generated)
        gumbel = rng.gumbel(loc=0.0, scale=1.0, size=(current, MAX_NUMBER)).astype(np.float32)
        keyed = gumbel + log_weights
        chosen_idx = np.argpartition(keyed, -PICK_COUNT, axis=1)[:, -PICK_COUNT:]
        combos = np.sort(numbers[chosen_idx], axis=1).astype(np.int16)

        ensemble_score = np.mean(state.ensemble[combos], axis=1)
        fourier_score = np.mean(state.fourier[combos], axis=1)
        bayes_score = np.mean(state.bayes[combos], axis=1)
        xgb_raw_score = np.mean(state.xgb_raw[combos], axis=1)
        xgb_contrast_score = np.mean(state.xgb_contrast[combos], axis=1)
        structural_score = structure_score(combos)

        confidence = (
            0.34 * ensemble_score
            + 0.28 * xgb_contrast_score
            + 0.17 * bayes_score
            + 0.12 * fourier_score
            + 0.09 * structural_score
        ) * 100.0

        keep_n = min(300, current)
        keep_idx = np.argpartition(confidence, -keep_n)[-keep_n:]

        for idx in keep_idx:
            key = tuple(int(x) for x in combos[idx])
            item = {
                "numbers": list(key),
                "confidence": float(confidence[idx]),
                "ensemble": float(ensemble_score[idx]),
                "xgboost_raw_mean": float(xgb_raw_score[idx]),
                "xgboost_contrast_mean": float(xgb_contrast_score[idx]),
                "bayes_mean": float(bayes_score[idx]),
                "fourier_mean": float(fourier_score[idx]),
                "structure_mean": float(structural_score[idx]),
            }
            if key not in top_records or item["confidence"] > top_records[key]["confidence"]:
                top_records[key] = item

        if len(top_records) > 6000:
            top_records = dict(sorted(top_records.items(), key=lambda pair: pair[1]["confidence"], reverse=True)[:2500])

        generated += current
        print(f"Monte Carlo vectorizado: {generated:,}/{total:,}", end="\r")

    print()
    return sorted(top_records.values(), key=lambda item: item["confidence"], reverse=True)


def run_final_simulation(draws: Sequence[Draw], prior, total_mc: int = MC_COMBINATIONS):
    model = train_gpu_calibrated_xgb(draws, prior, len(draws))
    window = draws[-WINDOW_SIZE:]
    state = build_component_state(window, prior, model)
    ranked = generate_mc_combinations(state=state, total=total_mc, batch_size=BATCH_SIZE)
    max_confidence = float(ranked[0]["confidence"]) if ranked else 0.0
    top = [item for item in ranked if float(item["confidence"]) >= CONFIDENCE_THRESHOLD][:10]
    return state, top, max_confidence


def build_result_json(session: CrunchSession) -> Dict:
    if session.final_state is None:
        raise RuntimeError("No hay simulación final en memoria. Ejecuta la opción [2] primero.")

    top_combinations = session.top_combinations or []

    result = {
        "last_update": datetime.now(timezone.utc).isoformat(),
        "drift_detected": bool(session.final_state.drift_detected),
        "hindsight_log": session.hindsight_log or "Sin auditoría ejecutada.",
        "max_confidence_found": round(float(session.max_confidence_found), 4),
        "number_scores": {
            str(number): round(float(session.final_state.ensemble[number] * 100.0), 4)
            for number in range(1, MAX_NUMBER + 1)
        },
        "top_combinations": [
            {
                "numbers": item["numbers"],
                "confidence": round(float(item["confidence"]), 4),
                "xgboost_raw_mean": round(float(item["xgboost_raw_mean"]), 8),
                "xgboost_contrast_mean": round(float(item["xgboost_contrast_mean"]), 6),
                "bayes_mean": round(float(item["bayes_mean"]), 6),
                "fourier_mean": round(float(item["fourier_mean"]), 6),
                "structure_mean": round(float(item["structure_mean"]), 6),
            }
            for item in top_combinations
        ],
    }

    if not top_combinations:
        result["capital_preservation"] = True
        result["stop_loss_reason"] = f"No hubo combinaciones con confianza >= {CONFIDENCE_THRESHOLD:.0f}%"
    else:
        result["capital_preservation"] = False

    return result


def write_resultados_json(session: CrunchSession) -> None:
    result = build_result_json(session)
    Path("resultados.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nArchivo resultados.json generado correctamente.")


def git_sync() -> None:
    print("\nSincronizando con Git...")
    os.system("git add resultados.json")
    os.system('git commit -m "Update predictions"')
    os.system("git push origin main")


def ensure_session_loaded(session: CrunchSession) -> None:
    if session.draws is None:
        session.draws = load_historial("historial.csv")
        session.prior = static_prior(session.draws)


def action_hindsight(session: CrunchSession) -> None:
    clear_screen()
    print_box(["[1] INGENIERÍA INVERSA", "Cargando historial.csv y analizando último sorteo real"])
    ensure_session_loaded(session)
    assert session.draws is not None
    assert session.prior is not None
    log, _ = hindsight_attribution(session.draws, session.prior)
    session.hindsight_log = log
    print("\n" + log)


def action_monte_carlo(session: CrunchSession) -> None:
    clear_screen()
    print_box(["[2] MONTE CARLO MASIVO", "Entrenamiento CUDA + 1,000,000 combinaciones vectorizadas"])
    ensure_session_loaded(session)
    assert session.draws is not None
    assert session.prior is not None
    state, top, max_confidence = run_final_simulation(session.draws, session.prior, MC_COMBINATIONS)
    session.final_state = state
    session.top_combinations = top
    session.max_confidence_found = max_confidence

    print(f"\nDrift detectado: {state.drift_detected}")
    print(f"KL: {state.kl_divergence:.6f}")
    print(f"Confianza máxima encontrada: {format_percent(max_confidence)}")

    if not top:
        print("\nSTOP-LOSS ACTIVO: No hubo combinaciones >= 70%.")
        return

    print("\nTOP COMBINACIONES OPERATIVAS:")
    for i, item in enumerate(top, start=1):
        print(
            f"{i:02d}. {item['numbers']} | "
            f"Confianza={item['confidence']:.2f}% | "
            f"XGB={item['xgboost_contrast_mean']:.4f} | "
            f"Bayes={item['bayes_mean']:.4f} | "
            f"Fourier={item['fourier_mean']:.4f}"
        )


def action_export(session: CrunchSession) -> None:
    clear_screen()
    print_box(["[3] EXPORTAR A WEB", "Generando resultados.json y sincronizando Git/Vercel"])
    if session.final_state is None:
        print("\nNo hay simulación en memoria. Ejecutando opción [2] automáticamente...")
        action_monte_carlo(session)
    write_resultados_json(session)
    git_sync()


def run_menu() -> None:
    session = CrunchSession()

    while True:
        print_menu()
        choice = input("\nSelecciona una opción: ").strip()

        try:
            if choice == "1":
                action_hindsight(session)
                pause()
            elif choice == "2":
                action_monte_carlo(session)
                pause()
            elif choice == "3":
                action_export(session)
                pause()
            elif choice == "4":
                print("\nSaliendo del sistema.")
                break
            else:
                print("\nOpción inválida.")
                pause()
        except KeyboardInterrupt:
            print("\nProceso interrumpido por el usuario.")
            pause()
        except Exception as exc:
            print("\nERROR:")
            print(str(exc))
            pause()


if __name__ == "__main__":
    ensure_dependencies()
    run_menu()
