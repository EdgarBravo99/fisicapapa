# -*- coding: utf-8 -*-
"""Combine replay failure diagnostics into a conservative signal summary."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from v4_benchmark_hardening import utc_now

VERSION = "V4.4-signal-decomposition-summary"


def _load(path: str | Path) -> dict[str, Any] | None:
    file_path = Path(path)
    if not file_path.exists():
        return None
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def build_signal_summary(
    windows_path: str = "v4_replay_window_diagnostics.json",
    ranking_path: str = "v4_ranking_inversion_audit.json",
    frequency_path: str = "v4_frequency_dominance_audit.json",
    draw_report_path: str = "v4_draw_failure_report.json",
    benchmark_summary_path: str = "v4_benchmark_summary.json",
) -> dict[str, Any]:
    windows = _load(windows_path)
    ranking = _load(ranking_path)
    frequency = _load(frequency_path)
    draw_report = _load(draw_report_path)
    benchmark = _load(benchmark_summary_path)
    missing = [
        name
        for name, data in {
            "windows": windows,
            "ranking": ranking,
            "frequency": frequency,
            "draw_report": draw_report,
            "benchmark_summary": benchmark,
        }.items()
        if data is None
    ]
    window_summary = (windows or {}).get("summary", {})
    failure_scope = "unknown"
    if window_summary.get("consistent_failure") is True:
        failure_scope = "global"
    elif window_summary.get("localized_signal") is True:
        failure_scope = "window_specific"
    ranking_mode = (ranking or {}).get("ranking_failure_mode") or "unknown"
    frequency_delta = (frequency or {}).get("frequency_minus_cruncher")
    frequency_dominance = bool(frequency_delta is not None and frequency_delta > 0)
    high_failures = (draw_report or {}).get("summary", {}).get("high_or_extreme_failures")
    combination_issue = "unknown"
    if isinstance(high_failures, int):
        combination_issue = high_failures > 0
    findings = []
    records = (windows or {}).get("records_count") or (draw_report or {}).get("records_count") or (frequency or {}).get("records_count")
    if records:
        findings.append(f"Replay {records} records analyzed as diagnostic_only.")
    if frequency_dominance:
        findings.append("Frequency baseline beats cruncher in progressive replay comparison.")
    if ranking_mode in ("inverted", "flat", "weak_top_only"):
        findings.append(f"Ranking failure mode detected: {ranking_mode}.")
    if (benchmark or {}).get("benchmark_signal_quality") == "weak":
        findings.append("Benchmark summary remains weak.")
    if missing:
        findings.append(f"Missing inputs: {', '.join(missing)}.")
    if not findings:
        findings.append("No strong failure evidence available; keep diagnostic_only.")
    return {
        "version": VERSION,
        "generated_at": utc_now(),
        "input_files": {
            "windows": windows_path,
            "ranking": ranking_path,
            "frequency": frequency_path,
            "draw_report": draw_report_path,
            "benchmark_summary": benchmark_summary_path,
        },
        "missing_inputs": missing,
        "recommendation": "diagnostic_only",
        "failure_scope": failure_scope,
        "ranking_failure_mode": ranking_mode,
        "frequency_dominance": frequency_dominance,
        "combination_issue": combination_issue,
        "prior_should_remain_blocked": True,
        "main_findings": findings,
        "recommended_next_action": "improve_signal_generation_or_ranking_before_more_replay",
        "do_not_do": [
            "do not enable replay prior",
            "do not modify Monte Carlo based on current replay",
            "do not add physics prior from one event",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build replay signal decomposition summary.")
    parser.add_argument("--windows", default="v4_replay_window_diagnostics.json")
    parser.add_argument("--ranking", default="v4_ranking_inversion_audit.json")
    parser.add_argument("--frequency", default="v4_frequency_dominance_audit.json")
    parser.add_argument("--draw-report", default="v4_draw_failure_report.json")
    parser.add_argument("--benchmark-summary", default="v4_benchmark_summary.json")
    parser.add_argument("--output", default="v4_signal_decomposition_summary.json")
    args = parser.parse_args()
    report = build_signal_summary(args.windows, args.ranking, args.frequency, args.draw_report, args.benchmark_summary)
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {args.output}; failure_scope={report['failure_scope']}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
