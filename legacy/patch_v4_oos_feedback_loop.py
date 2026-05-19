#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V4.2 OOS fold-by-fold feedback loop patch."""
from pathlib import Path

TARGET = Path("local_cruncher_v4_deep_stacking.py")
if not TARGET.exists():
    raise SystemExit("local_cruncher_v4_deep_stacking.py not found")

s = TARGET.read_text(encoding="utf-8")
if "def walk_forward_oos_feedback_v42" in s:
    print("OK: V4.2 OOS feedback patch already applied")
    raise SystemExit(0)

block = r'''

# ─────────────────────────────────────────────────────────────
# V4.2 FOLD-BY-FOLD OOS FEEDBACK LOOP PATCH
# ─────────────────────────────────────────────────────────────

def _append_oos_feedback_v42(base_X, base_y, feedback_X_parts, feedback_y_parts):
    if not feedback_X_parts:
        return base_X, base_y, {"enabled": True, "feedback_rows_used": 0, "feedback_folds_used": 0}
    fx = np.vstack(feedback_X_parts).astype(np.float32)
    fy = np.concatenate(feedback_y_parts).astype(np.float32)
    X = np.vstack([base_X, fx]).astype(np.float32)
    y = np.concatenate([base_y, fy]).astype(np.float32)
    return X, y, {
        "enabled": True,
        "feedback_rows_used": int(len(fy)),
        "feedback_folds_used": int(len(feedback_y_parts)),
        "feedback_positive_hits_used": int(np.sum(fy)),
    }


def _fold_hit_labels_v42(actual_numbers):
    labels = np.zeros(MAX_NUMBER, dtype=np.float32)
    for n in actual_numbers:
        if 1 <= int(n) <= MAX_NUMBER:
            labels[int(n) - 1] = 1.0
    return labels


def walk_forward_oos_feedback_v42(draws, mode):
    start = max(max(70, TRANSFORMER_WINDOW + 45), len(draws) - OOS_STEPS)
    rows, leakage_rows, mses, hits6, hits10 = [], [], [], [], []
    oos_scores, oos_hits = [], []
    feedback_X_parts, feedback_y_parts = [], []

    for target in range(start, len(draws)):
        leak = assert_no_leakage("walk_forward_oos_v42_feedback", target - 1, target, len(draws))
        leakage_rows.append(leak)
        prefix = draws[:target]
        print(f"OOS V4.2 feedback {target - start + 1}/{len(draws) - start}: train<=T-1 reveal={draws[target].draw_id} feedback_folds={len(feedback_y_parts)}")

        experts, audit = full_experts(prefix, mode)
        base_X, base_y = meta_training_rows(prefix, mode)
        X, y, fb_audit = _append_oos_feedback_v42(base_X, base_y, feedback_X_parts, feedback_y_parts)
        meta, meta_audit = train_meta_model(X, y)

        live_X = meta_features(prefix, experts, audit)
        score = meta_scores(meta, live_X, experts)
        order = top_order(score)
        actual = set(draws[target].numbers)
        h6 = len(actual.intersection(order[:6]))
        h10 = len(actual.intersection(order[:10]))

        y_true = np.zeros(MAX_NUMBER + 1, dtype=np.float64)
        for n in actual:
            y_true[n] = 1.0
        mse = float(np.mean((y_true[1:] - score[1:]) ** 2))

        oos_scores.extend([float(score[n]) for n in range(1, MAX_NUMBER + 1)])
        oos_hits.extend([1.0 if n in actual else 0.0 for n in range(1, MAX_NUMBER + 1)])

        # Feedback real: el fold T solo se añade DESPUÉS de evaluarlo, para alimentar T+1.
        feedback_X_parts.append(np.asarray(live_X, dtype=np.float32))
        feedback_y_parts.append(_fold_hit_labels_v42(draws[target].numbers))

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
            "feedback_rows_used": fb_audit["feedback_rows_used"],
            "feedback_folds_used": fb_audit["feedback_folds_used"],
            "feedback_positive_hits_used": fb_audit.get("feedback_positive_hits_used", 0),
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
        "feedback_loop": {
            "enabled": True,
            "type": "fold_by_fold_oos_error_replay",
            "description": "Cada sorteo OOS revelado añade 56 filas feature/hit al entrenamiento del MetaMLP del fold siguiente.",
            "total_feedback_folds_generated": int(len(feedback_y_parts)),
            "total_feedback_rows_generated": int(sum(len(x) for x in feedback_y_parts)),
            "anti_leakage": "El fold T usa solo feedback de folds anteriores ya revelados; el feedback de T se añade después de evaluar T.",
        },
    }, leakage_rows


def walk_forward(draws, mode):
    return walk_forward_oos_feedback_v42(draws, mode)

'''

marker = "\ndef main():\n"
if marker not in s:
    raise SystemExit("Could not find def main() insertion point")
s = s.replace(marker, block + marker, 1)

s = s.replace(
    '"hit_aware_training": {\n            "enabled": True,',
    '"hit_aware_training": {\n            "enabled": True,\n            "fold_by_fold_feedback_enabled": bool(wf.get("feedback_loop", {}).get("enabled", False)),\n            "feedback_loop": wf.get("feedback_loop", {}),',
)
s = s.replace(
    '"walk_forward": {"window_size": TRANSFORMER_WINDOW, "steps": len(wf["rows"]),',
    '"walk_forward": {"window_size": TRANSFORMER_WINDOW, "steps": len(wf["rows"]), "feedback_loop": wf.get("feedback_loop", {}),',
)

TARGET.write_text(s, encoding="utf-8")
print("OK: V4.2 fold-by-fold OOS feedback patch applied")
