# -*- coding: utf-8 -*-
"""Run the V4.4 decision audit pack without touching the model engine."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _run_step(label: str, args: list[str]) -> dict[str, object]:
    print(f"[audit-pack] {label}")
    result = subprocess.run(args, cwd=ROOT, text=True, capture_output=True, check=False)
    if result.stdout:
        print(result.stdout.strip())
    if result.stderr:
        print(result.stderr.strip())
    return {
        "label": label,
        "returncode": result.returncode,
        "ok": result.returncode == 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run V4.4 decision audit pack.")
    parser.add_argument("--results", default="resultados.json")
    parser.add_argument("--replay-memory", default="v4_replay_memory.json")
    parser.add_argument("--weights", default="sphere_weight_history.json")
    args = parser.parse_args()

    python = sys.executable
    steps = [
        (
            "diversity selector",
            [python, str(ROOT / "tools" / "v4_diversity_selector.py"), "--input", args.results, "--output", "v4_diversity_output.json", "--pool", "auto"],
        ),
        (
            "candidate pool audit",
            [python, str(ROOT / "tools" / "v4_candidate_pool_audit.py"), "--input", args.results, "--output", "v4_candidate_pool_audit.json"],
        ),
        (
            "baseline benchmark",
            [python, str(ROOT / "tools" / "v4_baseline_benchmark.py"), "--replay-memory", args.replay_memory, "--output", "v4_baseline_benchmark.json"],
        ),
        (
            "benchmark hardening",
            [python, str(ROOT / "tools" / "v4_benchmark_hardening.py"), "--replay-memory", args.replay_memory, "--output", "v4_benchmark_hardening.json"],
        ),
        (
            "calibration diagnostics",
            [python, str(ROOT / "tools" / "v4_calibration_diagnostics.py"), "--replay-memory", args.replay_memory, "--output", "v4_calibration_diagnostics.json"],
        ),
        (
            "diversified vs original eval",
            [python, str(ROOT / "tools" / "v4_diversified_vs_original_eval.py"), "--replay-memory", args.replay_memory, "--output", "v4_diversified_vs_original_eval.json"],
        ),
        (
            "benchmark stability",
            [python, str(ROOT / "tools" / "v4_benchmark_stability.py"), "--replay-memory", args.replay_memory, "--output", "v4_benchmark_stability.json"],
        ),
        (
            "benchmark summary gate",
            [python, str(ROOT / "tools" / "v4_benchmark_summary_gate.py"), "--output", "v4_benchmark_summary.json"],
        ),
        (
            "physics regime audit",
            [python, str(ROOT / "tools" / "v4_physics_regime_audit.py"), "--weights", args.weights, "--output", "v4_physics_regime_analysis.json"],
        ),
        (
            "physics timeline",
            [python, str(ROOT / "tools" / "v4_physics_timeline.py"), "--weights", args.weights, "--output", "v4_physics_regime_timeline.json"],
        ),
        (
            "replay qualification gate",
            [python, str(ROOT / "tools" / "v4_replay_qualification_gate.py"), "--output", "v4_replay_qualification.json"],
        ),
        (
            "decision slate",
            [python, str(ROOT / "tools" / "v4_decision_slate.py"), "--output", "v4_decision_slate.json"],
        ),
        (
            "local audit state",
            [python, str(ROOT / "tools" / "v4_audit_state.py"), "--output", "v4_audit_state.json"],
        ),
    ]
    reports = [_run_step(label, command) for label, command in steps]
    failed = [row for row in reports if not row["ok"]]
    if failed:
        print(f"[audit-pack] completed with {len(failed)} warning(s); generated outputs may be partial.")
        return 1
    print("[audit-pack] completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
