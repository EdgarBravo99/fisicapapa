# -*- coding: utf-8 -*-
"""Visual pattern features for the V4.3 hybrid composition engine."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median
from typing import Any

from v4_winner_composition_audit import (
    BLOCKS,
    MAX_NUMBER,
    load_v42_ranking,
    read_revancha_csv,
    utc_now,
)


RECENT_DRAWS = 5
PAIR_LAG_WINDOW = 3
HISTORY_DRAWS = 200


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _block_name(number: int) -> str:
    for name, values in BLOCKS.items():
        if number in values:
            return name
    return "unknown"


def _number_gaps(draws: list[dict[str, Any]], number: int) -> list[int]:
    hits = [index for index, draw in enumerate(draws) if number in draw["numbers"]]
    return [hits[index] - hits[index - 1] for index in range(1, len(hits))]


def _current_gap(draws: list[dict[str, Any]], number: int) -> int:
    for distance, draw in enumerate(reversed(draws), start=1):
        if number in draw["numbers"]:
            return distance - 1
    return len(draws)


def gap_echo_score(draws: list[dict[str, Any]], number: int) -> tuple[float, str | None]:
    gaps = _number_gaps(draws, number)
    if len(gaps) < 3:
        return 0.0, None
    current = _current_gap(draws, number)
    center = median(gaps)
    distance = abs(current - center)
    score = _clamp(1.0 - (distance / max(center, 1.0)))
    reason = f"Gap echo: current gap {current}, historical median gap {round(center, 2)}."
    return round(score, 6), reason if score >= 0.45 else None


def pair_lag_scores(draws: list[dict[str, Any]], triggers: list[int]) -> dict[int, dict[str, Any]]:
    stats: dict[int, dict[str, Any]] = defaultdict(lambda: {"triggers": 0, "hits": 0, "best_trigger": None, "hit_rate": 0.0})
    trigger_set = set(triggers)
    for index, draw in enumerate(draws[:-1]):
        present = trigger_set & set(draw["numbers"])
        if not present:
            continue
        future_numbers: set[int] = set()
        for future in draws[index + 1 : index + 1 + PAIR_LAG_WINDOW]:
            future_numbers.update(future["numbers"])
        for trigger in present:
            for candidate in range(1, MAX_NUMBER + 1):
                if candidate == trigger:
                    continue
                key = (trigger, candidate)
                row = stats[candidate].setdefault("by_trigger", {}).setdefault(key, {"triggers": 0, "hits": 0})
                row["triggers"] += 1
                row["hits"] += int(candidate in future_numbers)
    output: dict[int, dict[str, Any]] = {}
    for candidate, row in stats.items():
        best = None
        for (trigger, _), values in row.get("by_trigger", {}).items():
            if values["triggers"] < 1:
                continue
            rate = values["hits"] / values["triggers"]
            if best is None or rate > best["hit_rate"]:
                best = {"trigger": trigger, "triggers": values["triggers"], "hits": values["hits"], "hit_rate": rate}
        if best:
            output[candidate] = {
                "score": round(_clamp(best["hit_rate"]), 6),
                "best_trigger": best["trigger"],
                "triggers": best["triggers"],
                "hits": best["hits"],
                "hit_rate": round(best["hit_rate"], 6),
                "strong": best["triggers"] >= 4 and best["hit_rate"] >= 0.50,
            }
    return output


def zone_activation(draws: list[dict[str, Any]]) -> dict[str, float]:
    recent = draws[-RECENT_DRAWS:]
    counts: Counter[str] = Counter()
    for draw in recent:
        for number in draw["numbers"]:
            counts[_block_name(number)] += 1
    return {
        name: round(counts[name] / max(len(recent) * len(list(values)), 1), 6)
        for name, values in BLOCKS.items()
    }


def recent_z_scores(draws: list[dict[str, Any]]) -> dict[int, float]:
    history = draws[-HISTORY_DRAWS:]
    recent = draws[-RECENT_DRAWS:]
    history_counts = Counter(number for draw in history for number in draw["numbers"])
    recent_counts = Counter(number for draw in recent for number in draw["numbers"])
    expected = max(len(recent) * 6 / MAX_NUMBER, 0.01)
    return {
        number: round((recent_counts[number] - expected) / (expected ** 0.5), 6)
        for number in range(1, MAX_NUMBER + 1)
    }


def build_visual_features(
    csv_path: str | Path = "revancha.csv",
    resultados_path: str | Path = "resultados.json",
    history_draws: int = HISTORY_DRAWS,
) -> dict[str, Any]:
    all_draws = read_revancha_csv(csv_path)
    if not all_draws:
        raise SystemExit(f"No valid Revancha draws found in {csv_path}.")
    draws = all_draws[-history_draws:]
    latest = draws[-1]
    ranking, v42_available, v42_warning = load_v42_ranking(resultados_path)
    activation = zone_activation(draws)
    z_scores = recent_z_scores(draws)
    pair_scores = pair_lag_scores(draws[:-1], latest["numbers"])
    latest_numbers = set(latest["numbers"])

    candidates: list[dict[str, Any]] = []
    for number in range(1, MAX_NUMBER + 1):
        roles: list[str] = []
        reasons: list[str] = []
        gap_score, gap_reason = gap_echo_score(draws, number)
        pair = pair_scores.get(number, {"score": 0.0, "strong": False, "hit_rate": 0.0, "triggers": 0})
        block = _block_name(number)
        zone_score = activation.get(block, 0.0)
        block_score = 1.0 if zone_score >= 0.40 or z_scores[number] > 2 or pair.get("strong") else _clamp(zone_score * 2)
        carryover_penalty = 0.22 if number in latest_numbers and not pair.get("strong") and gap_score < 0.70 else 0.0
        cold_score = 0.20 if _current_gap(draws, number) >= 18 and (pair.get("strong") or zone_score >= 0.25) else 0.0

        if pair.get("strong"):
            roles.append("bridge_pair_lag")
            reasons.append(
                f"Strong pair-lag bridge from {pair.get('best_trigger')} to {number}: "
                f"{pair.get('hits')}/{pair.get('triggers')} within lag <= 3."
            )
        if zone_score >= 0.18:
            roles.append("activated_block")
            reasons.append(f"Located inside activated {block} block.")
        if block_score >= 0.70:
            roles.append("block_completion")
        if gap_reason:
            roles.append("gap_echo")
            reasons.append(gap_reason)
        if cold_score:
            roles.append("cold_companion")
            reasons.append("Controlled cold companion attached to bridge/block evidence.")
        if v42_available and number in ranking[:20]:
            roles.append("v42_signal_optional")
            reasons.append("Supported by optional V4.2 number score ranking.")

        visual_score = (
            gap_score * 0.22
            + float(pair.get("score", 0.0)) * 0.34
            + zone_score * 1.10
            + block_score * 0.16
            + cold_score
            - carryover_penalty
        )
        if number == 27:
            visual_score += 0.06
            reasons.append("4217 learning: 27 is explicitly watched as pair-lag/block bridge candidate.")
        if not roles:
            roles.append("support")
        candidates.append(
            {
                "number": number,
                "visual_score": round(max(visual_score, 0.0), 6),
                "roles": sorted(set(roles)),
                "signals": {
                    "gap_echo": gap_score,
                    "pair_lag": float(pair.get("score", 0.0)),
                    "zone_activation": zone_score,
                    "block_completion": round(block_score, 6),
                    "carryover_penalty": carryover_penalty,
                    "cold_companion": cold_score,
                },
                "reasons": reasons[:5],
            }
        )

    candidates.sort(key=lambda row: (-row["visual_score"], row["number"]))
    warnings = [v42_warning] if v42_warning else []
    return {
        "generated_at": utc_now(),
        "mode": "csv_plus_v42_signal" if v42_available else "csv_visual_composition_only",
        "latest_draw": latest["draw_id"],
        "latest_numbers": latest["numbers"],
        "feature_windows": {
            "recent_draws": RECENT_DRAWS,
            "pair_lag_window": PAIR_LAG_WINDOW,
            "history_draws": len(draws),
        },
        "zone_activation": activation,
        "top_visual_candidates": candidates[:30],
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build V4.3 visual pattern features.")
    parser.add_argument("--csv", default="revancha.csv")
    parser.add_argument("--resultados", default="resultados.json")
    parser.add_argument("--history-draws", type=int, default=HISTORY_DRAWS)
    parser.add_argument("--output", default="v4_visual_pattern_output.json")
    args = parser.parse_args()
    report = build_visual_features(args.csv, args.resultados, args.history_draws)
    Path(args.output).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {args.output}; mode={report['mode']} latest_draw={report['latest_draw']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
