# -*- coding: utf-8 -*-
"""V4.3 winner composition audit for Revancha historical draws."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MAX_NUMBER = 56
DRAW_SIZE = 6
DEFAULT_HISTORY_DRAWS = 200
BLOCKS = {
    "1_10": range(1, 11),
    "11_20": range(11, 21),
    "21_30": range(21, 31),
    "31_40": range(31, 41),
    "41_56": range(41, 57),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_int(value: Any) -> int | None:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None


def clean_numbers(values: list[Any]) -> list[int]:
    numbers: list[int] = []
    for value in values:
        number = parse_int(value)
        if number is not None and 1 <= number <= MAX_NUMBER and number not in numbers:
            numbers.append(number)
    return sorted(numbers) if len(numbers) == DRAW_SIZE else []


def read_revancha_csv(path: str | Path = "revancha.csv") -> list[dict[str, Any]]:
    csv_path = Path(path)
    rows: list[dict[str, Any]] = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            lowered = {str(key or "").strip().lower(): value for key, value in row.items()}
            draw_id = parse_int(
                row.get("CONCURSO")
                or row.get("draw")
                or row.get("draw_id")
                or row.get("sorteo")
                or lowered.get("sorteo")
                or lowered.get("concurso")
            )
            r_values = [row.get(f"R{i}") for i in range(1, 7)]
            n_values = [row.get(f"n{i}") or lowered.get(f"n{i}") for i in range(1, 7)]
            numbers = clean_numbers(r_values if any(value not in (None, "") for value in r_values) else n_values)
            if draw_id is None or not numbers:
                continue
            rows.append({"draw_id": draw_id, "numbers": numbers, "raw": row})
    return sorted(rows, key=lambda item: item["draw_id"])


def block_counts(numbers: list[int]) -> dict[str, int]:
    number_set = set(numbers)
    return {name: sum(1 for number in values if number in number_set) for name, values in BLOCKS.items()}


def parity_counts(numbers: list[int]) -> dict[str, int]:
    even = sum(1 for number in numbers if number % 2 == 0)
    return {"even": even, "odd": len(numbers) - even}


def consecutive_pairs(numbers: list[int]) -> int:
    number_set = set(numbers)
    return sum(1 for number in numbers if number + 1 in number_set)


def bucket_counter(values: list[int], bucket_size: int = 10) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for value in values:
        low = (value // bucket_size) * bucket_size
        high = low + bucket_size - 1
        counter[f"{low}_{high}"] += 1
    return dict(sorted(counter.items()))


def safe_avg(values: list[float]) -> float:
    return round(sum(values) / len(values), 6) if values else 0.0


def load_v42_ranking(path: str | Path = "resultados.json") -> tuple[list[int], bool, str | None]:
    json_path = Path(path)
    if not json_path.exists():
        return [], False, "resultados.json missing; V4.3 running CSV-only."
    raw = json_path.read_text(encoding="utf-8-sig", errors="replace")
    if not raw.strip():
        return [], False, "resultados.json empty; V4.3 running CSV-only."
    if any(marker in raw for marker in ("<<<<<<<", "=======", ">>>>>>>")):
        return [], False, "resultados.json contains conflict markers; V4.3 running CSV-only."
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return [], False, f"resultados.json invalid JSON: {exc}; V4.3 running CSV-only."
    scores = data.get("number_scores") if isinstance(data, dict) else None
    if not isinstance(scores, dict):
        return [], False, "resultados.json has no number_scores; V4.3 running CSV-only."
    ranking: list[tuple[int, float]] = []
    for raw_number, raw_score in scores.items():
        number = parse_int(raw_number)
        if number is None or not (1 <= number <= MAX_NUMBER):
            continue
        try:
            score = float(raw_score)
        except (TypeError, ValueError):
            continue
        ranking.append((number, score))
    ranked_numbers = [number for number, _ in sorted(ranking, key=lambda item: (-item[1], item[0]))]
    if len(ranked_numbers) < DRAW_SIZE:
        return [], False, "resultados.json number_scores insufficient; V4.3 running CSV-only."
    return ranked_numbers, True, None


def v42_bucket(number: int, ranking: list[int]) -> str:
    if not ranking or number not in ranking:
        return "unavailable"
    rank = ranking.index(number) + 1
    if rank <= 5:
        return "top5"
    if rank <= 10:
        return "rank6_10"
    if rank <= 20:
        return "rank11_20"
    if rank <= 30:
        return "rank21_30"
    return "rank31_56"


def build_audit(
    csv_path: str | Path = "revancha.csv",
    resultados_path: str | Path = "resultados.json",
    history_draws: int = DEFAULT_HISTORY_DRAWS,
) -> dict[str, Any]:
    draws = read_revancha_csv(csv_path)
    if not draws:
        raise SystemExit(f"No valid Revancha draws found in {csv_path}.")
    history = draws[-history_draws:]
    ranking, v42_available, v42_warning = load_v42_ranking(resultados_path)

    parity: Counter[str] = Counter()
    block_patterns: Counter[str] = Counter()
    block_totals: Counter[str] = Counter()
    overlap: Counter[str] = Counter()
    consecutive: Counter[str] = Counter()
    high_closures: Counter[str] = Counter()
    sums: list[int] = []
    v42_buckets: Counter[str] = Counter()
    previous: list[int] | None = None

    for draw in history:
        numbers = draw["numbers"]
        p = parity_counts(numbers)
        parity[f"{p['even']}_even_{p['odd']}_odd"] += 1
        blocks = block_counts(numbers)
        block_patterns["|".join(f"{name}:{count}" for name, count in blocks.items())] += 1
        block_totals.update(blocks)
        sums.append(sum(numbers))
        consecutive[str(consecutive_pairs(numbers))] += 1
        high_closures[str(blocks["41_56"])] += 1
        if previous is not None:
            overlap[str(len(set(numbers) & set(previous)))] += 1
        previous = numbers
        for number in numbers:
            bucket = v42_bucket(number, ranking)
            if bucket != "unavailable":
                v42_buckets[bucket] += 1

    recent = history[-5:]
    recent_block_hits: dict[str, int] = defaultdict(int)
    recent_unique_seen: dict[str, set[int]] = {name: set() for name in BLOCKS}
    for draw in recent:
        for name, count in block_counts(draw["numbers"]).items():
            recent_block_hits[name] += count
        for number in draw["numbers"]:
            for name, values in BLOCKS.items():
                if number in values:
                    recent_unique_seen[name].add(number)
                    break
    recent_activation = {
        name: {
            "unique_activation": round(len(recent_unique_seen[name]) / max(len(list(BLOCKS[name])), 1), 6),
            "hit_density": round(recent_block_hits[name] / max(len(recent) * len(list(BLOCKS[name])), 1), 6),
            "unique_seen": len(recent_unique_seen[name]),
            "total_hits": recent_block_hits[name],
        }
        for name in BLOCKS
    }

    return {
        "generated_at": utc_now(),
        "source": {
            "revancha_csv": str(csv_path),
            "resultados_json_available": v42_available,
            "resultados_json_warning": v42_warning,
        },
        "history": {
            "draws_used": len(history),
            "latest_draw": history[-1]["draw_id"],
            "latest_numbers": history[-1]["numbers"],
        },
        "composition_profile": {
            "parity": dict(parity.most_common()),
            "sum": {
                "average": safe_avg([float(value) for value in sums]),
                "min": min(sums),
                "max": max(sums),
                "buckets": bucket_counter(sums, 25),
            },
            "blocks": {
                "average_per_draw": {name: round(block_totals[name] / len(history), 6) for name in BLOCKS},
                "top_patterns": dict(block_patterns.most_common(12)),
            },
            "immediate_overlap": dict(overlap.most_common()),
            "consecutive_pairs": dict(consecutive.most_common()),
            "high_block_closures": dict(high_closures.most_common()),
            "activated_blocks": {
                "recent_window_draws": len(recent),
                "recent_activation": recent_activation,
                "active_blocks": [name for name, row in recent_activation.items() if row["unique_activation"] >= 0.40],
            },
            "v42_ranking_distribution": dict(v42_buckets.most_common()) if v42_available else {},
        },
        "recommendations": {
            "avoid_top6_pure": True,
            "allow_concentrated_activated_block": True,
            "penalize_unjustified_carryover": True,
            "treat_parity_sum_as_soft_filters": True,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build V4.3 winner composition audit.")
    parser.add_argument("--csv", default="revancha.csv")
    parser.add_argument("--resultados", default="resultados.json")
    parser.add_argument("--history-draws", type=int, default=DEFAULT_HISTORY_DRAWS)
    parser.add_argument("--output", default="v4_winner_composition_audit.json")
    args = parser.parse_args()
    report = build_audit(args.csv, args.resultados, args.history_draws)
    Path(args.output).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {args.output}; draws_used={report['history']['draws_used']} latest_draw={report['history']['latest_draw']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
