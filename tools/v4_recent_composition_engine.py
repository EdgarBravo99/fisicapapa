# -*- coding: utf-8 -*-
"""Analyze recent Revancha composition windows for V4.4 review guidance."""

from __future__ import annotations

import argparse
import itertools
import json
from collections import Counter
from pathlib import Path
from typing import Any

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
WINDOWS = (5, 20, 30)
LEGACY_WINDOW = 30


def tied_dominants(counter: Counter[Any]) -> list[Any]:
    if not counter:
        return []
    top_count = counter.most_common(1)[0][1]
    return [value for value, count in counter.items() if count == top_count]


def build_window_profile(draws: list[dict[str, Any]], csv_path: str, window: int) -> dict[str, Any]:
    if len(draws) < window:
        raise SystemExit(f"revancha.csv has {len(draws)} valid rows; {window} required for recent composition.")
    recent = draws[-window:]
    sums = [sum(draw["numbers"]) for draw in recent]
    bands = [sum_band(value) for value in sums]
    parity = [parity_label(draw["numbers"]) for draw in recent]
    presences = [presence_signature(draw["numbers"]) for draw in recent]
    overlaps: list[int] = []
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

    band_counts = Counter(bands)
    parity_counts = Counter(parity)
    presence_counts = Counter(presences)
    overlap_counts = Counter(overlaps)
    second_presence = presence_counts.most_common(2)[1][0] if len(presence_counts) > 1 else presence_counts.most_common(1)[0][0]
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
    summary_notes = [
        f"Perfil reciente de ventana {window} construido para revisar suma, paridad, presencia visual, pares companion y repetidos inmediatos."
    ]
    if len(tied_dominants(band_counts)) > 1:
        summary_notes.append(f"Empate en banda de suma dominante: {', '.join(map(str, tied_dominants(band_counts)))}.")
    if len(tied_dominants(parity_counts)) > 1:
        summary_notes.append(f"Empate en paridad dominante: {', '.join(map(str, tied_dominants(parity_counts)))}.")
    if len(tied_dominants(presence_counts)) > 1:
        summary_notes.append(f"Empate en firma de presencia dominante: {', '.join(map(str, tied_dominants(presence_counts)))}.")
    if len(tied_dominants(overlap_counts)) > 1:
        summary_notes.append(f"Empate en repetidos inmediatos dominantes: {', '.join(map(str, tied_dominants(overlap_counts)))}.")

    return {
        "window": window,
        "latest_draw": recent[-1]["draw_id"],
        "latest_draw_numbers": recent[-1]["numbers"],
        "draws_used": [draw["draw_id"] for draw in recent],
        "sum_profile": {
            "sum_min": min(sums),
            "sum_max": max(sums),
            "sum_avg": safe_avg([float(value) for value in sums]),
            "sum_median": safe_median([float(value) for value in sums]),
            "sum_band_distribution": distribution(bands),
            "dominant_sum_band": band_counts.most_common(1)[0][0],
            "dominant_sum_bands": tied_dominants(band_counts),
        },
        "parity_profile": {
            "parity_distribution": distribution(parity),
            "dominant_parity": parity_counts.most_common(1)[0][0],
            "dominant_parities": tied_dominants(parity_counts),
        },
        "presence_signature_profile": {
            "presence_signature_distribution": distribution(presences),
            "dominant_presence_signature": presence_counts.most_common(1)[0][0],
            "dominant_presence_signatures": tied_dominants(presence_counts),
            "second_presence_signature": second_presence,
        },
        "immediate_overlap_profile": {
            "immediate_overlap_distribution": distribution(overlaps),
            "avg_immediate_overlap": safe_avg([float(value) for value in overlaps]),
            "dominant_immediate_overlap": int(overlap_counts.most_common(1)[0][0]),
            "dominant_immediate_overlaps": [int(value) for value in tied_dominants(overlap_counts)],
        },
        "pair_companion_profile": {
            "pair_companion_counts": {"-".join(map(str, pair)): count for pair, count in pair_counts.most_common() if count >= 2},
            "top_pair_companions": companion_rows[:30],
            "pair_companion_candidates": companion_rows[:60],
        },
        "number_frequency": {str(number): count for number, count in sorted(number_counts.items())},
        "top_recent_numbers": top_recent_numbers,
        "summary_es": " ".join(summary_notes),
    }


def pair_set(profile: dict[str, Any], limit: int = 8) -> set[str]:
    rows = profile.get("pair_companion_profile", {}).get("top_pair_companions", [])[:limit]
    return {"-".join(map(str, row.get("pair", []))) for row in rows if len(row.get("pair", [])) == 2}


def number_set(profile: dict[str, Any], limit: int = 12) -> set[int]:
    return {int(row["number"]) for row in profile.get("top_recent_numbers", [])[:limit] if "number" in row}


def shift_between(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return any(
        (
            left.get("sum_profile", {}).get("dominant_sum_band") != right.get("sum_profile", {}).get("dominant_sum_band"),
            left.get("presence_signature_profile", {}).get("dominant_presence_signature") != right.get("presence_signature_profile", {}).get("dominant_presence_signature"),
            left.get("immediate_overlap_profile", {}).get("dominant_immediate_overlap") != right.get("immediate_overlap_profile", {}).get("dominant_immediate_overlap"),
            pair_set(left) != pair_set(right),
            number_set(left) != number_set(right),
        )
    )


def describe_shift(label: str, left: dict[str, Any], right: dict[str, Any], path: tuple[str, ...]) -> str:
    value: Any = left
    other: Any = right
    for key in path:
        value = value.get(key, {}) if isinstance(value, dict) else {}
        other = other.get(key, {}) if isinstance(other, dict) else {}
    if value == other:
        return f"{label}: sin cambio."
    return f"{label}: {value} frente a {other}."


def build_recent_regime_summary(windows: dict[str, dict[str, Any]], winner_profile_path: str = "v4_winner_profile.json") -> dict[str, Any]:
    window_5 = windows["5"]
    window_20 = windows["20"]
    window_30 = windows["30"]
    summary = {
        "window_5_vs_20_shift": shift_between(window_5, window_20),
        "window_20_vs_30_shift": shift_between(window_20, window_30),
        "sum_band_shift_es": " | ".join(
            [
                describe_shift("5 vs 20", window_5, window_20, ("sum_profile", "dominant_sum_band")),
                describe_shift("20 vs 30", window_20, window_30, ("sum_profile", "dominant_sum_band")),
            ]
        ),
        "presence_shift_es": " | ".join(
            [
                describe_shift("5 vs 20", window_5, window_20, ("presence_signature_profile", "dominant_presence_signature")),
                describe_shift("20 vs 30", window_20, window_30, ("presence_signature_profile", "dominant_presence_signature")),
            ]
        ),
        "pair_companion_shift_es": (
            "Pares companion recientes cambian entre ventanas."
            if pair_set(window_5) != pair_set(window_20) or pair_set(window_20) != pair_set(window_30)
            else "Pares companion: sin cambio relevante entre ventanas."
        ),
        "interpretation_es": "Lectura diagnóstica de cambio reciente de micro-régimen. No implica promesa de resultado futuro.",
    }
    winner_path = Path(winner_profile_path)
    if winner_path.exists():
        winner = json.loads(winner_path.read_text(encoding="utf-8"))
        historical_band = winner.get("sum_profile", {}).get("dominant_sum_band")
        historical_presence = winner.get("presence_signature_profile", {}).get("dominant_presence_signature")
        window_30_shift = (
            window_30.get("sum_profile", {}).get("dominant_sum_band") != historical_band
            or window_30.get("presence_signature_profile", {}).get("dominant_presence_signature") != historical_presence
        )
        summary["window_30_vs_historical_shift"] = bool(window_30_shift)
        summary["historical_shift_es"] = (
            f"Ventana 30 comparada con histórico: suma {window_30.get('sum_profile', {}).get('dominant_sum_band')} vs {historical_band}; "
            f"presencia {window_30.get('presence_signature_profile', {}).get('dominant_presence_signature')} vs {historical_presence}."
        )
    return summary


def build_recent_profile(csv_path: str, window: int = LEGACY_WINDOW) -> dict[str, Any]:
    draws = read_history_csv(csv_path)
    windows = {str(size): build_window_profile(draws, csv_path, size) for size in WINDOWS}
    legacy = windows[str(LEGACY_WINDOW)]
    report = {
        "generated_at": utc_now(),
        "engine_version": ENGINE_VERSION,
        "production_status": PRODUCTION_STATUS,
        "source_file": csv_path,
        "source_sha256": file_sha256(csv_path),
        "window": legacy["window"],
        "latest_draw": legacy["latest_draw"],
        "latest_draw_numbers": legacy["latest_draw_numbers"],
        "draws_used": legacy["draws_used"],
        "sum_profile": legacy["sum_profile"],
        "parity_profile": legacy["parity_profile"],
        "presence_signature_profile": legacy["presence_signature_profile"],
        "immediate_overlap_profile": legacy["immediate_overlap_profile"],
        "pair_companion_profile": legacy["pair_companion_profile"],
        "number_frequency_recent_30": legacy["number_frequency"],
        "top_recent_numbers": legacy["top_recent_numbers"],
        "summary_es": legacy["summary_es"],
        "windows": windows,
        "recent_regime_summary": build_recent_regime_summary(windows),
    }
    if window != LEGACY_WINDOW:
        report["requested_window_compatibility_note_es"] = (
            f"Se solicitó window={window}, pero el contrato PR #40 conserva raíz legacy window=30 y agrega windows 5/20/30."
        )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Build V4.4 recent composition profile.")
    parser.add_argument("--csv", default="revancha.csv")
    parser.add_argument("--window", type=int, default=LEGACY_WINDOW)
    parser.add_argument("--output", default="v4_recent_composition_profile.json")
    args = parser.parse_args()
    report = build_recent_profile(args.csv, args.window)
    write_json(args.output, report)
    print(
        f"Wrote {args.output}; windows={','.join(report['windows'].keys())} "
        f"legacy_window={report['window']} latest_draw={report['latest_draw']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
