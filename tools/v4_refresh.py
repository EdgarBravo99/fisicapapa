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
STEPS = (
    ("winner composition audit", "tools/v4_winner_composition_audit.py"),
    ("visual pattern features", "tools/v4_visual_pattern_features.py"),
    ("hybrid composition engine", "tools/v4_hybrid_composition_engine.py"),
    ("hybrid composition smoke test", "tools/v4_hybrid_composition_smoke_test.py"),
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


def run_step(label: str, script: str) -> None:
    command = [sys.executable, script]
    print(f"[v4-refresh] running {label}: {' '.join(command)}", flush=True)
    result = subprocess.run(command, cwd=ROOT, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"Step failed: {label} exited with {result.returncode}.")


def confirm_outputs() -> None:
    missing = [path for path in OUTPUT_FILES if not (ROOT / path).exists()]
    if missing:
        raise RuntimeError(f"Missing expected V4.3 outputs: {', '.join(missing)}")
    print("[v4-refresh] confirmed outputs: " + ", ".join(OUTPUT_FILES), flush=True)


def summarize() -> None:
    slate = load_json(ROOT / "v4_hybrid_composition_slate.json")
    warnings = slate.get("warnings")
    if not isinstance(warnings, list):
        warnings = []
    source_policy = slate.get("source_policy") if isinstance(slate.get("source_policy"), dict) else {}
    tickets = slate.get("slate")
    ticket_count = len(tickets) if isinstance(tickets, list) else 0

    print("[v4-refresh] summary", flush=True)
    print(f"  latest_draw: {slate.get('latest_draw', 'N/D')}", flush=True)
    print(f"  production_status: {slate.get('production_status', 'N/D')}", flush=True)
    print(f"  pair_lag_mode: {source_policy.get('pair_lag_mode', 'N/D')}", flush=True)
    print(f"  ticket_count: {ticket_count}", flush=True)
    print(f"  fallback_mode: {source_policy.get('fallback_mode', 'N/D')}", flush=True)
    print(f"  warnings: {warnings if warnings else 'none'}", flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh V4.3 Revancha composition outputs.")
    parser.add_argument("--game", default="revancha", help="Game mode to refresh. Only 'revancha' is supported for now.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if str(args.game).lower() != "revancha":
        print("[v4-refresh] ERROR: only --game revancha is supported for V4.3 refresh.", file=sys.stderr)
        return 2

    try:
        print("[v4-refresh] starting V4.3 refresh for revancha", flush=True)
        for label, script in STEPS:
            run_step(label, script)
        confirm_outputs()
        summarize()
    except RuntimeError as exc:
        print(f"[v4-refresh] ERROR: {exc}", file=sys.stderr)
        return 1

    print("[v4-refresh] done", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
