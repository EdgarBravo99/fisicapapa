# -*- coding: utf-8 -*-
"""Summary gate for the controlled post-ranking layer."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from v4_post_ranking_controlled_comparison import build_controlled_comparison
from v4_post_ranking_controlled_layer import build_controlled_layer, load_json


VERSION = "V4.4-controlled-post-ranking-summary"
CANDIDATE_VARIANT = "top6_preserved_plus_frequency_no_duplicates"
SMOOTHING_VARIANT = "frequency_window_15"
POLICY = "always_repair__min_history_15"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_controlled_summary(
    layer_path: str | Path = "v4_post_ranking_controlled_layer_output.json",
    comparison_path: str | Path = "v4_post_ranking_controlled_comparison.json",
    validation_summary_path: str | Path = "v4_post_ranking_full_validation_summary.json",
    audit_state_path: str | Path = "v4_audit_state.json",
    layer_report: dict[str, Any] | None = None,
    comparison_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    warnings: list[str] = []
    if layer_report is None:
        layer_report, layer_error = load_json(layer_path)
        if layer_error:
            warnings.append(layer_error)
            layer_report = build_controlled_layer(validation_summary_path=validation_summary_path)
    if comparison_report is None:
        comparison_report, comparison_error = load_json(comparison_path)
        if comparison_error:
            warnings.append(comparison_error)
            comparison_report = build_controlled_comparison(layer_report=layer_report, validation_summary_path=validation_summary_path)

    validation, validation_error = load_json(validation_summary_path)
    if validation_error:
        warnings.append(validation_error)

    layer_status = layer_report.get("status") if layer_report else "blocked"
    candidate_status = validation.get("candidate_status") if validation else None
    production_ready = False
    prior_should_remain_blocked = True
    top6_ok = comparison_report.get("top6_preservation_ok") is True if comparison_report else False
    official_untouched = layer_report.get("official_results_untouched") is True if layer_report else False
    gate_ready = (
        candidate_status == "ready_for_controlled_layer"
        and layer_status == "ready"
        and top6_ok
        and official_untouched
        and validation is not None
        and validation.get("production_ready") is False
        and validation.get("prior_should_remain_blocked") is True
        and validation.get("future_controlled_layer_candidate") is True
    )
    if gate_ready:
        status = "controlled_layer_ready"
        reason = "Controlled layer is ready for review-only app display; official V4.2 output remains untouched."
    elif layer_status == "insufficient_data":
        status = "insufficient_data"
        reason = "Controlled layer has insufficient replay-memory context for the approved window."
    else:
        status = "controlled_layer_blocked"
        reason = "Controlled layer blocked because one or more PR #29 or safety gates failed."

    return {
        "version": VERSION,
        "generated_at": utc_now(),
        "mode": "controlled_experiment",
        "controlled_layer_status": status,
        "candidate_variant": validation.get("candidate_variant", CANDIDATE_VARIANT) if validation else CANDIDATE_VARIANT,
        "smoothing_variant": validation.get("best_smoothing_variant", SMOOTHING_VARIANT) if validation else SMOOTHING_VARIANT,
        "policy": validation.get("best_policy", POLICY) if validation else POLICY,
        "usable_in_app": status == "controlled_layer_ready",
        "recommended_usage": "review_only",
        "production_ready": production_ready,
        "prior_should_remain_blocked": prior_should_remain_blocked,
        "official_results_untouched": official_untouched,
        "reason": reason,
        "must_not_do": [
            "do not replace resultados.json",
            "do not activate replay prior",
            "do not claim probability of winning",
            "do not mutate official scores",
        ],
        "recommended_next_evidence": [
            "future unseen validation after real draws",
            "continued comparison against original/frequency/random",
        ],
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build controlled post-ranking summary gate.")
    parser.add_argument("--layer", default="v4_post_ranking_controlled_layer_output.json")
    parser.add_argument("--comparison", default="v4_post_ranking_controlled_comparison.json")
    parser.add_argument("--validation-summary", default="v4_post_ranking_full_validation_summary.json")
    parser.add_argument("--audit-state", default="v4_audit_state.json")
    parser.add_argument("--output", default="v4_post_ranking_controlled_summary.json")
    args = parser.parse_args()

    report = build_controlled_summary(
        layer_path=args.layer,
        comparison_path=args.comparison,
        validation_summary_path=args.validation_summary,
        audit_state_path=args.audit_state,
    )
    Path(args.output).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[controlled-summary] wrote {args.output} status={report.get('controlled_layer_status')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
