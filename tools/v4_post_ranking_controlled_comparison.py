# -*- coding: utf-8 -*-
"""Compare official V4.2 ranking with controlled post-ranking output."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from v4_post_ranking_controlled_layer import build_controlled_layer, derive_original_ranking, load_json


VERSION = "V4.4-controlled-post-ranking-comparison"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _overlap(left: list[int], right: list[int], k: int) -> int:
    return len(set(left[:k]) & set(right[:k]))


def build_controlled_comparison(
    layer_path: str | Path = "v4_post_ranking_controlled_layer_output.json",
    results_path: str | Path = "resultados.json",
    validation_summary_path: str | Path = "v4_post_ranking_full_validation_summary.json",
    layer_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    warnings: list[str] = []
    if layer_report is None:
        layer_report, layer_error = load_json(layer_path)
        if layer_error:
            warnings.append(layer_error)
            layer_report = build_controlled_layer(input_path=results_path, validation_summary_path=validation_summary_path)

    results, results_error = load_json(results_path)
    validation, validation_error = load_json(validation_summary_path)
    if results_error:
        warnings.append(results_error)
    if validation_error:
        warnings.append(validation_error)

    official_rank: list[int] = []
    if results:
        official_rank, _, ranking_warnings = derive_original_ranking(results)
        warnings.extend(ranking_warnings)
    controlled_rank = layer_report.get("controlled_top40_numbers") if isinstance(layer_report, dict) else []
    if not isinstance(controlled_rank, list):
        controlled_rank = []
    controlled_rank = [int(number) for number in controlled_rank if isinstance(number, int) or str(number).isdigit()]

    controlled_available = bool(layer_report and layer_report.get("status") == "ready" and controlled_rank)
    top6_preservation_ok = bool(layer_report and layer_report.get("diff_vs_original", {}).get("preserved_top6") is True)
    validation_status = {
        "candidate_status": validation.get("candidate_status") if validation else None,
        "overfit_risk": validation.get("overfit_risk") if validation else None,
        "production_ready": False,
        "prior_should_remain_blocked": True,
    }
    if validation and validation.get("production_ready") is not False:
        warnings.append("Validation summary production_ready is not false; controlled comparison remains review-only.")
    if validation and validation.get("prior_should_remain_blocked") is not True:
        warnings.append("Validation summary prior_should_remain_blocked is not true; controlled comparison remains blocked.")

    official_top20 = set(official_rank[:20])
    controlled_top20 = set(controlled_rank[:20])
    return {
        "version": VERSION,
        "generated_at": utc_now(),
        "mode": "controlled_experiment",
        "controlled_layer_available": controlled_available,
        "top6_preservation_ok": top6_preservation_ok,
        "overlap": {
            "top6": _overlap(official_rank, controlled_rank, 6),
            "top10": _overlap(official_rank, controlled_rank, 10),
            "top20": _overlap(official_rank, controlled_rank, 20),
        },
        "added_numbers_top20": sorted(controlled_top20 - official_top20),
        "removed_numbers_top20": sorted(official_top20 - controlled_top20),
        "validation_status": validation_status,
        "recommended_usage": "review_only",
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare controlled post-ranking output with official ranking.")
    parser.add_argument("--layer", default="v4_post_ranking_controlled_layer_output.json")
    parser.add_argument("--input", default="resultados.json")
    parser.add_argument("--validation-summary", default="v4_post_ranking_full_validation_summary.json")
    parser.add_argument("--output", default="v4_post_ranking_controlled_comparison.json")
    args = parser.parse_args()

    report = build_controlled_comparison(
        layer_path=args.layer,
        results_path=args.input,
        validation_summary_path=args.validation_summary,
    )
    Path(args.output).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[controlled-comparison] wrote {args.output} available={report.get('controlled_layer_available')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
