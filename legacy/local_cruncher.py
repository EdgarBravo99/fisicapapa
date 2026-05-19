#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
local_cruncher.py

Motor local para Melate Pro:
- Lee historial.csv.
- Auto-instala dependencias.
- Ejecuta Walk-Forward corto, Hindsight, XGBoost CUDA calibrado y Monte Carlo vectorizado.
- Genera resultados.json enriquecido para que la web solo asimile resultados.
- Sincroniza resultados.json con Git/Vercel cuando Git está disponible.
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
CONFIDENCE_THRESHOLD = 70.0
DRIFT_KL_THRESHOLD = 0.18
RANDOM_SEED = 73073
EPS = 1e-12

INITIAL_MC_COMBINATIONS = 1_000_000
MAX_MC_COMBINATIONS = 10_000_000
MC_BATCH_SIZE = 100_000
TARGET_OPERATIONAL_COMBOS = 10
WALK_FORWARD_STEPS = 36

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
class WindowContext:
    start_idx: int
    end_idx: int
    rows: Sequence[Draw]
    fourier: object
    fourier_period: object
    bayes: object


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
    all_matrix: Optional[object] = None
    hindsight_context: Optional[WindowContext] = None
    current_context: Optional[WindowContext] = None
    hindsight_log: str = ""
    procedure_log: str = ""
    walk_forward: Optional[Dict] = None
    final_state: Optional[ComponentState] = None
    top_combinations: Optional[List[Dict]] = None
    generator_pool: Optional[List[Dict]] = None
    max_confidence_found: float = 0.0
    total_mc_evaluated: int = 0
    last_export_path: str = "resultados.json"


def dependency_exists(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def ensure_dependencies() -> None:
    missing = [(m, p) for m, p in REQUIRED_LIBS if not dependency_exists(m)]
    if missing:
        print("Instalando dependencias necesarias para el hardware, por favor espere...")
    for _, package_name in missing:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", package_name, "--quiet", "--disable-pip-version-check"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    import_runtime_libraries()


def import_runtime_libraries() -> None:
    global pd, np, rfft, rfftfreq, XGBClassifier, CalibratedClassifierCV
    import pandas as _pd
    import numpy as _np
    from scipy.fft import rfft as _rfft
    from scipy.fft import rfftfreq as _rfftfreq
    from sklearn.calibration import CalibratedClassifierCV as _CalibratedClassifierCV
    from xgboost import XGBClassifier as _XGBClassifier
    pd = _pd
    np = _np
    rfft = _rfft
    rfftfreq = _rfftfreq
    XGBClassifier = _XGBClassifier
    CalibratedClassifierCV = _CalibratedClassifierCV


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
    print_box([
        "MELATE LOCAL CRUNCHER · PIPELINE CUDA",
        "Python genera combinaciones, scores, Walk-Forward y explicación; la web solo asimila.",
        "",
        "[1] Ejecutar Pipeline Cuantitativo Completo",
        "[2] Solo Ingeniería Inversa del Último Sorteo",
        "[3] Solo Simulación Monte Carlo Extendida",
        "[4] Exportar/Sincronizar resultados.json",
        "[5] Salir del Sistema",
    ])


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
    groups = [
        ["n1", "n2", "n3", "n4", "n5", "n6"],
        ["num1", "num2", "num3", "num4", "num5", "num6"],
        ["numero1", "numero2", "numero3", "numero4", "numero5", "numero6"],
        ["bola1", "bola2", "bola3", "bola4", "bola5", "bola6"],
        ["b1", "b2", "b3", "b4", "b5", "b6"],
    ]
    natural_cols: List[str] = []
    for group in groups:
        if all(name in lower for name in group):
            natural_cols = [lower[name] for name in group]
            break
    if not natural_cols:
        numeric_like = []
        for col in cols:
            parsed = pd.to_numeric(df[col], errors="coerce")
            if parsed.notna().mean() > 0.80 and parsed.between(1, MAX_NUMBER).mean() > 0.55:
                numeric_like.append(col)
        if len(numeric_like) < PICK_COUNT:
            raise ValueError("No pude detectar las 6 columnas de números. Usa encabezados n1,n2,n3,n4,n5,n6.")
        natural_cols = numeric_like[:PICK_COUNT]
    additional_col = next((lower[n] for n in ["adicional", "additional", "bonus", "extra", "num_adicional", "numero_adicional"] if n in lower), None)
    draw_col = next((lower[n] for n in ["sorteo", "draw", "draw_id", "draw_number", "concurso", "id"] if n in lower), None)
    date_col = next((lower[n] for n in ["fecha", "date", "draw_date", "f_sorteo"] if n in lower), None)
    return natural_cols, additional_col, draw_col, date_col


def sort_draws(draws: List[Draw]) -> List[Draw]:
    numeric_ids = [parse_int(draw.draw_id) for draw in draws]
    if all(item is not None for item in numeric_ids) and len(set(numeric_ids)) > 1:
        ordered = [draw for _, draw in sorted(zip(numeric_ids, draws), key=lambda x: x[0])]
    elif all(draw.date for draw in draws):
        dates = pd.to_datetime([draw.date for draw in draws], errors="coerce", dayfirst=True)
        ordered = [draw for _, draw in sorted(zip(dates, draws), key=lambda x: x[0])] if dates.notna().mean() > 0.8 else draws
    else:
        ordered = draws
    return [Draw(i, d.draw_id, d.date, d.numbers, d.additional) for i, d in enumerate(ordered)]


def load_historial(path: str = "historial.csv") -> List[Draw]:
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"No existe el archivo: {csv_path.resolve()}")
    df = pd.read_csv(csv_path)
    natural_cols, additional_col, draw_col, date_col = detect_csv_columns(df)
    draws: List[Draw] = []
    for _, row in df.iterrows():
        nums = sorted({n for n in (parse_int(row[col]) for col in natural_cols) if n is not None and 1 <= n <= MAX_NUMBER})
        if len(nums) != PICK_COUNT:
            continue
        additional = None
        if additional_col:
            add = parse_int(row[additional_col])
            if add is not None and 1 <= add <= MAX_NUMBER:
                additional = add
        draw_id = str(row[draw_col]) if draw_col else str(len(draws))
        date = str(row[date_col]) if date_col else None
        draws.append(Draw(len(draws), draw_id, date, tuple(nums), additional))
    draws = sort_draws(draws)
    if len(draws) < WINDOW_SIZE + 1:
        raise ValueError(f"Se requieren al menos {WINDOW_SIZE + 1} sorteos válidos. Detectados: {len(draws)}")
    print(f"\nHistorial cargado correctamente: {len(draws)} sorteos válidos.")
    print(f"Columnas naturales detectadas: {natural_cols}")
    return draws


def binary_matrix(draws: Sequence[Draw]):
    matrix = np.zeros((len(draws), MAX_NUMBER + 1), dtype=np.float64)
    for i, draw in enumerate(draws):
        matrix[i, list(draw.numbers)] = 1.0
    return matrix


def counts_from_draws(draws: Sequence[Draw]):
    return np.sum(binary_matrix(draws), axis=0) if draws else np.zeros(MAX_NUMBER + 1, dtype=np.float64)


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
    return SIGMOID["L"] + (SIGMOID["K"] - SIGMOID["L"]) / (1.0 + math.exp(-SIGMOID["r"] * (impacts - SIGMOID["n0"])))


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
    posterior_raw[1:] = prior[1:] * (1.0 + 2.4 * wear_contrast[1:]) * (1.0 + 1.15 * freq_contrast[1:])
    posterior = probability_from_counts(posterior_raw)
    return minmax01(posterior)


def shannon_entropy(probabilities) -> float:
    p = probabilities[1:]
    p = p[p > 0]
    return 0.0 if len(p) == 0 else float(-np.sum(p * np.log2(p)))


def kl_divergence(p, q) -> float:
    pp = p[1:]
    qq = q[1:]
    mask = pp > 0
    return 0.0 if not np.any(mask) else float(np.sum(pp[mask] * np.log(pp[mask] / np.maximum(qq[mask], EPS))))


def drift_detection(window: Sequence[Draw]):
    p_window = probability_from_counts(counts_from_draws(window))
    p_recent = probability_from_counts(counts_from_draws(window[-DRIFT_WINDOW:]))
    entropy_window = shannon_entropy(p_window)
    entropy_recent = shannon_entropy(p_recent)
    kl = kl_divergence(p_recent, p_window)
    return bool(kl >= DRIFT_KL_THRESHOLD), kl, entropy_recent, entropy_window


def make_context(draws: Sequence[Draw], prior, start_idx: int, end_idx: int) -> WindowContext:
    rows = draws[start_idx:end_idx]
    fourier, periods = fft_microcycle_scores(rows)
    bayes = bayesian_sigmoid_posterior(rows, prior)
    return WindowContext(start_idx, end_idx, rows, fourier, periods, bayes)


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
    return np.column_stack([
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
    ]).astype(np.float32)


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


def build_component_state(context: WindowContext, prior, model) -> ComponentState:
    x_live = feature_matrix(context.rows, prior, context.fourier, context.bayes)
    xgb_raw = np.zeros(MAX_NUMBER + 1, dtype=np.float64)
    xgb_raw[1:] = model.predict_proba(x_live)[:, 1]
    xgb_contrast = minmax01(xgb_raw)
    ensemble = np.zeros(MAX_NUMBER + 1, dtype=np.float64)
    ensemble[1:] = ENSEMBLE_WEIGHTS["fourier"] * context.fourier[1:] + ENSEMBLE_WEIGHTS["bayes"] * context.bayes[1:] + ENSEMBLE_WEIGHTS["xgboost"] * xgb_contrast[1:]
    ensemble = minmax01(ensemble)
    drift_detected, kl, entropy_recent, entropy_window = drift_detection(context.rows)
    return ComponentState(context.fourier, context.fourier_period, context.bayes, xgb_raw, xgb_contrast, ensemble, drift_detected, kl, entropy_recent, entropy_window)


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


def score_combo_batch(state: ComponentState, combos):
    combos = np.asarray(combos, dtype=np.int16)
    ensemble_score = np.mean(state.ensemble[combos], axis=1)
    fourier_score = np.mean(state.fourier[combos], axis=1)
    bayes_score = np.mean(state.bayes[combos], axis=1)
    xgb_raw_score = np.mean(state.xgb_raw[combos], axis=1)
    xgb_contrast_score = np.mean(state.xgb_contrast[combos], axis=1)
    structural_score = structure_score(combos)
    confidence = (0.34 * ensemble_score + 0.28 * xgb_contrast_score + 0.17 * bayes_score + 0.12 * fourier_score + 0.09 * structural_score) * 100.0
    return confidence, ensemble_score, xgb_raw_score, xgb_contrast_score, bayes_score, fourier_score, structural_score


def generate_mc_combinations_until_target(state: ComponentState):
    rng = np.random.default_rng(RANDOM_SEED)
    numbers = np.arange(1, MAX_NUMBER + 1, dtype=np.int16)
    weights = np.maximum(state.ensemble[1:], EPS)
    weights = weights / np.sum(weights)
    log_weights = np.log(weights).reshape(1, -1).astype(np.float32)
    top_records: Dict[Tuple[int, ...], Dict] = {}
    generated = 0
    round_no = 0

    while generated < MAX_MC_COMBINATIONS:
        round_no += 1
        current = min(MC_BATCH_SIZE, MAX_MC_COMBINATIONS - generated)
        gumbel = rng.gumbel(loc=0.0, scale=1.0, size=(current, MAX_NUMBER)).astype(np.float32)
        keyed = gumbel + log_weights
        chosen_idx = np.argpartition(keyed, -PICK_COUNT, axis=1)[:, -PICK_COUNT:]
        combos = np.sort(numbers[chosen_idx], axis=1).astype(np.int16)
        confidence, ensemble_score, xgb_raw_score, xgb_contrast_score, bayes_score, fourier_score, structural_score = score_combo_batch(state, combos)
        keep_n = min(500, current)
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
                "source": "python_gpu_montecarlo",
            }
            if key not in top_records or item["confidence"] > top_records[key]["confidence"]:
                top_records[key] = item
        if len(top_records) > 8000:
            top_records = dict(sorted(top_records.items(), key=lambda pair: pair[1]["confidence"], reverse=True)[:3500])
        generated += current
        ranked_preview = sorted(top_records.values(), key=lambda item: item["confidence"], reverse=True)
        operational = [item for item in ranked_preview if item["confidence"] >= CONFIDENCE_THRESHOLD]
        print(f"Monte Carlo extendido: {generated:,}/{MAX_MC_COMBINATIONS:,} | operativas >=70: {len(operational)}/{TARGET_OPERATIONAL_COMBOS}", end="\r")
        if generated >= INITIAL_MC_COMBINATIONS and len(operational) >= TARGET_OPERATIONAL_COMBOS:
            break
    print()
    ranked = sorted(top_records.values(), key=lambda item: item["confidence"], reverse=True)
    return ranked, generated


def component_winner(state: ComponentState, number: int):
    components = {"Fourier": float(state.fourier[number]), "Bayes": float(state.bayes[number]), "XGBoost": float(state.xgb_contrast[number])}
    return max(components.items(), key=lambda item: item[1])


def rank_of_number(scores, number: int) -> int:
    order = np.argsort(scores[1:])[::-1] + 1
    position = np.where(order == number)[0]
    return int(position[0] + 1) if len(position) else MAX_NUMBER


def hindsight_attribution(draws: Sequence[Draw], prior, context: WindowContext):
    target = draws[-1]
    model = train_gpu_calibrated_xgb(draws, prior, len(draws) - 1)
    state = build_component_state(context, prior, model)
    lines = [
        f"Auditoría inversa del sorteo {target.draw_id} ({target.date or 'sin fecha'})",
        f"Combinación real: {' '.join(map(str, target.numbers))}",
        f"Ventana usada antes del sorteo: {len(context.rows)} sorteos",
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
            f"Fourier={state.fourier[number]:.4f}; Bayes={state.bayes[number]:.4f}; "
            f"XGBoostRaw={state.xgb_raw[number]:.6f}; XGBoostContrast={state.xgb_contrast[number]:.4f}; "
            f"Ensemble={state.ensemble[number]:.4f}; Rank={rank}/56; PeriodoFFT={state.fourier_period[number]:.2f}; "
            f"Resultado={'RASTREADO' if tracked else 'NO_RASTREADO'}"
        )
    route_confidence = float(np.mean(tracked_scores) * 100.0)
    lines.append(f"Confianza de ruta inversa: {route_confidence:.2f}%")
    return "\n".join(lines), state


def run_walk_forward(draws: Sequence[Draw], prior) -> Dict:
    start = max(WINDOW_SIZE, len(draws) - WALK_FORWARD_STEPS)
    rows = []
    hit_counts = []
    mse_values = []
    for idx in range(start, len(draws)):
        context = make_context(draws, prior, max(0, idx - WINDOW_SIZE), idx)
        try:
            model = train_gpu_calibrated_xgb(draws, prior, idx)
            state = build_component_state(context, prior, model)
        except Exception as exc:
            rows.append({"draw_id": draws[idx].draw_id, "error": str(exc)})
            continue
        top6 = list(map(int, np.argsort(state.ensemble[1:])[::-1][:6] + 1))
        actual = set(draws[idx].numbers)
        hits = len(actual.intersection(top6))
        y = np.zeros(MAX_NUMBER + 1, dtype=np.float64)
        for n in draws[idx].numbers:
            y[n] = 1.0
        mse = float(np.mean((y[1:] - state.ensemble[1:]) ** 2))
        hit_counts.append(hits)
        mse_values.append(mse)
        rows.append({
            "draw_id": draws[idx].draw_id,
            "date": draws[idx].date,
            "actual": list(draws[idx].numbers),
            "predicted_top6": top6,
            "hits": hits,
            "mse": round(mse, 6),
            "kl": round(float(state.kl_divergence), 6),
            "drift_detected": bool(state.drift_detected),
        })
        print(f"Walk-Forward {idx - start + 1}/{len(draws) - start}: sorteo {draws[idx].draw_id} | hits={hits}/6 | mse={mse:.5f}")
    return {
        "window_size": WINDOW_SIZE,
        "steps": len(rows),
        "avg_hits": round(float(np.mean(hit_counts)) if hit_counts else 0.0, 4),
        "avg_mse": round(float(np.mean(mse_values)) if mse_values else 0.0, 6),
        "rows": rows,
    }


def run_final_simulation(draws: Sequence[Draw], prior, context: WindowContext):
    model = train_gpu_calibrated_xgb(draws, prior, len(draws))
    state = build_component_state(context, prior, model)
    ranked, total_evaluated = generate_mc_combinations_until_target(state)
    max_confidence = float(ranked[0]["confidence"]) if ranked else 0.0
    top = [item for item in ranked if float(item["confidence"]) >= CONFIDENCE_THRESHOLD][:TARGET_OPERATIONAL_COMBOS]
    return state, top, max_confidence, ranked[:120], total_evaluated


def explain_combo(item: Dict, state: ComponentState) -> str:
    numbers = item.get("numbers", [])
    winners = []
    for number in numbers:
        winner, score = component_winner(state, int(number))
        winners.append(f"{number}:{winner}({score:.2f})")
    return (
        f"Combo {numbers} priorizado por ensemble Python. "
        f"Confianza={item.get('confidence', 0):.2f}%. "
        f"Componentes: XGB={item.get('xgboost_contrast_mean', 0):.3f}, Bayes={item.get('bayes_mean', 0):.3f}, "
        f"Fourier={item.get('fourier_mean', 0):.3f}, Estructura={item.get('structure_mean', 0):.3f}. "
        f"Ruta por número: {' | '.join(winners)}."
    )


def build_generation_pool(ranked: Sequence[Dict], state: ComponentState) -> List[Dict]:
    pool = []
    for idx, item in enumerate(ranked[:80], start=1):
        clone = dict(item)
        clone["rank"] = idx
        clone["procedure"] = explain_combo(item, state)
        pool.append(clone)
    return pool


def manual_suggestion_seed(state: ComponentState) -> List[Dict]:
    rows = []
    for n in range(1, MAX_NUMBER + 1):
        winner, winner_score = component_winner(state, n)
        rows.append({
            "number": n,
            "score": round(float(state.ensemble[n] * 100.0), 4),
            "winner_component": winner,
            "winner_component_score": round(float(winner_score), 6),
            "fourier": round(float(state.fourier[n]), 6),
            "bayes": round(float(state.bayes[n]), 6),
            "xgboost": round(float(state.xgb_contrast[n]), 6),
            "xgboost_raw": round(float(state.xgb_raw[n]), 8),
            "period_fft": round(float(state.fourier_period[n]), 4),
        })
    return sorted(rows, key=lambda x: x["score"], reverse=True)


def prepare_session_contexts(session: CrunchSession) -> None:
    ensure_session_loaded(session)
    assert session.draws is not None and session.prior is not None
    if session.all_matrix is None:
        session.all_matrix = binary_matrix(session.draws)
    hindsight_end = len(session.draws) - 1
    current_end = len(session.draws)
    if session.hindsight_context is None:
        print("Precalculando Fourier/Bayes para auditoría hindsight...")
        session.hindsight_context = make_context(session.draws, session.prior, max(0, hindsight_end - WINDOW_SIZE), hindsight_end)
    if session.current_context is None:
        print("Precalculando Fourier/Bayes para simulación futura...")
        session.current_context = make_context(session.draws, session.prior, max(0, current_end - WINDOW_SIZE), current_end)


def ensure_session_loaded(session: CrunchSession) -> None:
    if session.draws is None:
        session.draws = load_historial("historial.csv")
        session.prior = static_prior(session.draws)
        session.all_matrix = binary_matrix(session.draws)


def build_result_json(session: CrunchSession) -> Dict:
    if session.final_state is None:
        raise RuntimeError("No hay simulación final en memoria. Ejecuta la opción [3] o [1] primero.")
    top_combinations = session.top_combinations or []
    generator_pool = session.generator_pool or []
    result = {
        "last_update": datetime.now(timezone.utc).isoformat(),
        "source": "local_cruncher_python_gpu",
        "drift_detected": bool(session.final_state.drift_detected),
        "hindsight_log": session.hindsight_log or "Sin auditoría ejecutada.",
        "procedure_log": session.procedure_log or "Pipeline Python: CSV → ventana 120 → Fourier/Bayes → XGBoost CUDA calibrado → Monte Carlo extendido → filtro >=70.",
        "max_confidence_found": round(float(session.max_confidence_found), 4),
        "total_mc_evaluated": int(session.total_mc_evaluated),
        "number_scores": {str(number): round(float(session.final_state.ensemble[number] * 100.0), 4) for number in range(1, MAX_NUMBER + 1)},
        "manual_suggestion_seed": manual_suggestion_seed(session.final_state),
        "walk_forward": session.walk_forward or {},
        "generator_pool": generator_pool,
        "top_combinations": [
            {
                "numbers": item["numbers"],
                "confidence": round(float(item["confidence"]), 4),
                "xgboost_raw_mean": round(float(item["xgboost_raw_mean"]), 8),
                "xgboost_contrast_mean": round(float(item["xgboost_contrast_mean"]), 6),
                "bayes_mean": round(float(item["bayes_mean"]), 6),
                "fourier_mean": round(float(item["fourier_mean"]), 6),
                "structure_mean": round(float(item["structure_mean"]), 6),
                "procedure": item.get("procedure") or explain_combo(item, session.final_state),
                "source": item.get("source", "python_gpu_montecarlo"),
            }
            for item in top_combinations
        ],
    }
    if not top_combinations:
        result["capital_preservation"] = True
        result["stop_loss_reason"] = f"No hubo combinaciones con confianza >= {CONFIDENCE_THRESHOLD:.0f}% tras {session.total_mc_evaluated:,} evaluaciones."
    else:
        result["capital_preservation"] = False
    return result


def write_resultados_json(session: CrunchSession) -> None:
    result = build_result_json(session)
    Path(session.last_export_path).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nArchivo {session.last_export_path} generado correctamente.")


def find_git_executable() -> Optional[str]:
    found = shutil.which("git")
    if found:
        return found
    common_paths = [
        r"C:\Program Files\Git\cmd\git.exe",
        r"C:\Program Files\Git\bin\git.exe",
        r"C:\Program Files (x86)\Git\cmd\git.exe",
        r"C:\Program Files (x86)\Git\bin\git.exe",
        str(Path.home() / r"AppData\Local\Programs\Git\cmd\git.exe"),
        str(Path.home() / r"AppData\Local\Programs\Git\bin\git.exe"),
    ]
    for path in common_paths:
        if Path(path).exists():
            os.environ["PATH"] = str(Path(path).parent) + os.pathsep + os.environ.get("PATH", "")
            return path
    return None


def run_git_command(git_exe: str, args: List[str]) -> bool:
    result = subprocess.run([git_exe] + args, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.stderr.strip():
        print(result.stderr.strip())
    return result.returncode == 0


def git_sync() -> None:
    print("\nSincronizando con Git...")
    git_exe = find_git_executable()
    if git_exe is None:
        print("Git no está en PATH. resultados.json ya fue generado; instala Git o ejecuta manualmente git add/commit/push.")
        return
    run_git_command(git_exe, ["add", "resultados.json"])
    run_git_command(git_exe, ["commit", "-m", "Update predictions"])
    run_git_command(git_exe, ["push", "origin", "main"])


def print_simulation_summary(session: CrunchSession) -> None:
    assert session.final_state is not None
    print(f"\nDrift detectado: {session.final_state.drift_detected}")
    print(f"KL: {session.final_state.kl_divergence:.6f}")
    print(f"Confianza máxima encontrada: {session.max_confidence_found:.2f}%")
    print(f"Combinaciones Monte Carlo evaluadas: {session.total_mc_evaluated:,}")
    if not session.top_combinations:
        print("\nSTOP-LOSS ACTIVO: No hubo combinaciones >= 70%.")
        return
    print("\nTOP COMBINACIONES OPERATIVAS:")
    for i, item in enumerate(session.top_combinations, start=1):
        print(f"{i:02d}. {item['numbers']} | Confianza={item['confidence']:.2f}% | XGB={item['xgboost_contrast_mean']:.4f} | Bayes={item['bayes_mean']:.4f} | Fourier={item['fourier_mean']:.4f}")


def action_hindsight(session: CrunchSession) -> None:
    clear_screen()
    print_box(["[2] INGENIERÍA INVERSA", "Cargando historial.csv y analizando último sorteo real"])
    prepare_session_contexts(session)
    assert session.draws is not None and session.prior is not None and session.hindsight_context is not None
    log, _ = hindsight_attribution(session.draws, session.prior, session.hindsight_context)
    session.hindsight_log = log
    print("\n" + log)


def action_monte_carlo(session: CrunchSession) -> None:
    clear_screen()
    print_box(["[3] MONTE CARLO EXTENDIDO", "Python genera pool, scores y combinaciones para la web"])
    prepare_session_contexts(session)
    assert session.draws is not None and session.prior is not None and session.current_context is not None
    state, top, max_confidence, ranked_pool, total_evaluated = run_final_simulation(session.draws, session.prior, session.current_context)
    session.final_state = state
    session.top_combinations = top
    session.max_confidence_found = max_confidence
    session.total_mc_evaluated = total_evaluated
    session.generator_pool = build_generation_pool(ranked_pool, state)
    session.procedure_log = f"Se evaluaron {total_evaluated:,} combinaciones por Monte Carlo ponderado en Python. El ciclo continuó hasta obtener {len(top)} combinaciones >= {CONFIDENCE_THRESHOLD:.0f}% o alcanzar el límite de {MAX_MC_COMBINATIONS:,}."
    print_simulation_summary(session)


def action_export(session: CrunchSession) -> None:
    clear_screen()
    print_box(["[4] EXPORTAR A WEB", "Generando resultados.json y sincronizando Git/Vercel"])
    if session.final_state is None:
        print("\nNo hay simulación en memoria. Ejecutando Monte Carlo automáticamente...")
        action_monte_carlo(session)
    write_resultados_json(session)
    git_sync()


def action_full_pipeline(session: CrunchSession) -> None:
    clear_screen()
    started = time.perf_counter()
    print_box(["[1] PIPELINE CUANTITATIVO COMPLETO", "Carga → Walk-Forward → Hindsight → GPU → Monte Carlo extendido → JSON → Git"])
    print("\n[FASE 1] Cargando historial y montando matrices en RAM...")
    prepare_session_contexts(session)
    assert session.draws is not None and session.prior is not None and session.hindsight_context is not None and session.current_context is not None

    print("\n[FASE 2] Ejecutando Walk-Forward alimentado por el mismo contexto local...")
    session.walk_forward = run_walk_forward(session.draws, session.prior)

    print("\n[FASE 3] Ejecutando auditoría hindsight del último sorteo...")
    hindsight_log, _ = hindsight_attribution(session.draws, session.prior, session.hindsight_context)
    session.hindsight_log = hindsight_log
    print("\n═══════════════════════════════════════════════════════")
    print("AUDITORÍA HINDSIGHT")
    print("═══════════════════════════════════════════════════════")
    print(hindsight_log)
    print("═══════════════════════════════════════════════════════")

    print("\n[FASE 4] Entrenando modelo final y lanzando Monte Carlo extendido...")
    state, top, max_confidence, ranked_pool, total_evaluated = run_final_simulation(session.draws, session.prior, session.current_context)
    session.final_state = state
    session.top_combinations = top
    session.max_confidence_found = max_confidence
    session.total_mc_evaluated = total_evaluated
    session.generator_pool = build_generation_pool(ranked_pool, state)
    session.procedure_log = (
        f"Walk-Forward: {session.walk_forward.get('steps', 0)} pasos, avg_hits={session.walk_forward.get('avg_hits', 0)}, avg_mse={session.walk_forward.get('avg_mse', 0)}. "
        f"Monte Carlo: {total_evaluated:,} combinaciones evaluadas; objetivo={TARGET_OPERATIONAL_COMBOS} combos >= {CONFIDENCE_THRESHOLD:.0f}%. "
        "La web no recalcula: consume generator_pool, top_combinations, number_scores y manual_suggestion_seed desde este JSON."
    )
    print_simulation_summary(session)

    print("\n[FASE 5] Exportando resultados.json...")
    write_resultados_json(session)
    print("\n[FASE 6] Sincronizando Git/Vercel...")
    git_sync()
    print(f"\nPipeline completo finalizado en {time.perf_counter() - started:.2f} segundos.")


def run_menu() -> None:
    session = CrunchSession()
    while True:
        print_menu()
        choice = input("\nSelecciona una opción: ").strip()
        try:
            if choice == "1":
                action_full_pipeline(session); pause()
            elif choice == "2":
                action_hindsight(session); pause()
            elif choice == "3":
                action_monte_carlo(session); pause()
            elif choice == "4":
                action_export(session); pause()
            elif choice == "5":
                print("\nSaliendo del sistema."); break
            else:
                print("\nOpción inválida."); pause()
        except KeyboardInterrupt:
            print("\nProceso interrumpido por el usuario."); pause()
        except Exception as exc:
            print("\nERROR:"); print(str(exc)); pause()


if __name__ == "__main__":
    ensure_dependencies()
    run_menu()
