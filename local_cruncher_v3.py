#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
local_cruncher_v3.py

Motor secuencial local para Melate/Revancha.
- Buffer reciente estricto: descarta historia antigua y conserva solo los últimos N sorteos.
- Backtesting ciego secuencial sin leakage.
- Expertos: física web, temporal web, entropía, Fourier, Bayes, XGBoost, LSTM y Markov.
- Optuna optimiza pesos dinámicos sobre ventanas móviles recientes.
- Monte Carlo de 32M combinaciones con CuPy si existe CUDA; fallback NumPy.
- El ranking usa net_score ponderado por Optuna; no se exportan métricas cosméticas.
"""

from __future__ import annotations

import gc
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

# ═══════════════════════════════════════════════════════
# CONFIGURACIÓN GENERAL
# ═══════════════════════════════════════════════════════

MAX_NUMBER = 56
PICK_COUNT = 6
RECENT_BUFFER_DEFAULT = 180
RECENT_BUFFER_MIN = 150
RECENT_BUFFER_MAX = 200
LSTM_WINDOW = 20
OOS_STEPS = 45
OPTUNA_TRIALS = 300
MC_TOTAL_COMBINATIONS = 32_000_000
MC_BATCH_SIZE = 400_000
MC_KEEP_PER_BATCH = 4000
TOP_EXPORT = 250
TOP_FINAL = 10
RANDOM_SEED = 73073
EPS = 1e-12
DRIFT_WINDOW = 15
DRIFT_KL_THRESHOLD = 0.18

WEIGHT_MIN = 4.25
WEIGHT_MAX = 5.25
WEIGHT_DIFF_MAX = 0.30
BASE_WEIGHT = 4.75
WEB_WEAR = {"L": 0.0, "K": 0.085, "r": 0.055, "n0": 60.0}
BAYES_WEAR = {"L": 0.0, "K": 1.0, "r": 0.09, "n0": 35.0}

EXPERT_NAMES = [
    "physical",
    "temporal",
    "entropy",
    "fourier",
    "bayes",
    "xgboost",
    "lstm",
    "markov",
    "structural",
]

# Calibración OOS: la física de esferas debe ganarse su peso con sorteos ocultos.
PHYSICS_MIN_WEIGHT = 0.025
PHYSICS_MAX_WEIGHT_WEAK = 0.08
PHYSICS_MAX_WEIGHT_MEDIUM = 0.16
PHYSICS_MAX_WEIGHT_STRONG = 0.26
PHYSICS_MAX_WEIGHT_ELITE = 0.34
PHYSICS_RANDOM_TOP10_BASELINE = 6 * 10 / 56
PHYSICS_RANDOM_TOP6_BASELINE = 6 * 6 / 56

# Guardrails de jurado: ningún experto debe monopolizar el ensemble.
# XGBoost puede dominar si gana OOS, pero no tapar física, secuencia, Markov, Fourier, etc.
MAX_EXPERT_WEIGHT = 0.38
MIN_ACTIVE_EXPERTS = 4
DIVERSITY_PENALTY_STRENGTH = 1.35
ACTIVE_EXPERT_THRESHOLD = 0.055

# Ablación física: la física conserva peso alto solo si mejora el ensemble OOS completo.
PHYSICS_ABLATION_CONSERVATIVE_CAP = 0.08
PHYSICS_ABLATION_MEDIUM_CAP = 0.14
PHYSICS_ABLATION_STRONG_CAP = 0.22
PHYSICS_ABLATION_ELITE_CAP = 0.30
PHYSICS_ABLATION_MIN_GAIN = 0.035
PHYSICS_ABLATION_STRONG_GAIN = 0.105
PHYSICS_ABLATION_ELITE_GAIN = 0.180

REQUIRED_LIBS = [
    ("pandas", "pandas"),
    ("numpy", "numpy"),
    ("scipy", "scipy"),
    ("xgboost", "xgboost"),
    ("sklearn", "scikit-learn"),
    ("optuna", "optuna"),
    ("torch", "torch"),
]

pd = None
np = None
rfft = None
rfftfreq = None
XGBClassifier = None
optuna = None
torch = None
nn = None
cp = None
XP = None
GPU_ARRAYS = False

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
class ExpertBundle:
    experts: Dict[str, object]
    physics: Dict
    periods: object
    drift_detected: bool
    kl: float
    h_recent: float
    h_window: float


@dataclass
class FoldRecord:
    draw_id: str
    date: Optional[str]
    actual: Tuple[int, int, int, int, int, int]
    experts: Dict[str, object]
    drift_detected: bool
    kl: float


# ═══════════════════════════════════════════════════════
# DEPENDENCIAS Y DISPOSITIVOS
# ═══════════════════════════════════════════════════════

def module_exists(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def pip_install(package: str) -> bool:
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", package, "--quiet", "--disable-pip-version-check"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except Exception:
        return False


def ensure_dependencies() -> None:
    missing = [(m, p) for m, p in REQUIRED_LIBS if not module_exists(m)]
    if missing:
        print("Instalando dependencias necesarias para el hardware, por favor espere...")
    for _, package in missing:
        pip_install(package)

    # CuPy es opcional: si no entra, se usa NumPy sin cerrar el programa.
    if not module_exists("cupy"):
        print("Intentando habilitar CuPy para CUDA 12.x; si falla, se usará NumPy.")
        pip_install("cupy-cuda12x")

    import_runtime()


def import_runtime() -> None:
    global pd, np, rfft, rfftfreq, XGBClassifier, optuna, torch, nn, cp, XP, GPU_ARRAYS
    import pandas as _pd
    import numpy as _np
    from scipy.fft import rfft as _rfft, rfftfreq as _rfftfreq
    from xgboost import XGBClassifier as _XGBClassifier
    import optuna as _optuna
    import torch as _torch
    import torch.nn as _nn

    pd = _pd
    np = _np
    rfft = _rfft
    rfftfreq = _rfftfreq
    XGBClassifier = _XGBClassifier
    optuna = _optuna
    torch = _torch
    nn = _nn

    try:
        import glob as _glob
        cuda_bins = []
        cuda_path = os.environ.get("CUDA_PATH") or os.environ.get("CUDA_HOME")
        if cuda_path:
            cuda_bins.append(os.path.join(cuda_path, "bin"))
        cuda_bins.extend([p for p in os.environ.get("PATH", "").split(os.pathsep) if p])
        nvrtc_hits = []
        for folder in cuda_bins:
            nvrtc_hits.extend(_glob.glob(os.path.join(folder, "nvrtc64_*.dll")))
            nvrtc_hits.extend(_glob.glob(os.path.join(folder, "nvrtc*.dll")))
        if not nvrtc_hits:
            raise RuntimeError("No encontré nvrtc64_*.dll en CUDA_PATH/PATH. Se usará NumPy CPU para Monte Carlo.")
        import cupy as _cp
        _ = _cp.cuda.runtime.getDeviceCount()
        # Prueba real de NVRTC: fuerza compilación JIT antes de habilitar GPU_ARRAYS.
        _x = _cp.asarray([1, 2, 3], dtype=_cp.float32)
        _kernel = _cp.ElementwiseKernel("float32 x", "float32 y", "y = x + 1", "nvrtc_probe_kernel")
        _y = _kernel(_x)
        _ = float(_cp.sum(_y).get())
        del _x, _y, _kernel
        cp = _cp
        XP = _cp
        GPU_ARRAYS = True
        print("CuPy activo: Monte Carlo usará GPU/VRAM.")
    except Exception as exc:
        cp = None
        XP = _np
        GPU_ARRAYS = False
        print(f"CuPy no disponible o CUDA/NVRTC incompleto; Monte Carlo usará NumPy CPU. Detalle: {exc}")


def torch_device():
    if torch is not None and torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


def cleanup_memory() -> None:
    gc.collect()
    try:
        if torch is not None and torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass
    try:
        if cp is not None:
            cp.get_default_memory_pool().free_all_blocks()
            cp.get_default_pinned_memory_pool().free_all_blocks()
    except Exception:
        pass


# ═══════════════════════════════════════════════════════
# UI CONSOLA Y CARGA DE DATOS
# ═══════════════════════════════════════════════════════

def clear() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def pause() -> None:
    input("\nENTER para continuar...")


def print_menu() -> None:
    clear()
    print("╔" + "═" * 96 + "╗")
    print("║  MELATE LOCAL CRUNCHER V3 · BACKTESTING CIEGO SECUENCIAL + GPU                    ║")
    print("╠" + "═" * 96 + "╣")
    print("║  [1] Ejecutar pipeline secuencial completo                                         ║")
    print("║  [2] Sincronizar resultados.json existente                                         ║")
    print("║  [3] Salir                                                                         ║")
    print("╚" + "═" * 96 + "╝")


def choose_game_config() -> GameConfig:
    print("\nSelecciona juego a simular:")
    print("  [1] Revancha")
    print("  [2] Melate")
    choice = input("Opción [1]: ").strip() or "1"
    if choice == "2":
        return GameConfig("melate", "Melate", ["historial_melate.csv", "melate.csv", "historial.csv"], DEFAULT_BALL_WEIGHTS_MELATE)
    return GameConfig("revancha", "Revancha", ["historial_revancha.csv", "revancha.csv", "historial.csv"], DEFAULT_BALL_WEIGHTS_REVANCHA)


def choose_recent_buffer() -> int:
    raw = input(f"Buffer reciente [{RECENT_BUFFER_DEFAULT}; permitido {RECENT_BUFFER_MIN}-{RECENT_BUFFER_MAX}]: ").strip()
    if not raw:
        return RECENT_BUFFER_DEFAULT
    try:
        value = int(raw)
    except Exception:
        return RECENT_BUFFER_DEFAULT
    return max(RECENT_BUFFER_MIN, min(RECENT_BUFFER_MAX, value))


def resolve_csv_path(config: GameConfig) -> str:
    for candidate in config.csv_candidates:
        if Path(candidate).exists():
            return candidate
    return config.csv_candidates[-1]


def parse_int(value) -> Optional[int]:
    try:
        if pd.isna(value):
            return None
        return int(float(str(value).strip()))
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
        if all(name in lower for name in group):
            natural = [lower[name] for name in group]
            break
    if not natural:
        numeric = []
        for col in df.columns:
            s = pd.to_numeric(df[col], errors="coerce")
            if s.notna().mean() > 0.80 and s.between(1, MAX_NUMBER).mean() > 0.55:
                numeric.append(col)
        if len(numeric) < PICK_COUNT:
            raise ValueError("No pude detectar columnas de números. Usa n1,n2,n3,n4,n5,n6.")
        natural = numeric[:PICK_COUNT]
    draw_col = next((lower[x] for x in ["sorteo", "draw", "draw_id", "concurso", "id"] if x in lower), None)
    date_col = next((lower[x] for x in ["fecha", "date", "draw_date"] if x in lower), None)
    add_col = next((lower[x] for x in ["adicional", "additional", "bonus", "extra"] if x in lower), None)
    return natural, add_col, draw_col, date_col


def load_all_draws(path: str) -> List[Draw]:
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"No existe {csv_path.resolve()}")
    df = pd.read_csv(csv_path)
    natural, add_col, draw_col, date_col = detect_columns(df)
    draws: List[Draw] = []
    for _, row in df.iterrows():
        nums = sorted({n for n in (parse_int(row[c]) for c in natural) if n is not None and 1 <= n <= MAX_NUMBER})
        if len(nums) != PICK_COUNT:
            continue
        add = parse_int(row[add_col]) if add_col else None
        draw_id = str(row[draw_col]) if draw_col else str(len(draws))
        date = str(row[date_col]) if date_col else None
        draws.append(Draw(len(draws), draw_id, date, tuple(nums), add))

    ids = [parse_int(d.draw_id) for d in draws]
    if all(v is not None for v in ids) and len(set(ids)) > 1:
        draws = [d for _, d in sorted(zip(ids, draws), key=lambda x: x[0])]
    draws = [Draw(i, d.draw_id, d.date, d.numbers, d.additional) for i, d in enumerate(draws)]
    if len(draws) < RECENT_BUFFER_MIN:
        raise ValueError(f"Se requieren al menos {RECENT_BUFFER_MIN} sorteos válidos; hay {len(draws)}")
    return draws


def truncate_recent(draws: Sequence[Draw], buffer_size: int) -> Tuple[List[Draw], int]:
    buffer_size = max(RECENT_BUFFER_MIN, min(RECENT_BUFFER_MAX, int(buffer_size)))
    discarded = max(0, len(draws) - buffer_size)
    recent = list(draws[-buffer_size:])
    recent = [Draw(i, d.draw_id, d.date, d.numbers, d.additional) for i, d in enumerate(recent)]
    return recent, discarded


# ═══════════════════════════════════════════════════════
# MATEMÁTICA BASE / HEURÍSTICA WEB
# ═══════════════════════════════════════════════════════

def binary_matrix(draws: Sequence[Draw]):
    m = np.zeros((len(draws), MAX_NUMBER + 1), dtype=np.float64)
    for i, draw in enumerate(draws):
        m[i, list(draw.numbers)] = 1.0
    return m


def counts(draws: Sequence[Draw]):
    return np.sum(binary_matrix(draws), axis=0) if draws else np.zeros(MAX_NUMBER + 1, dtype=np.float64)


def probs_from_counts(c):
    p = np.zeros(MAX_NUMBER + 1, dtype=np.float64)
    total = float(np.sum(c[1:]))
    if total > 0:
        p[1:] = c[1:] / total
    return p


def minmax(v):
    arr = np.asarray(v, dtype=np.float64)
    out = np.zeros_like(arr, dtype=np.float64)
    x = np.nan_to_num(arr[1:], nan=0.0, posinf=0.0, neginf=0.0)
    lo = float(np.min(x))
    hi = float(np.max(x))
    out[1:] = 0.5 if hi - lo <= EPS else (x - lo) / (hi - lo)
    return out


def normalize_prob_like(v):
    arr = np.asarray(v, dtype=np.float64).copy()
    arr[0] = 0
    arr = np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0)
    arr[1:] = np.maximum(arr[1:], 0)
    s = float(np.sum(arr[1:]))
    if s <= EPS:
        arr[1:] = 1 / MAX_NUMBER
    else:
        arr[1:] /= s
    return arr


def sigmoid_loss(n, params):
    return params["L"] + (params["K"] - params["L"]) / (1 + math.exp(-params["r"] * (n - params["n0"])))


def build_physics(draws: Sequence[Draw], config: GameConfig):
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
        "score": minmax(score),
        "min_weight": float(np.min(valid)),
        "max_weight": float(np.max(valid)),
        "diff_weight": float(np.max(valid) - np.min(valid)),
        "regulatory_ok": bool(np.min(valid) >= WEIGHT_MIN and np.max(valid) <= WEIGHT_MAX and (np.max(valid) - np.min(valid)) <= WEIGHT_DIFF_MAX),
    }


def fourier_scores(draws: Sequence[Draw]):
    x = binary_matrix(draws)[:, 1:]
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


def bayes_scores(draws: Sequence[Draw]):
    c = counts(draws)
    p0 = probs_from_counts(c)
    wear = np.zeros(MAX_NUMBER + 1)
    for n in range(1, MAX_NUMBER + 1):
        wear[n] = sigmoid_loss(float(c[n]), BAYES_WEAR)
    raw = np.zeros(MAX_NUMBER + 1)
    raw[1:] = p0[1:] * (1 + 2.4 * minmax(wear)[1:]) * (1 + 1.15 * minmax(c)[1:])
    return minmax(normalize_prob_like(raw))


def shannon_entropy(p):
    q = p[1:]
    q = q[q > 0]
    return float(-np.sum(q * np.log2(q))) if len(q) else 0.0


def kl_divergence(p, q):
    pp, qq = p[1:], q[1:]
    mask = pp > 0
    return float(np.sum(pp[mask] * np.log(pp[mask] / np.maximum(qq[mask], EPS)))) if np.any(mask) else 0.0


def drift_metrics(draws: Sequence[Draw]):
    hist = probs_from_counts(counts(draws))
    recent = probs_from_counts(counts(draws[-DRIFT_WINDOW:]))
    k = kl_divergence(recent, hist)
    return bool(k >= DRIFT_KL_THRESHOLD), k, shannon_entropy(recent), shannon_entropy(hist)


def entropy_scores(draws: Sequence[Draw]):
    hist = probs_from_counts(counts(draws))
    recent = probs_from_counts(counts(draws[-DRIFT_WINDOW:]))
    score = np.zeros(MAX_NUMBER + 1)
    for n in range(1, MAX_NUMBER + 1):
        ratio = recent[n] / max(hist[n], EPS)
        score[n] = max(0, min(100, 70 - abs(math.log(ratio or 1)) * 18))
    return minmax(score)


def temporal_scores(draws: Sequence[Draw]):
    m = binary_matrix(draws)
    total = len(draws)
    freq = np.sum(m, axis=0)
    freq30 = np.sum(m[-min(30, total):], axis=0)
    last_seen = np.full(MAX_NUMBER + 1, total, dtype=np.float64)
    for gap, draw in enumerate(reversed(draws)):
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


def structural_number_scores(draws: Sequence[Draw]):
    """Score estructural dinámico por número.

    Conserva una base estructural estable (centralidad/paridad), pero ajusta por
    frecuencia de décadas en los últimos 30 sorteos contra el buffer completo.
    Si una década está subrepresentada recientemente, sus números reciben bonus;
    si está sobreexpuesta, reciben penalización.
    """
    score = np.zeros(MAX_NUMBER + 1, dtype=np.float64)
    if not draws:
        return minmax(score)

    mat = binary_matrix(draws)
    total = len(draws)
    recent_n = min(30, total)
    recent = mat[-recent_n:, 1:]
    full = mat[:, 1:]

    decade_recent = np.zeros(6, dtype=np.float64)
    decade_full = np.zeros(6, dtype=np.float64)
    for n in range(1, MAX_NUMBER + 1):
        d = int((n - 1) // 10)
        decade_recent[d] += float(np.sum(recent[:, n - 1])) / max(1, recent_n)
        decade_full[d] += float(np.sum(full[:, n - 1])) / max(1, total)

    decade_recent_share = decade_recent / max(EPS, float(np.sum(decade_recent)))
    decade_full_share = decade_full / max(EPS, float(np.sum(decade_full)))
    decade_gap = decade_full_share - decade_recent_share

    freq_recent = np.sum(recent, axis=0) / max(1, recent_n)
    freq_full = np.sum(full, axis=0) / max(1, total)
    freq_lift = np.divide(freq_recent + EPS, freq_full + EPS)

    for n in range(1, MAX_NUMBER + 1):
        decade = int((n - 1) // 10)
        center_bonus = 1 - abs(n - 28.5) / 28.5
        decade_base = 1.0 if 1 <= decade <= 4 else 0.72
        parity_bonus = 0.93 if n % 2 == 0 else 0.90

        # Positivo si la década está rezagada en los últimos 30 sorteos.
        decade_rebalance = float(np.clip(decade_gap[decade] * 4.0, -0.35, 0.35))

        # Pequeño refuerzo si el número está alineado con momentum reciente;
        # castigo suave si está exageradamente sobreexpuesto.
        lift = float(freq_lift[n - 1])
        number_momentum = np.clip((lift - 1.0) * 0.18, -0.16, 0.16)
        if lift > 2.2:
            number_momentum -= 0.07

        score[n] = 100 * (
            0.34 * center_bonus
            + 0.22 * decade_base
            + 0.16 * parity_bonus
            + 0.18 * (0.5 + decade_rebalance)
            + 0.10 * (0.5 + number_momentum)
        )
    return minmax(score)


def structure_combo_score_xp(combos, xp):
    arr = combos.astype(xp.float32)
    evens = xp.sum((combos % 2) == 0, axis=1).astype(xp.float32)
    lows = xp.sum(combos <= 28, axis=1).astype(xp.float32)
    sums = xp.sum(arr, axis=1)
    span = (xp.max(arr, axis=1) - xp.min(arr, axis=1)) / 55.0
    consec = xp.sum(xp.diff(combos, axis=1) == 1, axis=1).astype(xp.float32)
    dec = ((combos - 1) // 10).astype(xp.int32)
    decades = xp.zeros((combos.shape[0],), dtype=xp.float32)
    for d in range(6):
        decades += xp.any(dec == d, axis=1).astype(xp.float32)
    sum_score = xp.where((sums >= 110) & (sums <= 240), 1.0, 0.55)
    score = (
        (1 - xp.abs(evens - 3) / 3) * 0.22
        + (1 - xp.abs(lows - 3) / 3) * 0.20
        + (decades / 6) * 0.20
        + (1 - xp.minimum(consec, 4) / 4) * 0.13
        + sum_score * 0.15
        + span * 0.10
    )
    return xp.clip(score, 0, 1)


# ═══════════════════════════════════════════════════════
# MARKOV / LSTM / XGBOOST
# ═══════════════════════════════════════════════════════

def markov_scores(draws: Sequence[Draw]):
    trans = np.ones((MAX_NUMBER + 1, MAX_NUMBER + 1), dtype=np.float64) * 1e-3
    if len(draws) < 2:
        out = np.zeros(MAX_NUMBER + 1)
        out[1:] = 1 / MAX_NUMBER
        return out
    for i in range(1, len(draws)):
        prev = draws[i - 1].numbers
        curr = draws[i].numbers
        for a in prev:
            trans[a, list(curr)] += 1.0
    trans /= np.maximum(np.sum(trans, axis=1, keepdims=True), EPS)
    prev_state = draws[-1].numbers
    score = np.zeros(MAX_NUMBER + 1)
    score[1:] = np.mean(trans[list(prev_state), 1:], axis=0)
    return minmax(normalize_prob_like(score))


def TinyLSTM(input_size=56, hidden_size=128, layers=2, dropout=0.25):
    """Factory que crea el módulo LSTM después de que import_runtime() cargó torch/nn."""
    if nn is None:
        raise RuntimeError("PyTorch no está inicializado. Ejecuta ensure_dependencies() antes de entrenar LSTM.")

    class _TinyLSTM(nn.Module):
        def __init__(self):
            super().__init__()
            self.lstm = nn.LSTM(
                input_size=input_size,
                hidden_size=hidden_size,
                num_layers=layers,
                batch_first=True,
                dropout=dropout if layers > 1 else 0.0,
            )
            self.head = nn.Linear(hidden_size, input_size)

        def forward(self, x):
            out, _ = self.lstm(x)
            return self.head(out[:, -1, :])

    return _TinyLSTM()


def draws_to_binary56(draws: Sequence[Draw]):
    arr = np.zeros((len(draws), MAX_NUMBER), dtype=np.float32)
    for i, d in enumerate(draws):
        for n in d.numbers:
            arr[i, n - 1] = 1.0
    return arr


def train_lstm_scores(draws: Sequence[Draw], epochs: int, seed: int = RANDOM_SEED):
    if len(draws) <= LSTM_WINDOW + 1:
        return minmax(probs_from_counts(counts(draws)))

    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)

    device = torch_device()
    arr = draws_to_binary56(draws)
    X, Y = [], []
    for i in range(LSTM_WINDOW, len(arr)):
        X.append(arr[i - LSTM_WINDOW:i])
        Y.append(arr[i])

    X_np = np.stack(X).astype(np.float32)
    Y_np = np.stack(Y).astype(np.float32)

    if len(X_np) > 6:
        val_count = min(3, max(1, len(X_np) // 8))
        X_train_np, Y_train_np = X_np[:-val_count], Y_np[:-val_count]
        X_val_np, Y_val_np = X_np[-val_count:], Y_np[-val_count:]
    else:
        X_train_np, Y_train_np = X_np, Y_np
        X_val_np, Y_val_np = None, None

    model = TinyLSTM().to(device)
    pos_weight = torch.full((MAX_NUMBER,), (MAX_NUMBER - PICK_COUNT) / PICK_COUNT, dtype=torch.float32, device=device)
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
    opt = torch.optim.AdamW(model.parameters(), lr=0.0025, weight_decay=1e-4)

    X_t = torch.tensor(X_train_np, dtype=torch.float32, device=device)
    Y_t = torch.tensor(Y_train_np, dtype=torch.float32, device=device)
    X_val_t = torch.tensor(X_val_np, dtype=torch.float32, device=device) if X_val_np is not None else None
    Y_val_t = torch.tensor(Y_val_np, dtype=torch.float32, device=device) if Y_val_np is not None else None

    best_state = None
    best_val = float("inf")
    patience = 8
    stale = 0
    batch_size = min(64, X_t.shape[0])

    for _ in range(max(1, epochs)):
        model.train()
        perm = torch.randperm(X_t.shape[0], device=device)
        for start in range(0, X_t.shape[0], batch_size):
            idx = perm[start:start + batch_size]
            opt.zero_grad(set_to_none=True)
            logits = model(X_t[idx])
            loss = loss_fn(logits, Y_t[idx])
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()

        if X_val_t is not None:
            model.eval()
            with torch.no_grad():
                val_loss = float(loss_fn(model(X_val_t), Y_val_t).detach().cpu())
            if val_loss + 1e-5 < best_val:
                best_val = val_loss
                best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
                stale = 0
            else:
                stale += 1
                if stale >= patience:
                    break

    if best_state is not None:
        model.load_state_dict(best_state)

    model.eval()
    with torch.no_grad():
        last = torch.tensor(arr[-LSTM_WINDOW:][None, :, :], dtype=torch.float32, device=device)
        prob = torch.sigmoid(model(last)).detach().cpu().numpy()[0]

    out = np.zeros(MAX_NUMBER + 1)
    out[1:] = prob

    del model, X_t, Y_t
    if X_val_t is not None:
        del X_val_t, Y_val_t
    cleanup_memory()
    return minmax(normalize_prob_like(out))


def expert_bundle(draws: Sequence[Draw], config: GameConfig, lstm_epochs: int = 0, include_xgb_placeholder: bool = True) -> ExpertBundle:
    f, periods = fourier_scores(draws)
    b = bayes_scores(draws)
    physics = build_physics(draws, config)
    t = temporal_scores(draws)
    e = entropy_scores(draws)
    m = markov_scores(draws)
    s = structural_number_scores(draws)
    if lstm_epochs > 0:
        l = train_lstm_scores(draws, epochs=lstm_epochs)
    else:
        l = minmax(probs_from_counts(counts(draws[-LSTM_WINDOW:])))
    d, k, hr, hw = drift_metrics(draws)
    experts = {
        "physical": physics["score"],
        "temporal": t,
        "entropy": e,
        "fourier": f,
        "bayes": b,
        "lstm": l,
        "markov": m,
        "structural": s,
    }
    if include_xgb_placeholder:
        experts["xgboost"] = np.zeros(MAX_NUMBER + 1)
        experts["xgboost"][1:] = 0.5
    return ExpertBundle(experts, physics, periods, d, k, hr, hw)


def number_features(
    draws: Sequence[Draw],
    config: GameConfig,
    bundle: ExpertBundle,
    exclude_experts: Optional[Sequence[str]] = None,
):
    exclude = set(exclude_experts or [])
    m = binary_matrix(draws)
    total = len(draws)
    freq15 = np.mean(m[-min(15, total):], axis=0)
    freq30 = np.mean(m[-min(30, total):], axis=0)
    freq60 = np.mean(m[-min(60, total):], axis=0)
    gaps = np.full(MAX_NUMBER + 1, total + 1, dtype=np.float64)
    for gap, draw in enumerate(reversed(draws)):
        for n in draw.numbers:
            if gaps[n] == total + 1:
                gaps[n] = gap

    nums = np.arange(1, MAX_NUMBER + 1, dtype=np.float64)
    weights = np.array(config.ball_weights, dtype=np.float64)
    columns = [
        nums / MAX_NUMBER,
        freq15[1:],
        freq30[1:],
        freq60[1:],
        probs_from_counts(counts(draws))[1:],
        np.minimum(gaps[1:], RECENT_BUFFER_MAX) / RECENT_BUFFER_MAX,
        1 / (1 + gaps[1:]),
    ]

    for expert_name in ["physical", "temporal", "entropy", "fourier", "bayes", "lstm", "markov", "structural"]:
        if expert_name not in exclude:
            columns.append(bundle.experts[expert_name][1:])

    columns.extend([
        bundle.physics["bonus"][1:] / 20,
        bundle.physics["effective"][1:] / BASE_WEIGHT,
        weights[1:] / BASE_WEIGHT,
        (nums % 2).astype(float),
        np.floor((nums - 1) / 10) / 5,
        (nums > 28).astype(float),
    ])
    return np.column_stack(columns).astype(np.float32)


def train_xgb_scores(draws: Sequence[Draw], config: GameConfig):
    if len(draws) < LSTM_WINDOW + 25:
        out = np.zeros(MAX_NUMBER + 1)
        out[1:] = 0.5
        return out

    X_parts, y_parts = [], []
    start = max(LSTM_WINDOW + 1, len(draws) - 150)
    for target_idx in range(start, len(draws)):
        prefix = draws[:target_idx]
        # XGBoost no usa la columna LSTM para evitar inconsistencia OOS:
        # las mini-folds internas no deben depender de un experto costoso/no replicable.
        bundle = expert_bundle(prefix, config, lstm_epochs=0, include_xgb_placeholder=False)
        X_parts.append(number_features(prefix, config, bundle, exclude_experts=("lstm",)))
        y = np.zeros(MAX_NUMBER, dtype=np.int32)
        for n in draws[target_idx].numbers:
            y[n - 1] = 1
        y_parts.append(y)

    X = np.vstack(X_parts)
    y = np.concatenate(y_parts)

    split = max(1, int(len(X) * 0.85))
    if len(X) - split < MAX_NUMBER:
        split = max(1, len(X) - MAX_NUMBER)
    X_train, y_train = X[:split], y[:split]
    X_val, y_val = X[split:], y[split:]

    model = XGBClassifier(
        n_estimators=400,
        max_depth=4,
        learning_rate=0.02,
        subsample=1.0,
        colsample_bytree=1.0,
        min_child_weight=1.0,
        reg_lambda=0.75,
        objective="binary:logistic",
        eval_metric="logloss",
        scale_pos_weight=(MAX_NUMBER - PICK_COUNT) / PICK_COUNT,
        tree_method="hist",
        device="cuda",
        early_stopping_rounds=20,
        random_state=RANDOM_SEED,
        n_jobs=0,
        verbosity=0,
    )

    def fit_model(m):
        if len(X_val):
            return m.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)
        return m.fit(X_train, y_train, verbose=False)

    try:
        fit_model(model)
    except TypeError:
        model.set_params(early_stopping_rounds=None)
        fit_model(model)
    except Exception as exc:
        print(f"XGBoost CUDA falló, reintentando CPU: {exc}")
        model.set_params(device="cpu")
        try:
            fit_model(model)
        except TypeError:
            model.set_params(early_stopping_rounds=None)
            fit_model(model)

    live_bundle = expert_bundle(draws, config, lstm_epochs=0, include_xgb_placeholder=False)
    X_live = number_features(draws, config, live_bundle, exclude_experts=("lstm",))
    pred = model.predict_proba(X_live)[:, 1]

    out = np.zeros(MAX_NUMBER + 1)
    out[1:] = pred
    del model, X, y, X_train, y_train, X_val, y_val
    cleanup_memory()
    return minmax(normalize_prob_like(out))


def build_full_experts(draws: Sequence[Draw], config: GameConfig, lstm_epochs: int):
    bundle = expert_bundle(draws, config, lstm_epochs=lstm_epochs, include_xgb_placeholder=False)
    bundle.experts["xgboost"] = train_xgb_scores(draws, config)
    return bundle


# ═══════════════════════════════════════════════════════
# BACKTEST OOS + OPTUNA
# ═══════════════════════════════════════════════════════

def build_oos_records(draws: Sequence[Draw], config: GameConfig) -> List[FoldRecord]:
    min_start = max(LSTM_WINDOW + 45, 60)
    start = max(min_start, len(draws) - OOS_STEPS)
    records: List[FoldRecord] = []
    for target_idx in range(start, len(draws)):
        prefix = list(draws[:target_idx])
        target = draws[target_idx]
        print(f"OOS {target_idx - start + 1}/{len(draws) - start}: entrenando hasta T-1 para sorteo {target.draw_id}")
        bundle = build_full_experts(prefix, config, lstm_epochs=30)
        records.append(FoldRecord(target.draw_id, target.date, target.numbers, bundle.experts, bundle.drift_detected, bundle.kl))
        cleanup_memory()
    return records


def normalize_trial_weights(params: Dict[str, float]) -> Dict[str, float]:
    clean = {k: max(1e-6, float(params.get(k, 1e-6))) for k in EXPERT_NAMES}
    total = sum(clean.values()) or 1
    weights = {k: v / total for k, v in clean.items()}
    return enforce_weight_diversity(weights)


def enforce_weight_diversity(weights: Dict[str, float]) -> Dict[str, float]:
    # Cap duro por experto + redistribución proporcional al resto.
    w = {k: max(1e-8, float(weights.get(k, 0.0))) for k in EXPERT_NAMES}
    total = sum(w.values()) or 1.0
    w = {k: v / total for k, v in w.items()}

    excess = 0.0
    for k in EXPERT_NAMES:
        if w[k] > MAX_EXPERT_WEIGHT:
            excess += w[k] - MAX_EXPERT_WEIGHT
            w[k] = MAX_EXPERT_WEIGHT

    if excess > 0:
        eligible = [k for k in EXPERT_NAMES if w[k] < MAX_EXPERT_WEIGHT]
        eligible_total = sum(w[k] for k in eligible)
        if eligible_total <= 1e-12:
            spread = excess / len(EXPERT_NAMES)
            for k in EXPERT_NAMES:
                w[k] += spread
        else:
            for k in eligible:
                room = MAX_EXPERT_WEIGHT - w[k]
                add = excess * (w[k] / eligible_total)
                w[k] += min(room, add)

    total = sum(w.values()) or 1.0
    return {k: w[k] / total for k in EXPERT_NAMES}


def ensemble_diversity_penalty(weights: Dict[str, float]) -> float:
    # Herfindahl alto = concentración excesiva. El mínimo ideal con 9 expertos es ~0.111.
    hhi = sum(float(v) ** 2 for v in weights.values())
    active = sum(1 for v in weights.values() if float(v) >= ACTIVE_EXPERT_THRESHOLD)
    concentration_penalty = max(0.0, hhi - 0.24) * DIVERSITY_PENALTY_STRENGTH
    active_penalty = max(0, MIN_ACTIVE_EXPERTS - active) * 0.18
    return concentration_penalty + active_penalty


def weighted_net_score(experts: Dict[str, object], weights: Dict[str, float]):
    out = np.zeros(MAX_NUMBER + 1, dtype=np.float64)
    for name in EXPERT_NAMES:
        out += weights[name] * np.asarray(experts[name], dtype=np.float64)
    out[0] = 0
    return np.clip(out, 0, 1)


def evaluate_weights(records: Sequence[FoldRecord], weights: Dict[str, float]):
    hits6, hits8, hits10, hits12, mses = [], [], [], [], []
    row_logs = []
    for rec in records:
        net = weighted_net_score(rec.experts, weights)
        order = list(map(int, np.argsort(net[1:])[::-1] + 1))
        actual = set(rec.actual)
        h6 = len(actual.intersection(order[:6]))
        h8 = len(actual.intersection(order[:8]))
        h10 = len(actual.intersection(order[:10]))
        h12 = len(actual.intersection(order[:12]))
        y = np.zeros(MAX_NUMBER + 1)
        for n in actual:
            y[n] = 1.0
        mse = float(np.mean((y[1:] - net[1:]) ** 2))
        hits6.append(h6)
        hits8.append(h8)
        hits10.append(h10)
        hits12.append(h12)
        mses.append(mse)
        row_logs.append({
            "draw_id": rec.draw_id,
            "date": rec.date,
            "actual": list(rec.actual),
            "predicted_top6": order[:6],
            "predicted_top8": order[:8],
            "predicted_top10": order[:10],
            "hits": h6,
            "hits_top8": h8,
            "hits_top10": h10,
            "hits_top12": h12,
            "mse": round(mse, 6),
            "kl": round(float(rec.kl), 6),
            "drift_detected": bool(rec.drift_detected),
        })
    return {
        "avg_hits": float(np.mean(hits6)) if hits6 else 0.0,
        "avg_hits_top8": float(np.mean(hits8)) if hits8 else 0.0,
        "avg_hits_top10": float(np.mean(hits10)) if hits10 else 0.0,
        "avg_hits_top12": float(np.mean(hits12)) if hits12 else 0.0,
        "avg_mse": float(np.mean(mses)) if mses else 0.0,
        "rows": row_logs,
    }


def single_expert_oos_diagnostics(records: Sequence[FoldRecord]) -> Dict[str, Dict[str, float]]:
    diagnostics: Dict[str, Dict[str, float]] = {}
    for expert_name in EXPERT_NAMES:
        hits6, hits10, hits12, mses, lifts, actual_means, non_actual_means = [], [], [], [], [], [], []
        for rec in records:
            scores = np.asarray(rec.experts[expert_name], dtype=np.float64)
            order = list(map(int, np.argsort(scores[1:])[::-1] + 1))
            actual = set(rec.actual)
            h6 = len(actual.intersection(order[:6]))
            h10 = len(actual.intersection(order[:10]))
            h12 = len(actual.intersection(order[:12]))
            y = np.zeros(MAX_NUMBER + 1)
            for n in actual:
                y[n] = 1.0
            mse = float(np.mean((y[1:] - scores[1:]) ** 2))
            actual_values = [float(scores[n]) for n in actual]
            non_actual_values = [float(scores[n]) for n in range(1, MAX_NUMBER + 1) if n not in actual]
            actual_mean = float(np.mean(actual_values)) if actual_values else 0.0
            non_actual_mean = float(np.mean(non_actual_values)) if non_actual_values else 0.0
            lift = actual_mean - non_actual_mean
            hits6.append(h6)
            hits10.append(h10)
            hits12.append(h12)
            mses.append(mse)
            lifts.append(lift)
            actual_means.append(actual_mean)
            non_actual_means.append(non_actual_mean)
        diagnostics[expert_name] = {
            "avg_hits_top6": float(np.mean(hits6)) if hits6 else 0.0,
            "avg_hits_top10": float(np.mean(hits10)) if hits10 else 0.0,
            "avg_hits_top12": float(np.mean(hits12)) if hits12 else 0.0,
            "avg_mse": float(np.mean(mses)) if mses else 0.0,
            "winner_lift": float(np.mean(lifts)) if lifts else 0.0,
            "winner_score_mean": float(np.mean(actual_means)) if actual_means else 0.0,
            "non_winner_score_mean": float(np.mean(non_actual_means)) if non_actual_means else 0.0,
        }
    return diagnostics


def estimate_physics_weight_cap(expert_diag: Dict[str, Dict[str, float]]) -> Tuple[float, str]:
    phys = expert_diag.get("physical", {})
    p_top10 = float(phys.get("avg_hits_top10", 0.0))
    p_top6 = float(phys.get("avg_hits_top6", 0.0))
    p_lift = float(phys.get("winner_lift", 0.0))
    p_mse = float(phys.get("avg_mse", 1.0))

    utilities = {}
    for name, row in expert_diag.items():
        utilities[name] = (
            float(row.get("avg_hits_top6", 0.0)) * 2.50
            + float(row.get("avg_hits_top10", 0.0)) * 0.90
            + float(row.get("avg_hits_top12", 0.0)) * 0.35
            + max(0.0, float(row.get("winner_lift", 0.0))) * 1.25
            - float(row.get("avg_mse", 1.0)) * 2.20
        )
    best_name = max(utilities, key=utilities.get) if utilities else "physical"
    best_utility = utilities.get(best_name, 0.0)
    phys_utility = utilities.get("physical", 0.0)
    relative = phys_utility / max(abs(best_utility), 1e-9)

    if p_top10 <= PHYSICS_RANDOM_TOP10_BASELINE * 1.02 and p_lift <= 0:
        return PHYSICS_MAX_WEIGHT_WEAK, (
            f"La física quedó en modo débil: Top10={p_top10:.2f} vs azar={PHYSICS_RANDOM_TOP10_BASELINE:.2f}, "
            f"lift ganador={p_lift:.4f}. Se limita a {PHYSICS_MAX_WEIGHT_WEAK:.0%}."
        )
    if p_top10 < PHYSICS_RANDOM_TOP10_BASELINE * 1.22 or p_lift < 0.010:
        return PHYSICS_MAX_WEIGHT_MEDIUM, (
            f"La física mostró señal moderada: Top10={p_top10:.2f}, lift={p_lift:.4f}. "
            f"Se limita a {PHYSICS_MAX_WEIGHT_MEDIUM:.0%}."
        )
    if relative >= 0.92 and p_top6 >= PHYSICS_RANDOM_TOP6_BASELINE * 1.18 and p_lift >= 0.020:
        return PHYSICS_MAX_WEIGHT_ELITE, (
            f"La física sí explicó ganadores OOS con fuerza: Top6={p_top6:.2f}, Top10={p_top10:.2f}, "
            f"lift={p_lift:.4f}, utilidad relativa={relative:.2f}. Puede subir hasta {PHYSICS_MAX_WEIGHT_ELITE:.0%}."
        )
    return PHYSICS_MAX_WEIGHT_STRONG, (
        f"La física fue útil pero no dominante: Top6={p_top6:.2f}, Top10={p_top10:.2f}, "
        f"lift={p_lift:.4f}, MSE={p_mse:.4f}. Se limita a {PHYSICS_MAX_WEIGHT_STRONG:.0%}."
    )


def apply_physics_oos_cap(weights: Dict[str, float], physics_cap: float) -> Dict[str, float]:
    w = {k: max(0.0, float(weights.get(k, 0.0))) for k in EXPERT_NAMES}
    total = sum(w.values()) or 1.0
    w = {k: v / total for k, v in w.items()}
    cap = max(PHYSICS_MIN_WEIGHT, min(float(physics_cap), PHYSICS_MAX_WEIGHT_ELITE))
    if w.get("physical", 0.0) <= cap:
        return w
    excess = w["physical"] - cap
    w["physical"] = cap
    receivers = [k for k in EXPERT_NAMES if k != "physical"]
    receiver_total = sum(w[k] for k in receivers)
    if receiver_total <= 1e-12:
        for k in receivers:
            w[k] += excess / len(receivers)
    else:
        for k in receivers:
            w[k] += excess * (w[k] / receiver_total)
    total = sum(w.values()) or 1.0
    return {k: w[k] / total for k in EXPERT_NAMES}


def metrics_utility(metrics: Dict[str, float]) -> float:
    return (
        float(metrics.get("avg_hits", 0.0)) * 2.50
        + float(metrics.get("avg_hits_top8", 0.0)) * 0.65
        + float(metrics.get("avg_hits_top10", 0.0)) * 0.90
        + float(metrics.get("avg_hits_top12", 0.0)) * 0.35
        - float(metrics.get("avg_mse", 1.0)) * 2.20
    )


def remove_physics_and_renormalize(weights: Dict[str, float]) -> Dict[str, float]:
    w = {k: max(0.0, float(weights.get(k, 0.0))) for k in EXPERT_NAMES}
    w["physical"] = 0.0
    receivers = [k for k in EXPERT_NAMES if k != "physical"]
    receiver_total = sum(w[k] for k in receivers)
    if receiver_total <= 1e-12:
        for k in receivers:
            w[k] = 1.0 / len(receivers)
    else:
        for k in receivers:
            w[k] /= receiver_total
    return w


def cap_physics_and_renormalize(weights: Dict[str, float], cap: float) -> Dict[str, float]:
    w = {k: max(0.0, float(weights.get(k, 0.0))) for k in EXPERT_NAMES}
    total = sum(w.values()) or 1.0
    w = {k: v / total for k, v in w.items()}
    cap = max(0.0, min(float(cap), 1.0))
    if w.get("physical", 0.0) <= cap:
        return w
    excess = w["physical"] - cap
    w["physical"] = cap
    receivers = [k for k in EXPERT_NAMES if k != "physical"]
    receiver_total = sum(w[k] for k in receivers) or 1.0
    for k in receivers:
        w[k] += excess * (w[k] / receiver_total)
    total = sum(w.values()) or 1.0
    return {k: w[k] / total for k in EXPERT_NAMES}


def apply_physics_ablation_gate(records: Sequence[FoldRecord], weights: Dict[str, float]):
    with_physics_metrics = evaluate_weights(records, weights)
    without_physics_weights = remove_physics_and_renormalize(weights)
    without_physics_metrics = evaluate_weights(records, without_physics_weights)

    with_u = metrics_utility(with_physics_metrics)
    without_u = metrics_utility(without_physics_metrics)
    gain = with_u - without_u
    original_physical = float(weights.get("physical", 0.0))

    if gain <= 0:
        cap, level, reason = PHYSICS_ABLATION_CONSERVATIVE_CAP, "bloqueada", "quitar la física igualó o mejoró el ensemble"
    elif gain < PHYSICS_ABLATION_MIN_GAIN:
        cap, level, reason = PHYSICS_ABLATION_CONSERVATIVE_CAP, "débil", "la mejora por física fue marginal"
    elif gain < PHYSICS_ABLATION_STRONG_GAIN:
        cap, level, reason = PHYSICS_ABLATION_MEDIUM_CAP, "media", "la física aportó, pero no debe dominar"
    elif gain < PHYSICS_ABLATION_ELITE_GAIN:
        cap, level, reason = PHYSICS_ABLATION_STRONG_CAP, "fuerte", "la física mejoró el ensemble con claridad"
    else:
        cap, level, reason = PHYSICS_ABLATION_ELITE_CAP, "élite", "la física mejoró el ensemble de forma sostenida"

    gated = cap_physics_and_renormalize(weights, cap)
    gated_metrics = evaluate_weights(records, gated)
    gated_u = metrics_utility(gated_metrics)

    payload = {
        "utility_with_physics": round(float(with_u), 6),
        "utility_without_physics": round(float(without_u), 6),
        "utility_after_gate": round(float(gated_u), 6),
        "gain_vs_without_physics": round(float(gain), 6),
        "original_physical_weight": round(float(original_physical), 6),
        "final_physical_weight": round(float(gated.get("physical", 0.0)), 6),
        "applied_cap": round(float(cap), 6),
        "level": level,
        "reason": reason,
    }
    audit = (
        f"Ablación física: utilidad con física={with_u:.4f}, sin física={without_u:.4f}, "
        f"ganancia={gain:.4f}. Nivel={level}; {reason}. "
        f"Peso físico original={original_physical:.1%}, cap={cap:.0%}, "
        f"peso final={gated.get('physical', 0.0):.1%}."
    )
    return gated, payload, audit


def run_optuna(records: Sequence[FoldRecord]):
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    expert_diag = single_expert_oos_diagnostics(records)
    physics_cap, physics_audit = estimate_physics_weight_cap(expert_diag)

    def objective(trial):
        raw = {name: trial.suggest_float(name, 0.001, 1.0, log=True) for name in EXPERT_NAMES}
        weights = normalize_trial_weights(raw)
        weights = apply_physics_oos_cap(weights, physics_cap)
        diversity_penalty = ensemble_diversity_penalty(weights)

        chunk_size = max(8, min(15, len(records)))
        last_value = None
        for end in range(chunk_size, len(records) + 1, chunk_size):
            metrics = evaluate_weights(records[:end], weights)
            last_value = metrics_utility(metrics) - diversity_penalty
            trial.report(last_value, step=end)
            if trial.should_prune():
                raise optuna.TrialPruned()
        if last_value is None or len(records) % chunk_size:
            metrics = evaluate_weights(records, weights)
            last_value = metrics_utility(metrics) - diversity_penalty
        return last_value

    sampler = optuna.samplers.TPESampler(seed=RANDOM_SEED, multivariate=True, group=True)
    pruner = optuna.pruners.MedianPruner(n_startup_trials=30, n_warmup_steps=15, interval_steps=10)
    study = optuna.create_study(direction="maximize", sampler=sampler, pruner=pruner)
    study.optimize(objective, n_trials=OPTUNA_TRIALS, show_progress_bar=False)

    weights = apply_physics_oos_cap(normalize_trial_weights(study.best_params), physics_cap)
    weights, physics_ablation, physics_ablation_audit = apply_physics_ablation_gate(records, weights)

    metrics = evaluate_weights(records, weights)
    top_trials = []
    for tr in sorted(study.trials, key=lambda t: t.value if t.value is not None else -999, reverse=True)[:8]:
        if tr.value is None:
            continue
        trial_weights = apply_physics_oos_cap(normalize_trial_weights(tr.params), physics_cap)
        trial_weights, _, _ = apply_physics_ablation_gate(records, trial_weights)
        top_trials.append({
            "value": round(float(tr.value), 6),
            "weights": {k: round(v, 6) for k, v in trial_weights.items()},
        })

    sorted_weights = sorted(weights.items(), key=lambda kv: kv[1], reverse=True)
    leader, leader_w = sorted_weights[0]
    phys = expert_diag.get("physical", {})
    active_experts = sum(1 for _, v in sorted_weights if v >= ACTIVE_EXPERT_THRESHOLD)
    pruned = sum(1 for t in study.trials if t.state.name == "PRUNED")
    audit = (
        f"Optuna ejecutó {len(study.trials)} pruebas sobre backtesting ciego secuencial "
        f"({pruned} podadas por MedianPruner). "
        f"El experto dominante fue {human_expert_name(leader)} con {leader_w:.1%} del peso neto. "
        f"Calibración física OOS: {physics_audit} {physics_ablation_audit} "
        f"Métricas físicas ganadoras: Top6={phys.get('avg_hits_top6', 0):.2f}, "
        f"Top10={phys.get('avg_hits_top10', 0):.2f}, lift={phys.get('winner_lift', 0):.4f}, "
        f"MSE={phys.get('avg_mse', 0):.4f}. "
        f"Expertos activos: {active_experts}/{len(EXPERT_NAMES)}. "
        f"La selección maximizó aciertos OOS recientes, penalizó MSE, diversidad insuficiente y validó la física por OOS/ablación."
    )
    metrics["expert_diagnostics"] = {
        name: {k: round(float(v), 6) for k, v in row.items()}
        for name, row in expert_diag.items()
    }
    metrics["physics_calibration"] = {
        "cap": round(float(physics_cap), 6),
        "audit": physics_audit,
        "physical_final_weight": round(float(weights.get("physical", 0.0)), 6),
    }
    metrics["physics_ablation"] = physics_ablation
    return weights, metrics, top_trials, audit


# ═══════════════════════════════════════════════════════
# MONTE CARLO GPU
# ═══════════════════════════════════════════════════════

def gpu_score_combo(combos, net_scores, structural_weight, xp):
    base = xp.mean(net_scores[combos], axis=1)
    if structural_weight > 0:
        structural = structure_combo_score_xp(combos, xp)
        return (1 - structural_weight) * base + structural_weight * structural
    return base


def monte_carlo_gpu(final_experts: Dict[str, object], weights: Dict[str, float], total: int = MC_TOTAL_COMBINATIONS):
    xp = XP
    numbers = xp.arange(1, MAX_NUMBER + 1, dtype=xp.int32)
    structural_weight = float(weights.get("structural", 0.0))
    number_weights_total = max(EPS, 1.0 - structural_weight)
    net_cpu = np.zeros(MAX_NUMBER + 1, dtype=np.float64)
    for name in EXPERT_NAMES:
        if name == "structural":
            continue
        net_cpu += (weights[name] / number_weights_total) * np.asarray(final_experts[name], dtype=np.float64)
    net_cpu[0] = 0
    net_cpu = np.clip(net_cpu, 0, 1)
    sample_prob = np.maximum(net_cpu[1:], EPS)
    sample_prob = sample_prob / np.sum(sample_prob)

    net_gpu = xp.asarray(net_cpu, dtype=xp.float32)
    logw = xp.asarray(np.log(sample_prob).reshape(1, -1), dtype=xp.float32)
    rng = xp.random.default_rng(RANDOM_SEED) if GPU_ARRAYS else np.random.default_rng(RANDOM_SEED)
    records: Dict[Tuple[int, ...], Dict] = {}
    generated = 0
    while generated < total:
        batch = min(MC_BATCH_SIZE, total - generated)
        if GPU_ARRAYS:
            g = rng.gumbel(0, 1, size=(batch, MAX_NUMBER), dtype=xp.float32)
        else:
            g = rng.gumbel(0, 1, size=(batch, MAX_NUMBER)).astype(np.float32)
        idx = xp.argpartition(g + logw, -PICK_COUNT, axis=1)[:, -PICK_COUNT:]
        combos = xp.sort(numbers[idx], axis=1).astype(xp.int32)
        score = gpu_score_combo(combos, net_gpu, structural_weight, xp)
        keep_n = min(MC_KEEP_PER_BATCH, batch)
        keep_idx = xp.argpartition(score, -keep_n)[-keep_n:]
        kept_combos = combos[keep_idx]
        kept_scores = score[keep_idx]
        if GPU_ARRAYS:
            kept_combos_cpu = cp.asnumpy(kept_combos)
            kept_scores_cpu = cp.asnumpy(kept_scores)
        else:
            kept_combos_cpu = kept_combos
            kept_scores_cpu = kept_scores
        for row, sc in zip(kept_combos_cpu, kept_scores_cpu):
            key = tuple(int(x) for x in row)
            val = float(sc)
            if key not in records or val > records[key]["net_score"]:
                records[key] = {"numbers": list(key), "net_score": val, "source": "sequential_gpu_montecarlo"}
        if len(records) > 40000:
            records = dict(sorted(records.items(), key=lambda kv: kv[1]["net_score"], reverse=True)[:12000])
        generated += batch
        print(f"Monte Carlo GPU: {generated:,}/{total:,} combinaciones", end="\r")
        if generated % (MC_BATCH_SIZE * 8) == 0:
            cleanup_memory()
    print()
    ranked = sorted(records.values(), key=lambda x: x["net_score"], reverse=True)
    cleanup_memory()
    return ranked, net_cpu


# ═══════════════════════════════════════════════════════
# EXPLICABILIDAD / EXPORTACIÓN
# ═══════════════════════════════════════════════════════

def human_expert_name(name: str) -> str:
    return {
        "physical": "física de esferas",
        "temporal": "inercia temporal",
        "entropy": "estabilidad de entropía",
        "fourier": "micro-ciclos Fourier",
        "bayes": "Bayes por desgaste/frecuencia",
        "xgboost": "XGBoost",
        "lstm": "memoria secuencial LSTM",
        "markov": "transición Markov",
        "structural": "estructura de combinación",
    }.get(name, name)


def explain_number(n: int, final_experts: Dict[str, object], weights: Dict[str, float], bundle: ExpertBundle):
    weighted = {}
    raw = {}
    for name in EXPERT_NAMES:
        if name == "structural":
            continue
        raw[name] = float(final_experts[name][n])
        weighted[name] = float(weights[name] * final_experts[name][n])
    driver = max(weighted.items(), key=lambda kv: kv[1])[0]
    if driver == "lstm":
        reason = "la memoria secuencial de los últimos 20 sorteos lo marcó como compatible con el siguiente estado"
    elif driver == "markov":
        reason = "la transición desde el sorteo inmediatamente anterior favorece este número"
    elif driver == "physical":
        reason = f"su peso efectivo es {bundle.physics['effective'][n]:.4f}g con bonus físico {bundle.physics['bonus'][n]:.1f}"
    elif driver == "fourier":
        reason = f"tiene un micro-ciclo reciente; periodo estimado {bundle.periods[n]:.1f} sorteos"
    elif driver == "bayes":
        reason = "Bayes lo favorece por frecuencia y desgaste dentro del buffer reciente"
    elif driver == "temporal":
        reason = "la regla temporal de racha/retraso reciente lo favorece"
    elif driver == "entropy":
        reason = "su comportamiento reciente no rompe la distribución de entropía"
    else:
        reason = "XGBoost lo clasifica como compatible con la franja reciente"
    return {
        "number": int(n),
        "main_driver": driver,
        "main_driver_human": human_expert_name(driver),
        "reason": reason,
        "weighted_contribution": round(float(weighted[driver]), 8),
        "expert_raw": {k: round(float(v), 6) for k, v in raw.items()},
    }


def enrich_combo(item: Dict, final_experts: Dict[str, object], weights: Dict[str, float], bundle: ExpertBundle, game: GameConfig):
    nums = item["numbers"]
    explanations = [explain_number(n, final_experts, weights, bundle) for n in nums]
    counts_by_driver: Dict[str, int] = {}
    for exp in explanations:
        h = exp["main_driver_human"]
        counts_by_driver[h] = counts_by_driver.get(h, 0) + 1
    drivers = ", ".join(f"{count} por {name}" for name, count in sorted(counts_by_driver.items(), key=lambda kv: kv[1], reverse=True))
    item = dict(item)
    item["game_mode"] = game.mode
    item["game_label"] = game.label
    item["score_kind"] = "optuna_weighted_net_score"
    item["score_percent"] = round(float(item["net_score"] * 100), 4)
    item["human_explanation"] = (
        f"Combinación para {game.label} ordenada por score neto ponderado de Optuna. "
        f"Los impulsores principales fueron: {drivers}. "
        f"Score neto={item['score_percent']:.2f}/100. Este valor es un ranking informativo, no una probabilidad real de ganar."
    )
    item["procedure"] = item["human_explanation"]
    item["plain_route"] = " | ".join(f"{e['number']}: {e['main_driver_human']}" for e in explanations)
    item["number_explanations"] = explanations
    return item


def manual_seed(final_experts: Dict[str, object], weights: Dict[str, float], bundle: ExpertBundle):
    net = weighted_net_score(final_experts, weights)
    rows = []
    for n in range(1, MAX_NUMBER + 1):
        exp = explain_number(n, final_experts, weights, bundle)
        rows.append({
            "number": n,
            "score": round(float(net[n] * 100), 4),
            "winner_component": exp["main_driver"],
            "winner_component_human": exp["main_driver_human"],
            "reason": exp["reason"],
            "expert_raw": exp["expert_raw"],
            "effective_weight": round(float(bundle.physics["effective"][n]), 4),
            "physics_bonus": round(float(bundle.physics["bonus"][n]), 4),
            "uses_in_window": int(bundle.physics["uses"][n]),
        })
    return sorted(rows, key=lambda x: x["score"], reverse=True)


def hindsight_log(draws: Sequence[Draw], config: GameConfig, weights: Dict[str, float]):
    target = draws[-1]
    prefix = draws[:-1]
    bundle = build_full_experts(prefix, config, lstm_epochs=30)
    net = weighted_net_score(bundle.experts, weights)
    order = list(map(int, np.argsort(net[1:])[::-1] + 1))
    lines = [
        f"Auditoría ciega del último sorteo conocido · {config.label}",
        f"Sorteo auditado: {target.draw_id} ({target.date or 'sin fecha'})",
        f"Regla anti-leakage: expertos entrenados solo hasta T-1; el sorteo auditado se ocultó.",
        f"Combinación real: {' '.join(map(str, target.numbers))}",
        f"Hits en Top6={len(set(target.numbers).intersection(order[:6]))}, Top10={len(set(target.numbers).intersection(order[:10]))}, Top12={len(set(target.numbers).intersection(order[:12]))}",
    ]
    for n in target.numbers:
        exp = explain_number(n, bundle.experts, weights, bundle)
        rank = order.index(n) + 1 if n in order else 999
        lines.append(f"Número {n}: rank={rank}/56; {exp['main_driver_human']} · {exp['reason']}")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════
# PIPELINE FINAL
# ═══════════════════════════════════════════════════════

def run_pipeline():
    started = time.perf_counter()
    config = choose_game_config()
    buffer_size = choose_recent_buffer()
    csv_path = resolve_csv_path(config)
    all_draws = load_all_draws(csv_path)
    draws, discarded = truncate_recent(all_draws, buffer_size)
    print(f"\nModo: {config.label}")
    print(f"CSV: {csv_path}")
    print(f"Historia total detectada: {len(all_draws)} sorteos")
    print(f"Olvido histórico aplicado: {discarded} sorteos descartados")
    print(f"Buffer reciente usado: {len(draws)} sorteos ({draws[0].draw_id} → {draws[-1].draw_id})")

    print("\n[1/6] Construyendo backtesting ciego secuencial...")
    oos_records = build_oos_records(draws, config)

    print("\n[2/6] Optuna optimizando pesos dinámicos...")
    weights, wf_metrics, top_trials, optuna_audit = run_optuna(oos_records)
    print(optuna_audit)
    print("Pesos óptimos:")
    for k, v in sorted(weights.items(), key=lambda kv: kv[1], reverse=True):
        print(f"  {human_expert_name(k):28s}: {v:.2%}")

    print("\n[3/6] Auditando último sorteo conocido sin leakage...")
    hlog = hindsight_log(draws, config, weights)
    print(hlog)

    print("\n[4/6] Entrenando expertos finales con todo el buffer reciente...")
    final_bundle = build_full_experts(draws, config, lstm_epochs=120)

    print("\n[5/6] Monte Carlo GPU de 32,000,000 combinaciones...")
    try:
        ranked, net_cpu = monte_carlo_gpu(final_bundle.experts, weights, total=MC_TOTAL_COMBINATIONS)
    except Exception as exc:
        global XP, GPU_ARRAYS, cp
        print(f"Monte Carlo CuPy falló en runtime ({exc}). Reintentando con NumPy CPU sin detener el pipeline...")
        cp = None
        XP = np
        GPU_ARRAYS = False
        cleanup_memory()
        ranked, net_cpu = monte_carlo_gpu(final_bundle.experts, weights, total=MC_TOTAL_COMBINATIONS)

    print("\n[6/6] Exportando resultados.json...")
    enriched_pool = [enrich_combo(item, final_bundle.experts, weights, final_bundle, config) for item in ranked[:TOP_EXPORT]]
    top_combos = enriched_pool[:TOP_FINAL]
    physics = final_bundle.physics
    result = {
        "last_update": datetime.now(timezone.utc).isoformat(),
        "source": "local_cruncher_v3_sequential_gpu",
        "game_mode": config.mode,
        "game_label": config.label,
        "csv_path": csv_path,
        "historical_forgetting": {
            "total_loaded_draws": len(all_draws),
            "discarded_old_draws": discarded,
            "recent_buffer_size": len(draws),
            "buffer_first_draw": draws[0].draw_id,
            "buffer_last_draw": draws[-1].draw_id,
            "principle": "Todo entrenamiento, Optuna, LSTM, Markov, XGBoost y Monte Carlo usan solo el buffer reciente.",
        },
        "score_kind": "optuna_weighted_net_score",
        "vanity_metrics_removed": True,
        "drift_detected": bool(final_bundle.drift_detected),
        "hindsight_log": hlog,
        "procedure_log": (
            f"Se descartaron {discarded} sorteos antiguos y se trabajó solo con los últimos {len(draws)}. "
            f"Cada fold OOS entrenó expertos con datos hasta T-1. Optuna ajustó pesos sobre {len(oos_records)} folds recientes. "
            f"{optuna_audit} Después se entrenaron expertos finales sobre el buffer reciente completo y se generaron {MC_TOTAL_COMBINATIONS:,} combinaciones en Monte Carlo."
        ),
        "optuna_audit": {
            "summary": optuna_audit,
            "trials": OPTUNA_TRIALS,
            "best_weights": {k: round(float(v), 8) for k, v in weights.items()},
            "top_trials": top_trials,
        },
        "walk_forward": {
            "window_size": LSTM_WINDOW,
            "steps": len(oos_records),
            "avg_hits": round(float(wf_metrics["avg_hits"]), 6),
            "avg_hits_top8": round(float(wf_metrics["avg_hits_top8"]), 6),
            "avg_hits_top10": round(float(wf_metrics["avg_hits_top10"]), 6),
            "avg_hits_top12": round(float(wf_metrics["avg_hits_top12"]), 6),
            "avg_mse": round(float(wf_metrics["avg_mse"]), 8),
            "expert_diagnostics": wf_metrics.get("expert_diagnostics", {}),
            "physics_calibration": wf_metrics.get("physics_calibration", {}),
            "physics_ablation": wf_metrics.get("physics_ablation", {}),
            "rows": wf_metrics["rows"],
        },
        "physics_summary": {
            "min_weight": round(float(physics["min_weight"]), 4),
            "max_weight": round(float(physics["max_weight"]), 4),
            "diff_weight": round(float(physics["diff_weight"]), 4),
            "regulatory_ok": bool(physics["regulatory_ok"]),
            "avg_effective_weight": round(float(physics["avg_effective"]), 4),
        },
        "expert_weights": {k: round(float(v), 8) for k, v in weights.items()},
        "number_scores": {str(n): round(float(net_cpu[n] * 100), 6) for n in range(1, MAX_NUMBER + 1)},
        "manual_suggestion_seed": manual_seed(final_bundle.experts, weights, final_bundle),
        "total_mc_evaluated": MC_TOTAL_COMBINATIONS,
        "max_net_score_found": round(float(top_combos[0]["net_score"] if top_combos else 0), 8),
        "generator_pool": enriched_pool,
        "top_combinations": top_combos,
    }
    Path("resultados.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    cleanup_memory()
    print(f"resultados.json generado. Top net_score={result['max_net_score_found']:.8f}")
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
        print_menu()
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
            cleanup_memory()
            pause()
        except Exception as exc:
            print("ERROR:", exc)
            cleanup_memory()
            pause()


if __name__ == "__main__":
    ensure_dependencies()
    main()
