# -*- coding: utf-8 -*-
"""Build the full historical winner composition profile for V4.4."""

from __future__ import annotations

import argparse
from collections import Counter

from v4_history_common import (
    PRODUCTION_STATUS,
    block_signature,
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


ENGINE_VERSION = "v4.4-winner-profile"


def build_profile(csv_path: str) -> dict:
    draws = read_history_csv(csv_path)
    if not draws:
        raise SystemExit(f"No valid draws found in {csv_path}.")
    sums = [sum(draw["numbers"]) for draw in draws]
    sum_bands = [sum_band(value) for value in sums]
    parity = [parity_label(draw["numbers"]) for draw in draws]
    presences = [presence_signature(draw["numbers"]) for draw in draws]
    signatures = [block_signature(draw["numbers"]) for draw in draws]
    overlaps = []
    for previous, current in zip(draws, draws[1:]):
        overlaps.append(len(set(previous["numbers"]) & set(current["numbers"])))
    return {
        "generated_at": utc_now(),
        "engine_version": ENGINE_VERSION,
        "production_status": PRODUCTION_STATUS,
        "source_file": csv_path,
        "source_sha256": file_sha256(csv_path),
        "latest_draw": draws[-1]["draw_id"],
        "draw_count": len(draws),
        "sum_profile": {
            "sum_min": min(sums),
            "sum_max": max(sums),
            "sum_avg": safe_avg([float(value) for value in sums]),
            "sum_median": safe_median([float(value) for value in sums]),
            "sum_band_distribution": distribution(sum_bands),
            "dominant_sum_band": Counter(sum_bands).most_common(1)[0][0],
        },
        "parity_profile": {
            "parity_distribution": distribution(parity),
            "dominant_parity": Counter(parity).most_common(1)[0][0],
        },
        "presence_signature_profile": {
            "presence_signature_distribution": distribution(presences),
            "dominant_presence_signature": Counter(presences).most_common(1)[0][0],
        },
        "block_signature_profile": {
            "block_signature_distribution": distribution(signatures),
            "dominant_block_signature": Counter(signatures).most_common(1)[0][0],
        },
        "immediate_overlap_profile": {
            "immediate_overlap_distribution": distribution(overlaps),
            "avg_immediate_overlap": safe_avg([float(value) for value in overlaps]),
            "dominant_immediate_overlap": int(Counter(overlaps).most_common(1)[0][0]) if overlaps else 0,
        },
        "summary_es": "Perfil histórico ganador construido para revisión de composición.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build V4.4 historical winner profile.")
    parser.add_argument("--csv", default="revancha.csv")
    parser.add_argument("--output", default="v4_winner_profile.json")
    args = parser.parse_args()
    report = build_profile(args.csv)
    write_json(args.output, report)
    print(f"Wrote {args.output}; latest_draw={report['latest_draw']} draws={report['draw_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
