#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Melate/Revancha Local Cruncher V4.

State-of-the-art local lab with strict historical forgetting:
- Every stage sees only the recent buffer, never the full history.
- Walk-forward folds train on [0..T-1] and reveal T only for scoring.
- Legacy sequence and rule-only experts from V3 are intentionally absent.
- Output keeps the V3 JSON contract and adds V4 audit blocks.
"""

from __future__ import annotations

import gc
import importlib.util
import json
import math
import os
import random
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple


def env_int(name: str, default: int, lo: int, hi: int) -> int:
    try:
        return max(lo, min(hi, int(os.getenv(name, default))))
    except Exception:
        return default


MAX_NUMBER = 56
PICK_COUNT = 6
RECENT_BUFFER_MIN = 150
RECENT_BUFFER_MAX = 200
RECENT_BUFFER_DEFAULT = 200
TRANSFORMER_WINDOW = 20
OOS_STEPS = env_int("MELATE_V4_OOS_STEPS", 45, 3, 80)
MC_TOTAL = env_int("MELATE_V4_MC_TOTAL", 4_000_000, 1_000, 20_000_000)
MC_BATCH = env_int("MELATE_V4_MC_BATCH", 150_000, 1_000, 1_000_000)
RANDOM_SEED = 74004
EPS = 1e-12
EXPERT_NAMES = ["physical", "transformer", "xgboost", "fourier", "graph"]

TX_DROPOUT = 0.40
TX_WEIGHT_DECAY = 0.03
TX_EPOCHS = 80
TX_PATIENCE = 5
META_DROPOUT = 0.35
META_WEIGHT_DECAY = 0.05
META_EPOCHS = 120
META_PATIENCE = 6
MIN_DELTA = 1e-4

pd = np = rfft = rfftfreq = XGBClassifier = torch = nn = cp = None
GPU_ARRAYS = False

BALL_WEIGHTS = {
    "revancha": [0, 4.35, 4.33, 4.36, 4.31, 4.35, 4.39, 4.33, 4.37, 4.34, 4.37, 4.36, 4.32, 4.35, 4.32, 4.35, 4.33, 4.31, 4.33, 4.31, 4.39, 4.37, 4.33, 4.34, 4.31, 4.31, 4.38, 4.31, 4.34, 4.36, 4.34, 4.35, 4.35, 4.36, 4.34, 4.37, 4.34, 4.39, 4.32, 4.32, 4.33, 4.37, 4.39, 4.34, 4.35, 4.32, 4.36, 4.40, 4.30, 4.31, 4.32, 4.30, 4.29, 4.29, 4.43, 4.42, 4.44],
    "melate": [0, 4.53, 4.56, 4.53, 4.54, 4.53, 4.52, 4.52, 4.55, 4.54, 4.59, 4.51, 4.60, 4.54, 4.58, 4.60, 4.53, 4.55, 4.55, 4.51, 4.58, 4.57, 4.51, 4.58, 4.50, 4.53, 4.51, 4.50, 4.55, 4.51, 4.54, 4.51, 4.54, 4.52, 4.53, 4.52, 4.59, 4.59, 4.58, 4.52, 4.59, 4.53, 4.53, 4.58, 4.59, 4.51, 4.58, 4.58, 4.58, 4.55, 4.58, 4.59, 4.56, 4.61, 4.58, 4.59, 4.54],
}


@dataclass(frozen=True)
class Draw:
    index: int
    draw_id: str
    date: Optional[str]
    numbers: Tuple[int, int, int, int, int, int]


def exists(module: str) -> bool:
    return importlib.util.find_spec(module) is not None


def ensure_deps() -> None:
    required = [("pandas", "pandas"), ("numpy", "numpy"), ("scipy", "scipy"), ("sklearn", "scikit-learn"), ("xgboost", "xgboost"), ("torch", "torch")]
    missing = [pkg for mod, pkg in required if not exists(mod)]
    if missing:
        print("Instalando dependencias faltantes:", ", ".join(missing))
    for pkg in missing:
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg, "--quiet", "--disable-pip-version-check"])
    import_runtime()


def import_runtime() -> None:
    global pd, np, rfft, rfftfreq, XGBClassifier, torch, nn, cp, GPU_ARRAYS
    import pandas as _pd
    import numpy as _np
    from scipy.fft import rfft as _rfft, rfftfreq as _rfftfreq
    from xgboost import XGBClassifier as _XGBClassifier
    import torch as _torch
    import torch.nn as _nn
    pd, np, rfft, rfftfreq, XGBClassifier, torch, nn = _pd, _np, _rfft, _rfftfreq, _XGBClassifier, _torch, _nn
    try:
        import cupy as _cp
        _cp.cuda.runtime.getDeviceCount()
        cp, GPU_ARRAYS = _cp, True
        print("CuPy activo para aceleracion parcial.")
    except Exception as exc:
        cp, GPU_ARRAYS = None, False
        print(f"CuPy no disponible; fallback NumPy CPU. Detalle: {exc}")


def cleanup() -> None:
    gc.collect()
    if torch is not None and torch.cuda.is_available():
        torch.cuda.empty_cache()
    if cp is not None:
        cp.get_default_memory_pool().free_all_blocks()


def device():
    return torch.device("cuda" if torch is not None and torch.cuda.is_available() else "cpu")


def seed_all(seed: int = RANDOM_SEED) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def choose_mode() -> str:
    print("\n[1] Revancha\n[2] Melate")
    return "melate" if (input("Juego [1]: ").strip() == "2") else "revancha"


def choose_buffer() -> int:
    raw = input(f"Buffer reciente [{RECENT_BUFFER_DEFAULT}; {RECENT_BUFFER_MIN}-{RECENT_BUFFER_MAX}]: ").strip()
    return max(RECENT_BUFFER_MIN, min(RECENT_BUFFER_MAX, int(raw or RECENT_BUFFER_DEFAULT)))


def parse_int(value) -> Optional[int]:
    try:
        if pd.isna(value):
            return None
        return int(float(str(value).strip()))
    except Exception:
        return None


def detect_number_cols(df):
    lower = {str(c).lower().strip(): c for c in df.columns}
    for names in (["n1", "n2", "n3", "n4", "n5", "n6"], ["num1", "num2", "num3", "num4", "num5", "num6"], ["bola1", "bola2", "bola3", "bola4", "bola5", "bola6"]):
        if all(n in lower for n in names):
            return [lower[n] for n in names]
    numeric = []
    for col in df.columns:
        s = pd.to_numeric(df[col], errors="coerce")
        if s.notna().mean() > 0.80 and s.between(1, MAX_NUMBER).mean() > 0.55:
            numeric.append(col)
    if len(numeric) < PICK_COUNT:
        raise ValueError("No pude detectar columnas n1..n6.")
    return numeric[:PICK_COUNT]


def load_draws(path: str) -> List[Draw]:
    df = pd.read_csv(path)
    cols = detect_number_cols(df)
    lower = {str(c).lower().strip(): c for c in df.columns}
    draw_col = next((lower[x] for x in ("sorteo", "draw", "concurso", "id") if x in lower), None)
    date_col = next((lower[x] for x in ("fecha", "date") if x in lower), None)
    rows: List[Draw] = []
    for _, row in df.iterrows():
        nums = sorted({n for n in (parse_int(row[c]) for c in cols) if n and 1 <= n <= MAX_NUMBER})
        if len(nums) == PICK_COUNT:
            rows.append(Draw(len(rows), str(row[draw_col]) if draw_col else str(len(rows)), str(row[date_col]) if date_col else None, tuple(nums)))
    ids = [parse_int(d.draw_id) for d in rows]
    if rows and all(v is not None for v in ids):
        rows = [d for _, d in sorted(zip(ids, rows), key=lambda x: x[0])]
    rows = [Draw(i, d.draw_id, d.date, d.numbers) for i, d in enumerate(rows)]
    if len(rows) < RECENT_BUFFER_MIN:
        raise ValueError(f"Se requieren {RECENT_BUFFER_MIN}+ sorteos; hay {len(rows)}")
    return rows


def truncate_recent(draws: Sequence[Draw], buffer_size: int) -> Tuple[List[Draw], int]:
    buffer_size = max(RECENT_BUFFER_MIN, min(RECENT_BUFFER_MAX, buffer_size))
    recent = [Draw(i, d.draw_id, d.date, d.numbers) for i, d in enumerate(draws[-buffer_size:])]
    return recent, max(0, len(draws) - buffer_size)


def assert_no_leakage(context: str, train_end_idx: int, target_idx: int, buffer_size: int) -> Dict:
    ok = 0 <= train_end_idx < target_idx <= buffer_size - 1 and train_end_idx + 1 == target_idx and buffer_size <= RECENT_BUFFER_MAX
    row = {"context": context, "train_end_idx": train_end_idx, "target_idx": target_idx, "buffer_size": buffer_size, "passed": bool(ok), "rule": "train ends at T-1; target T and future are forbidden"}
    if not ok:
        raise RuntimeError(f"Leakage guard failed: {row}")
    return row


def mat(draws: Sequence[Draw], width: int = MAX_NUMBER + 1):
    m = np.zeros((len(draws), width), dtype=np.float64)
    for i, d in enumerate(draws):
        offset = 1 if width == MAX_NUMBER + 1 else 0
        for n in d.numbers:
            m[i, n - offset] = 1.0
    return m


def minmax(v):
    a = np.asarray(v, dtype=np.float64).copy()
    x = np.nan_to_num(a[1:], nan=0, posinf=0, neginf=0)
    lo, hi = float(np.min(x)), float(np.max(x))
    out = np.zeros(MAX_NUMBER + 1)
    out[1:] = 0.5 if hi - lo <= EPS else (x - lo) / (hi - lo)
    return out


def normalize(v):
    a = np.asarray(v, dtype=np.float64).copy()
    a[0] = 0
    a[1:] = np.maximum(np.nan_to_num(a[1:]), EPS)
    a[1:] /= np.sum(a[1:])
    return a


def counts(draws): return np.sum(mat(draws), axis=0) if draws else np.zeros(MAX_NUMBER + 1)


def entropy(p):
    q = p[1:][p[1:] > 0]
    return float(-np.sum(q * np.log2(q))) if len(q) else 0.0


def kl(p, q):
    pp, qq = p[1:], q[1:]
    mask = pp > 0
    return float(np.sum(pp[mask] * np.log(pp[mask] / np.maximum(qq[mask], EPS)))) if np.any(mask) else 0.0


def drift(draws):
    hist, recent = normalize(counts(draws)), normalize(counts(draws[-15:]))
    k = kl(recent, hist)
    return {"kl": k, "h_recent": entropy(recent), "h_window": entropy(hist), "drift_detected": bool(k >= 0.18)}


def last_gaps(draws):
    gaps = np.full(MAX_NUMBER + 1, len(draws), dtype=np.float64)
    for idx in range(len(draws) - 1, -1, -1):
        gap = len(draws) - 1 - idx
        for n in draws[idx].numbers:
            if gaps[n] == len(draws):
                gaps[n] = gap
    return gaps


def physical_scores(draws, mode):
    uses = counts(draws)
    w = np.asarray(BALL_WEIGHTS[mode], dtype=np.float64)
    eff = np.zeros(MAX_NUMBER + 1)
    bonus = np.zeros(MAX_NUMBER + 1)
    for n in range(1, MAX_NUMBER + 1):
        wear = 0.085 / (1 + math.exp(-0.055 * (uses[n] - 60.0)))
        eff[n] = w[n] - wear
    avg = float(np.mean(eff[1:]))
    for n in range(1, MAX_NUMBER + 1):
        bonus[n] = max(-15, min(20, -((eff[n] - avg) / 0.05) * 6 + (8 if uses[n] / len(draws) > 0.35 else 0)))
    return minmax(50 + bonus * 1.5), {"uses": uses, "effective": eff, "bonus": bonus, "avg_effective": avg, "min_weight": float(np.min(w[1:])), "max_weight": float(np.max(w[1:])), "diff_weight": float(np.ptp(w[1:])), "regulatory_ok": bool(np.ptp(w[1:]) <= 0.30)}


def graph_scores(draws, decay: float = 0.985):
    adj = np.zeros((MAX_NUMBER + 1, MAX_NUMBER + 1), dtype=np.float64)
    for age, d in enumerate(reversed(draws)):
        weight = decay ** age
        nums = list(d.numbers)
        for i in range(len(nums)):
            for j in range(i + 1, len(nums)):
                a, b = nums[i], nums[j]
                adj[a, b] += weight
                adj[b, a] += weight
    raw = adj / max(float(np.max(adj)), EPS)
    return minmax(np.sum(raw, axis=1)), {"adjacency": raw, "max_edge": float(np.max(adj)), "decay": decay}


def graph_bonus(nums, graph):
    vals = [graph["adjacency"][a, b] for i, a in enumerate(nums) for b in nums[i + 1:]]
    return float(np.mean(vals)) if vals else 0.0


def fourier_scores(draws):
    x = mat(draws)[:, 1:]
    x = x - np.mean(x, axis=0, keepdims=True)
    if len(x) < 8:
        return np.r_[0, np.ones(MAX_NUMBER) * 0.5], np.zeros(MAX_NUMBER + 1)
    power = np.abs(rfft(x, axis=0)) ** 2
    freqs = rfftfreq(x.shape[0], 1.0)
    usable = power[1:]
    idx = np.argmax(usable, axis=0)
    raw = np.r_[0, np.log1p(usable[idx, np.arange(MAX_NUMBER)] + np.sum(usable, axis=0))]
    periods = np.zeros(MAX_NUMBER + 1)
    for i, j in enumerate(idx):
        f = freqs[j + 1]
        periods[i + 1] = 1 / f if f > EPS else 0
    return minmax(raw), periods


def train_val_split(X, y, min_val=3):
    if len(X) <= min_val + 2:
        return X, y, None, None, True
    v = min(max(min_val, len(X) // 5), len(X) - 2)
    return X[:-v], y[:-v], X[-v:], y[-v:], False


def build_transformer():
    class Pos(nn.Module):
        def __init__(self):
            super().__init__()
            pe = torch.zeros(TRANSFORMER_WINDOW, 64)
            pos = torch.arange(0, TRANSFORMER_WINDOW, dtype=torch.float32).unsqueeze(1)
            div = torch.exp(torch.arange(0, 64, 2).float() * (-math.log(10000.0) / 64))
            pe[:, 0::2], pe[:, 1::2] = torch.sin(pos * div), torch.cos(pos * div)
            self.register_buffer("pe", pe.unsqueeze(0))
        def forward(self, x): return x + self.pe[:, :x.size(1)]
    class Model(nn.Module):
        def __init__(self):
            super().__init__()
            self.proj = nn.Linear(MAX_NUMBER, 64)
            self.pos = Pos()
            layer = nn.TransformerEncoderLayer(64, 4, 128, TX_DROPOUT, activation="gelu", batch_first=True, norm_first=True)
            self.enc = nn.TransformerEncoder(layer, 2)
            self.norm = nn.LayerNorm(64)
            self.drop = nn.Dropout(TX_DROPOUT)
            self.head = nn.Linear(64, MAX_NUMBER)
        def forward(self, x): return self.head(self.drop(self.norm(self.enc(self.pos(self.proj(x)))[:, -1, :])))
    return Model()


def train_transformer_scores(draws):
    fallback = minmax(counts(draws[-TRANSFORMER_WINDOW:]))
    audit = {"model": "torch.nn.TransformerEncoder", "window_size": TRANSFORMER_WINDOW, "dropout": TX_DROPOUT, "weight_decay": TX_WEIGHT_DECAY, "patience": TX_PATIENCE, "max_epochs": TX_EPOCHS, "trained": False}
    if len(draws) <= TRANSFORMER_WINDOW + 3:
        audit["fallback"] = "insufficient_data"
        return fallback, audit
    arr = mat(draws, MAX_NUMBER).astype(np.float32)
    X = np.stack([arr[i - TRANSFORMER_WINDOW:i] for i in range(TRANSFORMER_WINDOW, len(arr))])
    y = np.stack([arr[i] for i in range(TRANSFORMER_WINDOW, len(arr))])
    Xtr, ytr, Xv, yv, limited = train_val_split(X, y)
    seed_all()
    dev = device()
    model = build_transformer().to(dev)
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=torch.full((MAX_NUMBER,), (MAX_NUMBER - PICK_COUNT) / PICK_COUNT, device=dev))
    opt = torch.optim.AdamW(model.parameters(), lr=0.0015, weight_decay=TX_WEIGHT_DECAY)
    Xt, yt = torch.tensor(Xtr, device=dev), torch.tensor(ytr, device=dev)
    Xvt = torch.tensor(Xv, device=dev) if Xv is not None else Xt
    yvt = torch.tensor(yv, device=dev) if yv is not None else yt
    best, state, stale = float("inf"), None, 0
    epochs = min(TX_EPOCHS, 24 if limited else TX_EPOCHS)
    for epoch in range(1, epochs + 1):
        model.train()
        perm = torch.randperm(len(Xt), device=dev)
        for s in range(0, len(Xt), min(32, len(Xt))):
            idx = perm[s:s + min(32, len(Xt))]
            opt.zero_grad(set_to_none=True)
            loss = loss_fn(model(Xt[idx]), yt[idx])
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
        model.eval()
        with torch.no_grad():
            val = float(loss_fn(model(Xvt), yvt).detach().cpu())
        if val + MIN_DELTA < best:
            best, stale, state = val, 0, {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
        else:
            stale += 1
            if stale >= TX_PATIENCE:
                break
    if state:
        model.load_state_dict(state)
    with torch.no_grad():
        pred = torch.sigmoid(model(torch.tensor(arr[-TRANSFORMER_WINDOW:][None, :, :], device=dev))).detach().cpu().numpy()[0]
    out = np.r_[0, pred]
    audit.update({"trained": True, "validation_limited": bool(limited), "epochs_run": epoch, "best_epoch": max(1, epoch - stale), "best_val_loss": round(best, 8), "early_stopped": bool(stale >= TX_PATIENCE), "architecture": {"d_model": 64, "nhead": 4, "layers": 2, "feedforward": 128}, "device": str(dev)})
    del model
    cleanup()
    return minmax(out), audit


def base_experts(draws, mode, train_tx=True):
    physical, phys_audit = physical_scores(draws, mode)
    fourier, periods = fourier_scores(draws)
    graph, graph_audit = graph_scores(draws)
    transformer, tx_audit = train_transformer_scores(draws) if train_tx else (minmax(counts(draws[-TRANSFORMER_WINDOW:])), {"trained": False, "fallback": "fast_internal"})
    xgb = minmax(counts(draws[-60:]))
    d = drift(draws)
    return {"physical": physical, "transformer": transformer, "xgboost": xgb, "fourier": fourier, "graph": graph}, {"physics": phys_audit, "graph": graph_audit, "transformer": tx_audit, "periods": periods, **d}


def meta_features(draws, experts, audit):
    c = counts(draws)
    freq = c / max(1, len(draws))
    gaps = np.minimum(last_gaps(draws), RECENT_BUFFER_MAX) / RECENT_BUFFER_MAX
    rows = []
    for n in range(1, MAX_NUMBER + 1):
        rows.append([experts[k][n] for k in EXPERT_NAMES] + [freq[n], gaps[n], 1 if n % 2 else 0, 1 if n > 28 else 0, audit["kl"], audit["h_recent"]])
    return np.asarray(rows, dtype=np.float32)


def train_xgb_scores(draws, mode):
    if len(draws) < 60:
        return minmax(counts(draws[-60:])), {"trained": False, "fallback": "insufficient_data"}
    X, y = [], []
    start = max(30, len(draws) - 55)
    for target in range(start, len(draws)):
        prefix = draws[:target]
        experts, audit = base_experts(prefix, mode, train_tx=False)
        feats = meta_features(prefix, experts, audit)
        actual = set(draws[target].numbers)
        X.extend(feats)
        y.extend([1 if n in actual else 0 for n in range(1, MAX_NUMBER + 1)])
    model = XGBClassifier(n_estimators=180, max_depth=3, learning_rate=0.035, subsample=0.82, colsample_bytree=0.82, eval_metric="logloss", random_state=RANDOM_SEED, n_jobs=1, tree_method="hist")
    model.fit(np.asarray(X, dtype=np.float32), np.asarray(y, dtype=np.int32))
    experts, audit = base_experts(draws, mode, train_tx=False)
    pred = model.predict_proba(meta_features(draws, experts, audit))[:, 1]
    return minmax(np.r_[0, pred]), {"trained": True, "rows": len(y), "features": "physical, transformer_placeholder, graph, fourier, freq, gap"}


def full_experts(draws, mode):
    experts, audit = base_experts(draws, mode, train_tx=True)
    experts["xgboost"], audit["xgboost"] = train_xgb_scores(draws, mode)
    return experts, audit


def build_meta():
    class MLP(nn.Module):
        def __init__(self, dim):
            super().__init__()
            self.net = nn.Sequential(nn.Linear(dim, 32), nn.LayerNorm(32), nn.GELU(), nn.Dropout(META_DROPOUT), nn.Linear(32, 16), nn.LayerNorm(16), nn.GELU(), nn.Dropout(META_DROPOUT), nn.Linear(16, 1))
        def forward(self, x): return self.net(x).squeeze(-1)
    return MLP


def meta_training_rows(draws, mode, max_targets=8):
    X, y = [], []
    start = max(70, len(draws) - max_targets)
    for target in range(start, len(draws)):
        prefix = draws[:target]
        experts, audit = full_experts(prefix, mode)
        X.extend(meta_features(prefix, experts, audit))
        actual = set(draws[target].numbers)
        y.extend([1 if n in actual else 0 for n in range(1, MAX_NUMBER + 1)])
        cleanup()
    return np.asarray(X, dtype=np.float32), np.asarray(y, dtype=np.float32)


def train_meta_model(X, y):
    audit = {"model": "PyTorch MetaStackingMLP", "dropout": META_DROPOUT, "weight_decay": META_WEIGHT_DECAY, "patience": META_PATIENCE, "max_epochs": META_EPOCHS, "trained": False}
    if X is None or len(X) < 120:
        audit["fallback"] = "insufficient_rows"
        return None, audit
    dev = device()
    MLP = build_meta()
    model = MLP(X.shape[1]).to(dev)
    Xtr, ytr, Xv, yv, limited = train_val_split(X, y, min_val=56)
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=torch.tensor([(MAX_NUMBER - PICK_COUNT) / PICK_COUNT], device=dev))
    opt = torch.optim.AdamW(model.parameters(), lr=0.0018, weight_decay=META_WEIGHT_DECAY)
    Xt, yt = torch.tensor(Xtr, device=dev), torch.tensor(ytr, device=dev)
    Xvt = torch.tensor(Xv, device=dev) if Xv is not None else Xt
    yvt = torch.tensor(yv, device=dev) if yv is not None else yt
    best, state, stale = float("inf"), None, 0
    epochs = min(META_EPOCHS, 36 if limited else META_EPOCHS)
    for epoch in range(1, epochs + 1):
        model.train()
        perm = torch.randperm(len(Xt), device=dev)
        for s in range(0, len(Xt), min(256, len(Xt))):
            idx = perm[s:s + min(256, len(Xt))]
            opt.zero_grad(set_to_none=True)
            loss = loss_fn(model(Xt[idx]), yt[idx])
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
        model.eval()
        with torch.no_grad():
            val = float(loss_fn(model(Xvt), yvt).detach().cpu())
        if val + MIN_DELTA < best:
            best, stale, state = val, 0, {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
        else:
            stale += 1
            if stale >= META_PATIENCE:
                break
    if state:
        model.load_state_dict(state)
    audit.update({"trained": True, "validation_limited": bool(limited), "epochs_run": epoch, "best_epoch": max(1, epoch - stale), "best_val_loss": round(best, 8), "early_stopped": bool(stale >= META_PATIENCE), "architecture": [32, 16], "device": str(dev)})
    return model, audit


def meta_scores(model, X, experts):
    if model is None:
        raw = sum(experts[k] for k in EXPERT_NAMES) / len(EXPERT_NAMES)
        return minmax(raw)
    dev = next(model.parameters()).device
    model.eval()
    with torch.no_grad():
        pred = torch.sigmoid(model(torch.tensor(X, dtype=torch.float32, device=dev))).detach().cpu().numpy()
    return minmax(normalize(np.r_[0, pred]))


def top_order(score): return list(map(int, np.argsort(np.asarray(score)[1:])[::-1] + 1))


def walk_forward(draws, mode):
    start = max(max(70, TRANSFORMER_WINDOW + 45), len(draws) - OOS_STEPS)
    rows, leakage_rows, mses, hits = [], [], [], []
    for target in range(start, len(draws)):
        leak = assert_no_leakage("walk_forward_oos", target - 1, target, len(draws))
        leakage_rows.append(leak)
        prefix = draws[:target]
        print(f"OOS V4 {target - start + 1}/{len(draws) - start}: train<=T-1 reveal={draws[target].draw_id}")
        experts, audit = full_experts(prefix, mode)
        X, y = meta_training_rows(prefix, mode)
        meta, meta_audit = train_meta_model(X, y)
        score = meta_scores(meta, meta_features(prefix, experts, audit), experts)
        order = top_order(score)
        actual = set(draws[target].numbers)
        h = len(actual.intersection(order[:6]))
        y_true = np.zeros(MAX_NUMBER + 1)
        for n in actual:
            y_true[n] = 1
        mse = float(np.mean((y_true[1:] - score[1:]) ** 2))
        rows.append({"draw_id": draws[target].draw_id, "date": draws[target].date, "actual": list(draws[target].numbers), "predicted_top6": order[:6], "predicted_top10": order[:10], "hits": h, "hits_top10": len(actual.intersection(order[:10])), "mse": round(mse, 8), "meta_loss": meta_audit.get("best_val_loss"), "kl": round(audit["kl"], 6), "drift_detected": audit["drift_detected"], "leakage": leak})
        hits.append(h)
        mses.append(mse)
        del meta
        cleanup()
    return {"rows": rows, "avg_hits": float(np.mean(hits)) if hits else 0.0, "avg_mse": float(np.mean(mses)) if mses else 0.0, "last3_error_variance": float(np.var(mses[-3:])) if len(mses) >= 3 else 0.0}, leakage_rows


def structural(nums):
    nums = sorted(nums)
    evens = sum(n % 2 == 0 for n in nums)
    lows = sum(n <= 28 for n in nums)
    decades = len(set((n - 1) // 10 for n in nums))
    return max(0, min(1, 0.35 * (1 - abs(evens - 3) / 3) + 0.30 * (1 - abs(lows - 3) / 3) + 0.20 * decades / 6 + 0.15 * (1 if 110 <= sum(nums) <= 240 else 0.55)))


def monte_carlo(score, graph, total=MC_TOTAL):
    rng = np.random.default_rng(RANDOM_SEED)
    p = normalize(score)[1:]
    nums = np.arange(1, MAX_NUMBER + 1)
    best: Dict[Tuple[int, ...], Dict] = {}
    done = 0
    while done < total:
        batch = min(MC_BATCH, total - done)
        combos = np.vstack([rng.choice(nums, PICK_COUNT, replace=False, p=p) for _ in range(batch)])
        combos.sort(axis=1)
        vals = []
        for row in combos:
            arr = [int(x) for x in row]
            vals.append(0.82 * float(np.mean([score[n] for n in arr])) + 0.12 * graph_bonus(arr, graph) + 0.06 * structural(arr))
        vals = np.asarray(vals)
        for idx in np.argpartition(vals, -min(2500, batch))[-min(2500, batch):]:
            key = tuple(int(x) for x in combos[idx])
            if key not in best or float(vals[idx]) > best[key]["net_score"]:
                best[key] = {"numbers": list(key), "net_score": float(vals[idx]), "source": "v4_deep_stacking_montecarlo"}
        if len(best) > 40000:
            best = dict(sorted(best.items(), key=lambda kv: kv[1]["net_score"], reverse=True)[:12000])
        done += batch
        print(f"Monte Carlo V4 {done:,}/{total:,}", end="\r")
    print()
    return sorted(best.values(), key=lambda x: x["net_score"], reverse=True)


def explain_number(n, experts, audit, score):
    raw = {k: float(experts[k][n]) for k in EXPERT_NAMES}
    driver = max(raw.items(), key=lambda kv: kv[1])[0]
    labels = {"physical": "fisica de esferas", "transformer": "Transformer attention", "xgboost": "XGBoost tabular", "fourier": "micro-ciclos Fourier", "graph": "grafo de co-ocurrencia"}
    return {"number": n, "main_driver": driver, "main_driver_human": labels[driver], "reason": f"{labels[driver]} domina el score local dentro del buffer reciente", "meta_score": round(float(score[n] * 100), 6), "expert_raw": {k: round(v, 6) for k, v in raw.items()}, "effective_weight": round(float(audit["physics"]["effective"][n]), 4), "physics_bonus": round(float(audit["physics"]["bonus"][n]), 4), "uses_in_window": int(audit["physics"]["uses"][n])}


def enrich(item, experts, audit, score, mode):
    nums = item["numbers"]
    explanations = [explain_number(n, experts, audit, score) for n in nums]
    out = dict(item)
    out.update({"game_mode": mode, "score_kind": "v4_deep_stacking_meta_score", "score_percent": round(float(item["net_score"] * 100), 4), "number_explanations": explanations, "plain_route": " | ".join(f"{e['number']}: {e['main_driver_human']}" for e in explanations)})
    out["human_explanation"] = f"V4 Deep Stacking: MetaStackingMLP + expertos fisica/Transformer/XGBoost/Fourier/grafo, limitado al buffer reciente. Ranking informativo, no probabilidad real de ganar."
    return out


def manual_seed(experts, audit, score):
    return sorted([explain_number(n, experts, audit, score) for n in range(1, MAX_NUMBER + 1)], key=lambda x: x["meta_score"], reverse=True)


def portfolio(pool): return [dict(x, portfolio_rank=i + 1, portfolio_method="v4_deep_stacking_diversified") for i, x in enumerate(pool[:10])]


def run_pipeline():
    t0 = time.perf_counter()
    ensure_deps()
    seed_all()
    mode = choose_mode()
    buffer_size = choose_buffer()
    candidates = ["historial_revancha.csv", "revancha.csv", "historial.csv"] if mode == "revancha" else ["historial_melate.csv", "melate.csv", "historial.csv"]
    csv_path = next((c for c in candidates if Path(c).exists()), candidates[-1])
    all_draws = load_draws(csv_path)
    draws, discarded = truncate_recent(all_draws, buffer_size)
    print(f"Buffer reciente usado: {len(draws)}; descartados por olvido historico: {discarded}")
    wf, leakage = walk_forward(draws, mode)
    experts, audit = full_experts(draws, mode)
    X, y = meta_training_rows(draws, mode)
    meta, meta_audit = train_meta_model(X, y)
    score = meta_scores(meta, meta_features(draws, experts, audit), experts)
    ranked = monte_carlo(score, audit["graph"])
    pool = [enrich(x, experts, audit, score, mode) for x in ranked[:250]]
    result = {
        "last_update": datetime.now(timezone.utc).isoformat(),
        "source": "local_cruncher_v4_deep_stacking",
        "game_mode": mode,
        "csv_path": csv_path,
        "score_kind": "v4_deep_stacking_meta_score",
        "historical_forgetting": {"total_loaded_draws": len(all_draws), "discarded_old_draws": discarded, "recent_buffer_size": len(draws), "buffer_first_draw": draws[0].draw_id, "buffer_last_draw": draws[-1].draw_id, "principle": "solo buffer reciente truncado"},
        "procedure_log": "V4 usa walk-forward ciego, TransformerEncoder regularizado, grafo de co-ocurrencia y MetaStackingMLP sin leer historia previa al buffer.",
        "deep_stacking": {"experts": EXPERT_NAMES, "meta_model": "PyTorch MetaStackingMLP", "score_kind": "v4_deep_stacking_meta_score", "regularization": {"transformer_dropout": TX_DROPOUT, "transformer_weight_decay": TX_WEIGHT_DECAY, "meta_dropout": META_DROPOUT, "meta_weight_decay": META_WEIGHT_DECAY}},
        "transformer_audit": audit["transformer"],
        "graph_audit": {"decay": audit["graph"]["decay"], "max_edge": round(audit["graph"]["max_edge"], 8)},
        "meta_model_audit": meta_audit,
        "leakage_audit": {"passed": all(x["passed"] for x in leakage), "rows": leakage, "buffer_size": len(draws), "max_allowed_buffer": RECENT_BUFFER_MAX},
        "walk_forward": {"window_size": TRANSFORMER_WINDOW, "steps": len(wf["rows"]), "avg_hits": round(wf["avg_hits"], 6), "avg_mse": round(wf["avg_mse"], 8), "metrics": {"hit_rate": wf["avg_hits"] / PICK_COUNT, "mean_meta_loss": meta_audit.get("best_val_loss"), "last3_error_variance": wf["last3_error_variance"]}, "rows": wf["rows"]},
        "physics_summary": {"min_weight": round(audit["physics"]["min_weight"], 4), "max_weight": round(audit["physics"]["max_weight"], 4), "diff_weight": round(audit["physics"]["diff_weight"], 4), "regulatory_ok": audit["physics"]["regulatory_ok"], "avg_effective_weight": round(audit["physics"]["avg_effective"], 4)},
        "expert_scores_v4": {k: {str(n): round(float(experts[k][n] * 100), 6) for n in range(1, MAX_NUMBER + 1)} for k in EXPERT_NAMES},
        "expert_weights": {"meta": 1.0},
        "number_scores": {str(n): round(float(score[n] * 100), 6) for n in range(1, MAX_NUMBER + 1)},
        "manual_suggestion_seed": manual_seed(experts, audit, score),
        "model_portfolio": {"top10": portfolio(pool)},
        "generator_pool": pool,
        "top_combinations": pool[:10],
        "total_mc_evaluated": MC_TOTAL,
        "max_net_score_found": round(float(pool[0]["net_score"] if pool else 0), 8),
        "runtime_seconds": round(time.perf_counter() - t0, 2),
    }
    Path("resultados.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("resultados.json V4 generado.")


def main():
    print("MELATE LOCAL CRUNCHER V4 - DEEP STACKING")
    print("[1] Ejecutar pipeline V4 completo")
    print("[2] Inspeccionar resultados.json")
    choice = input("Opcion [1]: ").strip() or "1"
    if choice == "2":
        data = json.loads(Path("resultados.json").read_text(encoding="utf-8"))
        print(data.get("score_kind"), data.get("source"), len(data.get("top_combinations", [])))
    else:
        run_pipeline()


if __name__ == "__main__":
    main()
