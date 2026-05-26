# -*- coding: utf-8 -*-
"""Refresh V4.3 Revancha composition outputs and run smoke checks."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_FILES = (
    "v4_winner_composition_audit.json",
    "v4_visual_pattern_output.json",
    "v4_hybrid_composition_slate.json",
)
V44_OUTPUT_FILES = (
    "revancha.csv",
    "v4_history_matrix.json",
    "v4_gap_echo_output.json",
    "v4_signature_history.json",
    "v4_pair_lag_signals.json",
    "v4_block_completion_signals.json",
    "v4_winner_profile.json",
    "v4_recent_composition_profile.json",
    "v4_combination_slate.json",
)
BASE_STEPS = (
    ("winner composition audit", "tools/v4_winner_composition_audit.py"),
    ("visual pattern features", "tools/v4_visual_pattern_features.py"),
)


def load_json(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError as exc:
        raise RuntimeError(f"Missing required output: {path.name}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON output: {path.name}: {exc}") from exc
    if not isinstance(data, dict):
        raise RuntimeError(f"Expected JSON object in {path.name}.")
    return data


def run_step(label: str, script: str, extra_args: list[str] | None = None, allow_failure: bool = False) -> int:
    command = [sys.executable, script, *(extra_args or [])]
    print(f"[v4-refresh] running {label}: {' '.join(command)}", flush=True)
    result = subprocess.run(command, cwd=ROOT, check=False)
    if result.returncode != 0:
        if allow_failure:
            print(f"[v4-refresh] warning: {label} exited with {result.returncode}; continuing.", flush=True)
            return result.returncode
        raise RuntimeError(f"Step failed: {label} exited with {result.returncode}.")
    return result.returncode


def confirm_outputs() -> None:
    missing = [path for path in OUTPUT_FILES if not (ROOT / path).exists()]
    if missing:
        raise RuntimeError(f"Missing expected V4.3 outputs: {', '.join(missing)}")
    print("[v4-refresh] confirmed outputs: " + ", ".join(OUTPUT_FILES), flush=True)


def confirm_v44_outputs() -> None:
    missing = [path for path in V44_OUTPUT_FILES if not (ROOT / path).exists()]
    if missing:
        raise RuntimeError(f"Missing expected V4.4 outputs: {', '.join(missing)}")
    print("[v4-refresh] confirmed V4.4 outputs: " + ", ".join(V44_OUTPUT_FILES), flush=True)


def _try_load(path: str) -> dict[str, Any]:
    try:
        return load_json(ROOT / path)
    except RuntimeError:
        return {}


def summarize(history_sync_ran: bool = False, snapshot_ran: bool = False, visual_export_ran: bool = False) -> None:
    slate = load_json(ROOT / "v4_hybrid_composition_slate.json")
    warnings = slate.get("warnings")
    if not isinstance(warnings, list):
        warnings = []
    source_policy = slate.get("source_policy") if isinstance(slate.get("source_policy"), dict) else {}
    tickets = slate.get("slate")
    ticket_count = len(tickets) if isinstance(tickets, list) else 0
    validation = slate.get("validation_summary") if isinstance(slate.get("validation_summary"), dict) else {}
    history_sync = _try_load("v4_history_sync_report.json") if history_sync_ran else {}
    matrix_report = _try_load("v4_visual_matrix_export_report.json") if visual_export_ran else {}
    snapshot_path = None
    if snapshot_ran:
        latest = slate.get("latest_draw")
        if isinstance(latest, int):
            snapshot = ROOT / "v4_predraw_slate_snapshots" / f"v4_predraw_slate_target_{latest + 1}.json"
            snapshot_path = str(snapshot) if snapshot.exists() else None

    print("[v4-refresh] summary", flush=True)
    print(f"  latest_draw: {slate.get('latest_draw', 'N/D')}", flush=True)
    if snapshot_path:
        print(f"  target_draw: {int(slate.get('latest_draw')) + 1}", flush=True)
    print(f"  production_status: {slate.get('production_status', 'N/D')}", flush=True)
    print(f"  pair_lag_mode: {source_policy.get('pair_lag_mode', 'N/D')}", flush=True)
    print(f"  ticket_count: {ticket_count}", flush=True)
    print(f"  fallback_mode: {source_policy.get('fallback_mode', 'N/D')}", flush=True)
    if history_sync:
        print(f"  history_sync_latest_draw: {history_sync.get('latest_draw', 'N/D')}", flush=True)
    print(f"  sum_band_distribution: {validation.get('slate_sum_distribution', 'N/D')}", flush=True)
    print(f"  harmonic_coherence_summary: {validation.get('harmonic_coherence_summary', 'N/D')}", flush=True)
    print(f"  pair_companion_summary: {validation.get('pair_companion_summary', 'N/D')}", flush=True)
    if snapshot_path:
        print(f"  snapshot_path: {snapshot_path}", flush=True)
    if matrix_report:
        print(f"  visual_matrix_paths: {matrix_report.get('paths', 'N/D')}", flush=True)
    print(f"  warnings: {warnings if warnings else 'none'}", flush=True)


def summarize_v44() -> None:
    slate = load_json(ROOT / "v4_combination_slate.json")
    recent = _try_load("v4_recent_composition_profile.json")
    tickets = slate.get("tickets") if isinstance(slate.get("tickets"), list) else []
    summary = slate.get("slate_structure_summary") if isinstance(slate.get("slate_structure_summary"), dict) else {}
    print("[v4-refresh] V4.4 summary", flush=True)
    print(f"  latest_draw: {slate.get('latest_draw', 'N/D')}", flush=True)
    print(f"  target_draw: {slate.get('target_draw', 'N/D')}", flush=True)
    print(f"  production_status: {slate.get('production_status', 'N/D')}", flush=True)
    print(f"  ticket_count: {len(tickets)}", flush=True)
    print(f"  recent_window: {recent.get('window', 'N/D')}", flush=True)
    print(f"  dominant_sum_band: {slate.get('recent_composition_profile_used', {}).get('dominant_sum_band', 'N/D')}", flush=True)
    print(f"  pair_companion_usage_count: {summary.get('pair_companion_usage_count', 'N/D')}", flush=True)
    print(f"  pair_lag_usage_count: {summary.get('pair_lag_usage_count', 'N/D')}", flush=True)
    print(f"  immediate_overlap_distribution: {summary.get('immediate_overlap_distribution', 'N/D')}", flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh V4.3 Revancha composition outputs.")
    parser.add_argument("--game", default="revancha", help="Game mode to refresh. Only 'revancha' is supported for now.")
    parser.add_argument("--sync-history-from-pakin", action="store_true")
    parser.add_argument("--snapshot-predraw", action="store_true")
    parser.add_argument("--export-visual-matrix", action="store_true")
    parser.add_argument("--pair-companion-audit", action="store_true")
    parser.add_argument("--scrape", action="store_true")
    parser.add_argument("--reconstruct", action="store_true")
    parser.add_argument("--full-signals", action="store_true")
    parser.add_argument("--recent-composition", action="store_true")
    parser.add_argument("--construct", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if str(args.game).lower() != "revancha":
        print("[v4-refresh] ERROR: only --game revancha is supported for V4.3 refresh.", file=sys.stderr)
        return 2

    try:
        v44_requested = any((args.scrape, args.reconstruct, args.full_signals, args.recent_composition, args.construct))
        if v44_requested:
            print("[v4-refresh] starting V4.4 constructor refresh for revancha", flush=True)
            if args.scrape:
                run_step("Pakin scraper", "tools/v4_scraper_pakin.py")
            if args.reconstruct:
                run_step("CSV reconstructor", "tools/v4_csv_reconstructor.py")
            if args.full_signals:
                run_step("history matrix", "tools/v4_matrix_builder.py")
                run_step("gap echo", "tools/v4_gap_echo_engine.py")
                run_step("signature history", "tools/v4_signature_history_engine.py")
                run_step("pair lag constructor", "tools/v4_pair_lag_constructor.py")
                run_step("block completion", "tools/v4_block_completion_engine.py")
                run_step("winner profile", "tools/v4_winner_profile_engine.py")
            if args.recent_composition:
                run_step("recent composition profile", "tools/v4_recent_composition_engine.py")
            if args.construct:
                if not args.full_signals:
                    required = [
                        "v4_gap_echo_output.json",
                        "v4_signature_history.json",
                        "v4_pair_lag_signals.json",
                        "v4_block_completion_signals.json",
                        "v4_winner_profile.json",
                    ]
                    missing = [path for path in required if not (ROOT / path).exists()]
                    if missing:
                        raise RuntimeError(f"--construct requires --full-signals or existing files: {', '.join(missing)}")
                if not args.recent_composition and not (ROOT / "v4_recent_composition_profile.json").exists():
                    raise RuntimeError("--construct requires --recent-composition or existing v4_recent_composition_profile.json")
                run_step("combination constructor", "tools/v4_combination_constructor.py")
            run_step("hybrid composition smoke test", "tools/v4_hybrid_composition_smoke_test.py")
            confirm_v44_outputs()
            summarize_v44()
            print("[v4-refresh] done", flush=True)
            return 0

        print("[v4-refresh] starting V4.3 refresh for revancha", flush=True)
        if args.sync_history_from_pakin:
            run_step("Pakin history sync", "tools/v4_history_sync_from_pakin.py", ["--game", "revancha"], allow_failure=True)
        for label, script in BASE_STEPS:
            run_step(label, script)
        if args.pair_companion_audit:
            run_step("pair companion audit", "tools/v4_pair_companion_audit.py")
        run_step("hybrid composition engine", "tools/v4_hybrid_composition_engine.py")
        run_step("hybrid composition smoke test", "tools/v4_hybrid_composition_smoke_test.py")
        if args.export_visual_matrix:
            run_step("visual matrix export", "tools/v4_visual_matrix_export.py")
        if args.snapshot_predraw:
            run_step("pre-draw snapshot", "tools/v4_predraw_snapshot.py", allow_failure=True)
        confirm_outputs()
        summarize(args.sync_history_from_pakin, args.snapshot_predraw, args.export_visual_matrix)
    except RuntimeError as exc:
        print(f"[v4-refresh] ERROR: {exc}", file=sys.stderr)
        return 1

    print("[v4-refresh] done", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
