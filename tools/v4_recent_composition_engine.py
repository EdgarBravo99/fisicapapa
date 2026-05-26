# -*- coding: utf-8 -*-
"""Analyze the last 30 Revancha combinations for V4.4 composition guidance."""

from __future__ import annotations

import argparse
import itertools
from collections import Counter

from v4_history_common import (
    PRODUCTION_STATUS,
    distribution,
    file_sha256,
    parity_label,
    presence_signature,
    read_history_csv,
    safe_avg,
    safe_median,
    sum_band,
    utc_now,
    write_json,
)


ENGINE_VERSION = "v4.4-recent-composition"
WINDOW = 30


def build_recent_profile(csv_path: str, window: int = WINDOW) -> dict:
    draws = read_history_csv(csv_path)
    if len(draws) < window:
        raise SystemExit(f"revancha.csv has {len(draws)} valid rows; {window} required for recent composition.")
    recent = draws[-window:]
    sums = [sum(draw["numbers"]) for draw in recent]
    bands = [sum_band(value) for value in sums]
    parity = [parity_label(draw["numbers"]) for draw in recent]
    presences = [presence_signature(draw["numbers"]) for draw in recent]
    overlaps = []
    draw_by_id = {draw["draw_id"]: draw for draw in draws}
    for draw in recent:
        previous = draw_by_id.get(draw["draw_id"] - 1)
        overlaps.append(len(set(draw["numbers"]) & set(previous["numbers"])) if previous else 0)
    pair_counts: Counter[tuple[int, int]] = Counter()
    number_counts: Counter[int] = Counter()
    for draw in recent:
        number_counts.update(draw["numbers"])
        for pair in itertools.combinations(draw["numbers"], 2):
            pair_counts[tuple(sorted(pair))] += 1
    companion_rows = [
        {
            "pair": list(pair),
            "recent_co_appearances": count,
            "window": window,
            "pair_companion_score": round(count / window, 6),
        }
        for pair, count in pair_counts.most_common()
        if count >= 2
    ]
    top_recent_numbers = [
        {"number": number, "count": count, "recent_frequency_score": round(count / window, 6)}
        for number, count in number_counts.most_common(25)
    ]
    presence_counts = Counter(presences)
    second_presence = presence_counts.most_common(2)[1][0] if len(presence_counts) > 1 else presence_counts.most_common(1)[0][0]
    return {
        "generated_at": utc_now(),
        "engine_version": ENGINE_VERSION,
        "production_status": PRODUCTION_STATUS,
        "source_file": csv_path,
        "source_sha256": file_sha256(csv_path),
        "window": window,
        "latest_draw": recent[-1]["draw_id"],
        "draws_used": [draw["draw_id"] for draw in recent],
        "sum_profile": {
            "sum_min": min(sums),
            "sum_max": max(sums),
            "sum_avg": safe_avg([float(value) for value in sums]),
            "sum_median": safe_median([float(value) for value in sums]),
            "sum_band_distribution": distribution(bands),
            "dominant_sum_band": Counter(bands).most_common(1)[0][0],
        },
        "parity_profile": {
            "parity_distribution": distribution(parity),
            "dominant_parity": Counter(parity).most_common(1)[0][0],
        },
        "presence_signature_profile": {
            "presence_signature_distribution": distribution(presences),
            "dominant_presence_signature": presence_counts.most_common(1)[0][0],
            "second_presence_signature": second_presence,
        },
        "immediate_overlap_profile": {
            "immediate_overlap_distribution": distribution(overlaps),
            "avg_immediate_overlap": safe_avg([float(value) for value in overlaps]),
            "dominant_immediate_overlap": int(Counter(overlaps).most_common(1)[0][0]),
        },
        "pair_companion_profile": {
            "pair_companion_counts": {"-".join(map(str, pair)): count for pair, count in pair_counts.most_common() if count >= 2},
            "top_pair_companions": companion_rows[:30],
            "pair_companion_candidates": companion_rows[:60],
        },
        "number_frequency_recent_30": {str(number): count for number, count in sorted(number_counts.items())},
        "top_recent_numbers": top_recent_numbers,
        "summary_es": "Perfil reciente construido desde las últimas 30 combinaciones ganadoras para guiar composición, suma, pares compañeros y formación de estructura.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build V4.4 recent composition profile.")
    parser.add_argument("--csv", default="revancha.csv")
    parser.add_argument("--window", type=int, default=WINDOW)
    parser.add_argument("--output", default="v4_recent_composition_profile.json")
    args = parser.parse_args()
    report = build_recent_profile(args.csv, args.window)
    write_json(args.output, report)
    print(f"Wrote {args.output}; window={report['window']} latest_draw={report['latest_draw']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
