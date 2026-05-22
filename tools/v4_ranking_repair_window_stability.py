# -*- coding: utf-8 -*-
"""Window stability for diagnostic ranking repair variants."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from v4_benchmark_hardening import DRAW_SIZE, load_replay_records, parse_int, utc_now
from v4_ranking_repair_experiment import RANDOM_TOP10_HITS, build_ranking_repair_experiment

VERSION = "V4.4-ranking-repair-window-stability"


def _load(path: str | Path) -> dict[str, Any] | None:
    file_path = Path(path)
    if not file_path.exists():
        return None
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _avg(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 6) if values else None


def _draw(row: dict[str, Any]) -> int:
    return parse_int(row.get("target_draw")) or 0


def _windows(draws: list[int], size: int = 15) -> list[tuple[int, int]]:
    clean = sorted(draw for draw in draws if draw)
    windows: list[tuple[int, int]] = []
    for start in range(0, len(clean), size):
        chunk = clean[start : start + size]
        if chunk:
            windows.append((chunk[0], chunk[-1]))
    if clean:
        windows.append((clean[0], clean[-1]))
    return windows


def _variant_rows(experiment: dict[str, Any], name: str) -> list[dict[str, Any]]:
    rows = experiment.get("variants", {}).get(name, {}).get("record_results", [])
    return rows if isinstance(rows, list) else []


def _window_metric(rows: list[dict[str, Any]], low: int, high: int, key: str) -> float | None:
    values = []
    for row in rows:
        draw = _draw(row)
        if low <= draw <= high and row.get(key) is not None:
            values.append(float(row[key]))
    return _avg(values)


def build_window_stability(
    experiment_path: str = "v4_ranking_repair_experiment.json",
    replay_memory: str = "v4_replay_memory.json",
) -> dict[str, Any]:
    experiment = _load(experiment_path) or build_ranking_repair_experiment(replay_memory)
    records, _ = load_replay_records(replay_memory)
    original_rows = _variant_rows(experiment, "original_cruncher")
    frequency_rows = _variant_rows(experiment, "frequency_only")
    all_draws = [_draw(row) for row in original_rows] or [parse_int(record.get("target_draw")) or 0 for record in records]
    windows = []
    variants = experiment.get("variants", {})
    repair_names = [name for name in variants if name not in ("original_cruncher", "frequency_only", "random_expected")]
    best_variant_name = experiment.get("best_variant", {}).get("name")
    improved_windows = 0
    total_core_windows = 0
    for low, high in _windows(all_draws):
        is_total = low == min(all_draws or [0]) and high == max(all_draws or [0]) and len(all_draws) > 15
        original_top10 = _window_metric(original_rows, low, high, "top10_hits")
        frequency_top10 = _window_metric(frequency_rows, low, high, "top10_hits")
        variant_metrics = {}
        for name in repair_names:
            rows = _variant_rows(experiment, name)
            top10 = _window_metric(rows, low, high, "top10_hits")
            top20 = _window_metric(rows, low, high, "top20_hits")
            variant_metrics[name] = {
                "top10_avg_hits": top10,
                "top20_avg_hits": top20,
                "variant_minus_original": round(top10 - original_top10, 6) if top10 is not None and original_top10 is not None else None,
                "variant_minus_frequency": round(top10 - frequency_top10, 6) if top10 is not None and frequency_top10 is not None else None,
                "variant_minus_random": round(top10 - RANDOM_TOP10_HITS, 6) if top10 is not None else None,
            }
        best = variant_metrics.get(best_variant_name or "", {})
        if not is_total:
            total_core_windows += 1
            if best.get("variant_minus_original") is not None and best["variant_minus_original"] > 0:
                improved_windows += 1
        best_edge = best.get("variant_minus_original")
        freq_edge = best.get("variant_minus_frequency")
        if best_edge is None:
            quality = "unknown"
        elif best_edge > 0 and (freq_edge is None or freq_edge >= -0.25):
            quality = "weak_positive"
        else:
            quality = "weak"
        windows.append(
            {
                "window_id": f"draws_{low}_{high}",
                "draw_start": low,
                "draw_end": high,
                "records_count": sum(1 for draw in all_draws if low <= draw <= high),
                "is_total_window": is_total,
                "variants": variant_metrics,
                "window_signal_quality": quality,
                "window_recommendation": "diagnostic_only",
            }
        )
    stable = total_core_windows >= 4 and improved_windows >= 3
    return {
        "version": VERSION,
        "generated_at": utc_now(),
        "records_count": len(records),
        "windows": windows,
        "summary": {
            "best_variant": best_variant_name,
            "stable_across_windows": stable,
            "windows_improved_count": improved_windows,
            "windows_total": total_core_windows,
            "recommendation": "diagnostic_only",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build ranking repair window stability report.")
    parser.add_argument("--experiment", default="v4_ranking_repair_experiment.json")
    parser.add_argument("--replay-memory", default="v4_replay_memory.json")
    parser.add_argument("--output", default="v4_ranking_repair_window_stability.json")
    args = parser.parse_args()
    report = build_window_stability(args.experiment, args.replay_memory)
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {args.output}; stable={report['summary']['stable_across_windows']}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
