# -*- coding: utf-8 -*-
"""Bootstrap-lite stability checks for replay benchmark edges.

This script is diagnostic-only. It reads replay benchmark artifacts and writes a
summary; it never updates replay memory, resultados.json, or any prior state.
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from statistics import mean
from typing import Any

from v4_benchmark_hardening import build_hardening, utc_now

VERSION = "V4.4-benchmark-stability"


def _load(path: str | Path) -> dict[str, Any] | None:
    file_path = Path(path)
    if not file_path.exists():
        return None
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _values(edges: list[dict[str, Any]], key: str) -> list[float]:
    values: list[float] = []
    for row in edges:
        if not isinstance(row, dict):
            continue
        try:
            value = float(row.get(key))
        except (TypeError, ValueError):
            continue
        values.append(value)
    return values


def _ci(values: list[float], iterations: int, seed: int) -> dict[str, Any]:
    if not values:
        return {
            "available": False,
            "reason": "insufficient data",
            "mean": None,
            "ci_95": None,
            "interpretation": "unavailable",
        }
    rng = random.Random(seed)
    draws = []
    for _ in range(iterations):
        sample = [values[rng.randrange(len(values))] for _ in values]
        draws.append(mean(sample))
    draws.sort()
    low_index = max(0, int(0.025 * len(draws)) - 1)
    high_index = min(len(draws) - 1, int(0.975 * len(draws)))
    low = round(draws[low_index], 6)
    high = round(draws[high_index], 6)
    avg = round(mean(values), 6)
    if low <= 0 <= high:
        interpretation = "not_statistically_stable"
    elif low > 0:
        interpretation = "favorable_but_still_diagnostic"
    else:
        interpretation = "worse_than_baseline"
    return {
        "available": True,
        "mean": avg,
        "ci_95": [low, high],
        "interpretation": interpretation,
    }


def _overall_stability(rows: list[dict[str, Any]], records_count: int) -> str:
    if records_count < 30:
        return "insufficient_data"
    available = [row for row in rows if row.get("available")]
    if not available:
        return "insufficient_data"
    favorable = sum(1 for row in available if row.get("interpretation") == "favorable_but_still_diagnostic")
    unstable = sum(1 for row in available if row.get("interpretation") == "not_statistically_stable")
    worse = sum(1 for row in available if row.get("interpretation") == "worse_than_baseline")
    if worse:
        return "weak"
    if unstable:
        return "unstable"
    if favorable == len(available) and len(available) >= 3:
        return "stable"
    return "moderate"


def build_stability(
    hardening_path: str = "v4_benchmark_hardening.json",
    replay_memory: str = "v4_replay_memory.json",
    iterations: int = 1000,
    seed: int = 42,
) -> dict[str, Any]:
    hardening = _load(hardening_path)
    if not hardening or not isinstance(hardening.get("record_edges"), list):
        hardening = build_hardening(replay_memory)
    edges = [row for row in hardening.get("record_edges", []) if isinstance(row, dict)]
    records_count = int(hardening.get("records_count") or len(edges))
    metrics = {
        "cruncher_minus_random": _ci(_values(edges, "cruncher_minus_random"), iterations, seed),
        "cruncher_minus_frequency": _ci(_values(edges, "cruncher_minus_frequency"), iterations, seed + 1),
        "cruncher_minus_recency": _ci(_values(edges, "cruncher_minus_recency"), iterations, seed + 2),
    }
    stability = _overall_stability(list(metrics.values()), records_count)
    return {
        "version": VERSION,
        "generated_at": utc_now(),
        "input_files": {"hardening": hardening_path, "replay_memory": replay_memory},
        "records_count": records_count,
        "bootstrap_iterations": iterations,
        "random_seed": seed,
        "cruncher_minus_random_mean": metrics["cruncher_minus_random"].get("mean"),
        "cruncher_minus_random_ci_95": metrics["cruncher_minus_random"].get("ci_95"),
        "cruncher_minus_frequency_mean": metrics["cruncher_minus_frequency"].get("mean"),
        "cruncher_minus_frequency_ci_95": metrics["cruncher_minus_frequency"].get("ci_95"),
        "cruncher_minus_recency_mean": metrics["cruncher_minus_recency"].get("mean"),
        "cruncher_minus_recency_ci_95": metrics["cruncher_minus_recency"].get("ci_95"),
        "metrics": metrics,
        "stability": stability,
        "recommendation": "diagnostic_only",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap replay benchmark edge stability.")
    parser.add_argument("--hardening", default="v4_benchmark_hardening.json")
    parser.add_argument("--replay-memory", default="v4_replay_memory.json")
    parser.add_argument("--output", default="v4_benchmark_stability.json")
    parser.add_argument("--bootstrap-iterations", type=int, default=1000)
    parser.add_argument("--random-seed", type=int, default=42)
    args = parser.parse_args()
    iterations = max(100, args.bootstrap_iterations)
    report = build_stability(args.hardening, args.replay_memory, iterations, args.random_seed)
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {args.output}; stability={report['stability']}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
