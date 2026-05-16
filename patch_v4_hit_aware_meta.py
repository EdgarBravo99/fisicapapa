#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V4.1 hit-aware MetaStacking patch.

Aplica sin cambiar la arquitectura base:
- MetaStackingMLP sigue siendo el mismo MLP.
- TransformerEncoder y expertos base no se modifican.
- Se cambia el objetivo del MetaMLP a BCE+MSE hit-aware.
- Early stopping se decide por hit-rate Top6/Top10 en validación.
- Se agrega calibración isotónica sobre scores OOS vs hits reales.
- La búsqueda exhaustiva recibe probabilidades calibradas de hit.
"""
from __future__ import annotations

from pathlib import Path

TARGET = Path("local_cruncher_v4_deep_stacking.py")
if not TARGET.exists():
    raise SystemExit("local_cruncher_v4_deep_stacking.py not found")

s = TARGET.read_text(encoding="utf-8")
if "def train_meta_model_hitaware_v41" in s:
    print("OK: V4.1 hit-aware patch already applied")
    raise SystemExit(0)

block = r'''

# ─────────────────────────────────────────────────────────────
# V4.1 HIT-AWARE META STACKING PATCH
# ─────────────────────────────────────────────────────────────

def _ensure_optuna_v41():
    try:
        import optuna
        return optuna
    except Exception:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "optuna", "--quiet", "--disable-pip-version-check"])
        import optuna
        return optuna


def _group_split_56_v41(X, y, min_val_groups=2):
    groups = max(1, len(y) // MAX_NUMBER)
    usable = groups * MAX_NUMBER
    X = X[:usable]
    y = y[:usable]
    if groups <= min_val_groups + 1:
        return X, y, X, y, True
    val_groups = max(min_val_groups, min(8, max(2, groups // 5)))
    split = (groups - val_groups) * MAX_NUMBER
    return X[:split], y[:split], X[split:], y[split:], False


def _topk_hits_from_vector_v41(scores, y_group):
    order = list(map(int, np.argsort(np.asarray(scores))[::-1] + 1))
    actual = {i + 1 for i, v in enumerate(y_group) if float(v) > 0.5}
    return len(actual.intersection(order[:6])), len(actual.intersection(order[:10])), order


def _validation_hit_metric_v41(model, Xv, yv, dev):
    model.eval()
    with torch.no_grad():
        logits = model(torch.tensor(Xv, dtype=torch.float32, device=dev))
        probs = torch.sigmoid(logits).detach().cpu().numpy()
    groups = len(yv) // MAX_NUMBER
    if groups <= 0:
        return 0.0, 0.0, 0.0
    h6, h10 = [], []
    for g in range(groups):
        a = g * MAX_NUMBER
        b = a + MAX_NUMBER
        x6, x10, _ = _topk_hits_from_vector_v41(probs[a:b], yv[a:b])
        h6.append(x6)
        h10.append(x10)
    avg6 = float(np.mean(h6)) if h6 else 0.0
    avg10 = float(np.mean(h10)) if h10 else 0.0
    # Normalizado por 6 positivos reales. Sirve para early stopping/Optuna.
    metric = 0.5 * (avg6 / PICK_COUNT) + 0.5 * (avg10 / PICK_COUNT)
    return metric, avg6, avg10


def _fit_meta_once_v41(Xtr, ytr, Xv, yv, hit_weight, epochs, patience, limited=False):
    dev = device()
    MLP = build_meta()
    model = MLP(Xtr.shape[1]).to(dev)
    pos_weight = torch.tensor([(MAX_NUMBER - PICK_COUNT) / PICK_COUNT], dtype=torch.float32, device=dev)
    bce = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
    mse = nn.MSELoss()
    opt = torch.optim.AdamW(model.parameters(), lr=0.0018, weight_decay=META_WEIGHT_DECAY)
    Xt = torch.tensor(Xtr, dtype=torch.float32, device=dev)
    yt = torch.tensor(ytr, dtype=torch.float32, device=dev)
    Xv_np = np.asarray(Xv, dtype=np.float32)
    yv_np = np.asarray(yv, dtype=np.float32)
    best_metric, best_state, stale, best_epoch = -1.0, None, 0, 0
    run_epochs = min(epochs, 36 if limited else epochs)
    batch = min(256, len(Xt))
    for epoch in range(1, run_epochs + 1):
        model.train()
        perm = torch.randperm(len(Xt), device=dev)
        for st in range(0, len(Xt), batch):
            idx = perm[st:st + batch]
            opt.zero_grad(set_to_none=True)
            logits = model(Xt[idx])
            probs = torch.sigmoid(logits)
            loss = float(hit_weight) * bce(logits, yt[idx]) + (1.0 - float(hit_weight)) * mse(probs, yt[idx])
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
        val_metric, _, _ = _validation_hit_metric_v41(model, Xv_np, yv_np, dev)
        if val_metric > best_metric + 1e-6:
            best_metric = val_metric
            best_epoch = epoch
            stale = 0
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
        else:
            stale += 1
            if stale >= patience:
                break
    if best_state:
        model.load_state_dict(best_state)
    final_metric, final_h6, final_h10 = _validation_hit_metric_v41(model, Xv_np, yv_np, dev)
    return model, {
        "best_val_hit_metric": round(float(best_metric), 8),
        "final_val_hit_metric": round(float(final_metric), 8),
        "val_hits_top6": round(float(final_h6), 6),
        "val_hits_top10": round(float(final_h10), 6),
        "best_epoch": int(best_epoch),
        "epochs_run": int(epoch),
        "early_stopped": bool(stale >= patience),
    }


def _tune_hit_weight_v41(Xtr, ytr, Xv, yv, limited=False):
    trials = env_int("MELATE_V4_HIT_OPTUNA_TRIALS", 12, 1, 80)
    if trials <= 1:
        return 0.60, {"enabled": False, "trials": 0, "best_hit_weight": 0.60}
    optuna = _ensure_optuna_v41()
    def objective(trial):
        hit_weight = trial.suggest_float("hit_weight", 0.4, 0.8)
        model, audit = _fit_meta_once_v41(
            Xtr, ytr, Xv, yv,
            hit_weight=hit_weight,
            epochs=min(38, META_EPOCHS),
            patience=max(3, min(5, META_PATIENCE)),
            limited=limited,
        )
        metric = float(audit.get("final_val_hit_metric", 0.0))
        del model
        cleanup()
        # El prompt lo define como minimizar el negativo del hit-rate.
        return -metric
    sampler = optuna.samplers.TPESampler(seed=RANDOM_SEED + 41)
    study = optuna.create_study(direction="minimize", sampler=sampler)
    study.optimize(objective, n_trials=trials, show_progress_bar=False)
    best = float(study.best_params.get("hit_weight", 0.60))
    return best, {
        "enabled": True,
        "trials": int(trials),
        "best_hit_weight": round(best, 6),
        "best_objective": round(float(study.best_value), 8),
        "objective": "minimize -(0.5*hit_rate_top6 + 0.5*hit_rate_top10)",
    }


def train_meta_model_hitaware_v41(X, y):
    audit = {
        "model": "PyTorch MetaStackingMLP",
        "training_mode": "V4.1 hit-aware BCE+MSE",
        "loss": "hit_weight*BCEWithLogits(pos_weight=50/6)+(1-hit_weight)*MSE(sigmoid(logit),hit_label)",
        "early_stopping_metric": "0.5*val_hit_rate_top6 + 0.5*val_hit_rate_top10",
        "dropout": META_DROPOUT,
        "weight_decay": META_WEIGHT_DECAY,
        "patience": META_PATIENCE,
        "max_epochs": META_EPOCHS,
        "trained": False,
    }
    if X is None or len(X) < 120:
        audit["fallback"] = "insufficient_rows"
        return None, audit
    X = np.asarray(X, dtype=np.float32)
    y = np.asarray(y, dtype=np.float32)
    Xtr, ytr, Xv, yv, limited = _group_split_56_v41(X, y, min_val_groups=2)
    best_hit_weight, optuna_audit = _tune_hit_weight_v41(Xtr, ytr, Xv, yv, limited=limited)
    model, fit_audit = _fit_meta_once_v41(
        Xtr, ytr, Xv, yv,
        hit_weight=best_hit_weight,
        epochs=META_EPOCHS,
        patience=max(META_PATIENCE, 8),
        limited=limited,
    )
    audit.update({
        "trained": True,
        "validation_limited": bool(limited),
        "hit_weight": round(float(best_hit_weight), 6),
        "mse_weight": round(float(1.0 - best_hit_weight), 6),
        "architecture": [32, 16],
        "device": str(device()),
        "optuna": optuna_audit,
        **fit_audit,
    })
    return model, audit


def train_meta_model(X, y):
    return train_meta_model_hitaware_v41(X, y)


def _raw_meta_probabilities_v41(model, X, experts):
    if model is None:
        raw = sum(experts[k] for k in EXPERT_NAMES) / len(EXPERT_NAMES)
        return minmax(raw)
    dev = next(model.parameters()).device
    model.eval()
    with torch.no_grad():
        pred = torch.sigmoid(model(torch.tensor(X, dtype=torch.float32, device=dev))).detach().cpu().numpy()
    out = np.zeros(MAX_NUMBER + 1, dtype=np.float64)
    out[1:] = pred
    return np.nan_to_num(out, nan=0.0, posinf=1.0, neginf=0.0)


def meta_scores(model, X, experts):
    # Mantiene firma histórica, pero ahora devuelve probabilidad cruda de hit en vez de ranking normalizado arbitrario.
    return _raw_meta_probabilities_v41(model, X, experts)


def calibrate_hit_probabilities_v41(wf):
    try:
        from sklearn.isotonic import IsotonicRegression
        from sklearn.metrics import r2_score, brier_score_loss
    except Exception:
        return None, {"enabled": False, "reason": "sklearn calibration imports failed", "calibration_r2": 0.0}
    scores = np.asarray(wf.get("oos_scores", []), dtype=np.float64)
    hits = np.asarray(wf.get("oos_hits", []), dtype=np.float64)
    if len(scores) < 112 or len(np.unique(hits)) < 2:
        return None, {"enabled": False, "reason": "insufficient_oos_calibration_rows", "calibration_r2": 0.0, "rows": int(len(scores))}
    iso = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
    iso.fit(scores, hits)
    pred = iso.predict(scores)
    r2 = float(r2_score(hits, pred)) if len(hits) else 0.0
    brier = float(brier_score_loss(hits, pred)) if len(hits) else 0.0
    return iso, {
        "enabled": True,
        "method": "IsotonicRegression(out_of_bounds='clip')",
        "rows": int(len(scores)),
        "positives": int(np.sum(hits)),
        "calibration_r2": round(r2, 8),
        "brier_score": round(brier, 8),
        "mean_raw_score": round(float(np.mean(scores)), 8),
        "mean_calibrated_prob": round(float(np.mean(pred)), 8),
    }


def apply_hit_calibrator_v41(score, calibrator):
    arr = np.asarray(score, dtype=np.float64).copy()
    out = np.zeros(MAX_NUMBER + 1, dtype=np.float64)
    if calibrator is None:
        out[1:] = np.clip(arr[1:], 0.0, 1.0)
    else:
        out[1:] = np.clip(calibrator.predict(arr[1:]), 0.0, 1.0)
    return out


def walk_forward(draws, mode):
    start = max(max(70, TRANSFORMER_WINDOW + 45), len(draws) - OOS_STEPS)
    rows, leakage_rows, mses, hits6, hits10 = [], [], [], [], []
    oos_scores, oos_hits = [], []
    for target in range(start, len(draws)):
        leak = assert_no_leakage("walk_forward_oos", target - 1, target, len(draws))
        leakage_rows.append(leak)
        prefix = draws[:target]
        print(f"OOS V4.1 hit-aware {target - start + 1}/{len(draws) - start}: train<=T-1 reveal={draws[target].draw_id}")
        experts, audit = full_experts(prefix, mode)
        X, y = meta_training_rows(prefix, mode)
        meta, meta_audit = train_meta_model(X, y)
        score = meta_scores(meta, meta_features(prefix, experts, audit), experts)
        order = top_order(score)
        actual = set(draws[target].numbers)
        h6 = len(actual.intersection(order[:6]))
        h10 = len(actual.intersection(order[:10]))
        y_true = np.zeros(MAX_NUMBER + 1)
        for n in actual:
            y_true[n] = 1
        mse = float(np.mean((y_true[1:] - score[1:]) ** 2))
        oos_scores.extend([float(score[n]) for n in range(1, MAX_NUMBER + 1)])
        oos_hits.extend([1.0 if n in actual else 0.0 for n in range(1, MAX_NUMBER + 1)])
        rows.append({
            "draw_id": draws[target].draw_id,
            "date": draws[target].date,
            "actual": list(draws[target].numbers),
            "predicted_top6": order[:6],
            "predicted_top10": order[:10],
            "hits": h6,
            "hits_top6": h6,
            "hits_top10": h10,
            "mse": round(mse, 8),
            "meta_loss": meta_audit.get("best_val_loss"),
            "val_hit_metric": meta_audit.get("final_val_hit_metric"),
            "hit_weight": meta_audit.get("hit_weight"),
            "kl": round(audit["kl"], 6),
            "drift_detected": audit["drift_detected"],
            "leakage": leak,
        })
        hits6.append(h6)
        hits10.append(h10)
        mses.append(mse)
        del meta
        cleanup()
    return {
        "rows": rows,
        "avg_hits": float(np.mean(hits6)) if hits6 else 0.0,
        "avg_hits_top6": float(np.mean(hits6)) if hits6 else 0.0,
        "avg_hits_top10": float(np.mean(hits10)) if hits10 else 0.0,
        "avg_mse": float(np.mean(mses)) if mses else 0.0,
        "last3_error_variance": float(np.var(mses[-3:])) if len(mses) >= 3 else 0.0,
        "oos_scores": oos_scores,
        "oos_hits": oos_hits,
    }, leakage_rows


def _best_numbers_by_decade_v41(experts, audit, score):
    groups = [("1-9", range(1, 10)), ("10-19", range(10, 20)), ("20-29", range(20, 30)), ("30-39", range(30, 40)), ("40-49", range(40, 50)), ("50-56", range(50, 57))]
    rows = []
    for label, values in groups:
        cands = []
        for n in values:
            exp = explain_number(n, experts, audit, score)
            cands.append({
                "decade": label,
                "number": int(n),
                "score": round(float(score[n] * 100), 6),
                "main_driver": exp.get("main_driver"),
                "main_driver_human": exp.get("main_driver_human"),
                "reason": exp.get("reason"),
                "expert_raw": exp.get("expert_raw", {}),
                "effective_weight": exp.get("effective_weight"),
                "physics_bonus": exp.get("physics_bonus"),
                "uses_in_window": exp.get("uses_in_window"),
            })
        cands.sort(key=lambda x: x["score"], reverse=True)
        best = cands[0]
        best["alternatives"] = cands[1:4]
        rows.append(best)
    return rows


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
    calibrator, calibration_audit = calibrate_hit_probabilities_v41(wf)

    experts, audit = full_experts(draws, mode)
    X, y = meta_training_rows(draws, mode)
    meta, meta_audit = train_meta_model(X, y)
    raw_score = meta_scores(meta, meta_features(draws, experts, audit), experts)
    score = apply_hit_calibrator_v41(raw_score, calibrator)

    print("V4.1 scoring final: exhaustive_search usa calibrated_hit_prob como señal principal")
    ranked = exhaustive_search(score, audit["graph"])
    pool = [enrich(x, experts, audit, score, mode) for x in ranked[:250]]

    avg6 = float(wf.get("avg_hits_top6", wf.get("avg_hits", 0.0)))
    avg10 = float(wf.get("avg_hits_top10", 0.0))
    cal_r2 = float(calibration_audit.get("calibration_r2", 0.0) or 0.0)
    validation_targets = {
        "avg_hits_top6_target": 1.0,
        "avg_hits_top10_target": 1.5,
        "calibration_r2_target": 0.05,
        "avg_hits_top6_actual": round(avg6, 6),
        "avg_hits_top10_actual": round(avg10, 6),
        "calibration_r2_actual": round(cal_r2, 8),
        "passed": bool(avg6 > 1.0 and avg10 > 1.5 and cal_r2 > 0.05),
    }

    result = {
        "last_update": datetime.now(timezone.utc).isoformat(),
        "source": "local_cruncher_v4_deep_stacking",
        "model_version": "V4.1-hit-aware",
        "game_mode": mode,
        "game_label": "Melate" if mode == "melate" else "Revancha",
        "csv_path": csv_path,
        "score_kind": "optuna_weighted_net_score",
        "v4_score_kind": "v4_hit_aware_calibrated_hit_probability",
        "historical_forgetting": {"total_loaded_draws": len(all_draws), "discarded_old_draws": discarded, "recent_buffer_size": len(draws), "buffer_first_draw": draws[0].draw_id, "buffer_last_draw": draws[-1].draw_id, "principle": "solo buffer reciente truncado"},
        "procedure_log": "V4.1 usa walk-forward ciego, TransformerEncoder regularizado, grafo de co-ocurrencia y MetaStackingMLP con hit-aware loss + calibración isotónica. No lee historia previa al buffer.",
        "hit_aware_training": {
            "enabled": True,
            "loss": "hit_weight*BCEWithLogits(pos_weight=50/6)+(1-hit_weight)*MSE(sigmoid(logit),hit_label)",
            "early_stopping_metric": "0.5*val_hit_rate_top6 + 0.5*val_hit_rate_top10",
            "selection_score": "sum(calibrated_hit_prob[n] for n in combo) with graph/structure tie-breakers in exhaustive_search",
            "hit_weight": meta_audit.get("hit_weight"),
            "mse_weight": meta_audit.get("mse_weight"),
            "optuna": meta_audit.get("optuna", {}),
            "validation_targets": validation_targets,
        },
        "calibration": calibration_audit,
        "calibration_r2": cal_r2,
        "deep_stacking": {"experts": EXPERT_NAMES, "meta_model": "PyTorch MetaStackingMLP", "score_kind": "v4_hit_aware_calibrated_hit_probability", "regularization": {"transformer_dropout": TX_DROPOUT, "transformer_weight_decay": TX_WEIGHT_DECAY, "meta_dropout": META_DROPOUT, "meta_weight_decay": META_WEIGHT_DECAY}},
        "transformer_audit": audit["transformer"],
        "graph_audit": {"decay": audit["graph"].get("decay"), "max_edge": round(float(audit["graph"].get("max_edge", 0.0)), 8)},
        "meta_model_audit": meta_audit,
        "leakage_audit": {"passed": all(x["passed"] for x in leakage), "rows": leakage, "buffer_size": len(draws), "max_allowed_buffer": RECENT_BUFFER_MAX},
        "walk_forward": {"window_size": TRANSFORMER_WINDOW, "steps": len(wf["rows"]), "avg_hits": round(avg6, 6), "avg_hits_top6": round(avg6, 6), "avg_hits_top10": round(avg10, 6), "avg_mse": round(float(wf["avg_mse"]), 8), "metrics": {"hit_rate": avg6 / PICK_COUNT, "hit_rate_top10": avg10 / PICK_COUNT, "mean_meta_loss": meta_audit.get("best_val_loss"), "val_hit_metric": meta_audit.get("final_val_hit_metric"), "last3_error_variance": wf["last3_error_variance"]}, "rows": wf["rows"]},
        "physics_summary": {"min_weight": round(audit["physics"]["min_weight"], 4), "max_weight": round(audit["physics"]["max_weight"], 4), "diff_weight": round(audit["physics"]["diff_weight"], 4), "regulatory_ok": audit["physics"]["regulatory_ok"], "avg_effective_weight": round(audit["physics"]["avg_effective"], 4)},
        "expert_scores_v4": {k: {str(n): round(float(experts[k][n] * 100), 6) for n in range(1, MAX_NUMBER + 1)} for k in EXPERT_NAMES},
        "expert_weights": {"meta": 1.0, "hit_weight": float(meta_audit.get("hit_weight", 0.6)), "mse_weight": float(meta_audit.get("mse_weight", 0.4))},
        "number_scores_raw_v4": {str(n): round(float(raw_score[n] * 100), 6) for n in range(1, MAX_NUMBER + 1)},
        "calibrated_hit_probabilities": {str(n): round(float(score[n]), 8) for n in range(1, MAX_NUMBER + 1)},
        "number_scores": {str(n): round(float(score[n] * 100), 6) for n in range(1, MAX_NUMBER + 1)},
        "manual_suggestion_seed": manual_seed(experts, audit, score),
        "best_numbers_by_decade": _best_numbers_by_decade_v41(experts, audit, score),
        "model_portfolio": {"method": "v4_hit_aware_calibrated_top10", "top10": portfolio(pool)},
        "generator_pool": pool,
        "top_combinations": pool[:10],
        "total_mc_evaluated": globals().get("EXHAUSTIVE_TOTAL", MC_TOTAL),
        "search_mode": "exhaustive_full_space_calibrated_hit_prob",
        "max_net_score_found": round(float(pool[0]["net_score"] if pool else 0), 8),
        "runtime_seconds": round(time.perf_counter() - t0, 2),
    }
    Path("resultados.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("resultados.json V4.1 hit-aware generado.")
    print(f"avg_hits_top6={avg6:.4f} avg_hits_top10={avg10:.4f} calibration_r2={cal_r2:.6f}")

'''

marker = "\ndef main():\n"
if marker not in s:
    raise SystemExit("Could not find def main() insertion point")

s = s.replace(marker, block + marker, 1)
TARGET.write_text(s, encoding="utf-8")
print("OK: V4.1 hit-aware meta patch applied")
