# -*- coding: utf-8 -*-
"""V4.3 Hybrid Composition Engine: role-based Revancha ticket slate."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from v4_visual_pattern_features import gap_echo_score, pair_lag_scores, pair_lag_validation, recent_z_scores, zone_activation
from v4_winner_composition_audit import (
    BLOCKS,
    DRAW_SIZE,
    MAX_NUMBER,
    block_counts,
    load_v42_ranking,
    parity_counts,
    read_revancha_csv,
    utc_now,
)


ENGINE_VERSION = "V4.3-hybrid-composition"
PRODUCTION_STATUS = "review_default"
DISCLAIMER = "Experimental composition ranking for review only."
TICKET_TYPES = [
    "composition_main",
    "activated_block_main",
    "pair_lag_bridge",
    "balanced_hybrid",
    "contrarian_controlled",
    "cold_companion_high_edge",
]
FORBIDDEN_LANGUAGE = ("guaranteed", "probability_model", "winning_model", "winning chance")


def _block_name(number: int) -> str:
    for name, values in BLOCKS.items():
        if number in values:
            return name
    return "unknown"


def _unique(numbers: list[int]) -> list[int]:
    output: list[int] = []
    for number in numbers:
        if 1 <= number <= MAX_NUMBER and number not in output:
            output.append(number)
    return output


def _avg(values: list[float]) -> float:
    return round(sum(values) / len(values), 6) if values else 0.0


def _activation_metric(activation: dict[str, Any], block: str, key: str) -> float:
    row = activation.get(block, {})
    if isinstance(row, dict):
        try:
            return float(row.get(key, 0.0) or 0.0)
        except (TypeError, ValueError):
            return 0.0
    try:
        return float(row or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _candidate_rows_from_draws(
    draws: list[dict[str, Any]],
    ranking: list[int] | None = None,
    pair_lag_mode: str | None = None,
) -> list[dict[str, Any]]:
    if not draws:
        return []
    ranking = ranking or []
    latest = draws[-1]
    activation = zone_activation(draws)
    z_scores = recent_z_scores(draws)
    pair_scores = pair_lag_scores(draws[:-1], latest["numbers"])
    if pair_lag_mode is None:
        pair_validation = pair_lag_validation(draws)
        pair_lag_mode = str(pair_validation.get("status", "disabled_by_validation"))
    latest_numbers = set(latest["numbers"])
    rows: list[dict[str, Any]] = []
    frequency = Counter(number for draw in draws[-15:] for number in draw["numbers"])

    for number in range(1, MAX_NUMBER + 1):
        roles: set[str] = set()
        reasons: list[str] = []
        gap_score, gap_reason = gap_echo_score(draws, number)
        pair = pair_scores.get(number, {"score": 0.0, "strong": False, "hit_rate": 0.0, "triggers": 0, "hits": 0})
        block = _block_name(number)
        zone_score = _activation_metric(activation, block, "unique_activation")
        hit_density = _activation_metric(activation, block, "hit_density")
        generic_bridge_support = bool(pair.get("strong") and zone_score >= 0.40 and (gap_score >= 0.35 or number not in latest_numbers))
        block_score = 1.0 if zone_score >= 0.40 or z_scores[number] > 2 or generic_bridge_support else min(zone_score * 1.5, 1.0)
        carryover_penalty = 0.22 if number in latest_numbers and not generic_bridge_support and gap_score < 0.70 else 0.0
        cold_score = 0.20 if frequency[number] <= 1 and len(draws) >= 18 and (generic_bridge_support or zone_score >= 0.35) else 0.0
        support_score = frequency[number] / max(len(draws[-15:]), 1)

        if generic_bridge_support and pair_lag_mode == "promoter":
            roles.add("bridge_pair_lag")
            reasons.append(f"Validated pair-lag bridge from {pair.get('best_trigger')} with {pair.get('hits')}/{pair.get('triggers')} lag hits.")
        elif pair.get("strong") and pair_lag_mode == "support_only":
            roles.add("support")
            reasons.append("Pair-lag evidence downgraded to support by walk-forward validation.")
        if zone_score >= 0.40:
            roles.add("activated_block")
            reasons.append(f"Active block {block} by recent unique activation.")
        if block_score >= 0.70:
            roles.add("block_completion")
        if gap_reason:
            roles.add("gap_echo")
            reasons.append(gap_reason)
        if cold_score:
            roles.add("cold_companion")
            reasons.append("Controlled cold companion connected to active local evidence.")
        if ranking and number in ranking[:20]:
            roles.add("v42_signal_optional")
        if not roles:
            roles.add("support")

        score = (
            float(pair.get("score", 0.0)) * (0.36 if pair_lag_mode == "promoter" else 0.12 if pair_lag_mode == "support_only" else 0.02)
            + zone_score * 0.92
            + hit_density * 0.18
            + block_score * 0.17
            + gap_score * 0.18
            + support_score * 0.18
            + cold_score
            - carryover_penalty
        )
        rows.append(
            {
                "number": number,
                "score": round(max(score, 0.0), 6),
                "roles": sorted(roles),
                "signals": {
                    "gap_echo": gap_score,
                    "pair_lag": float(pair.get("score", 0.0)),
                    "zone_activation": zone_score,
                    "unique_activation": zone_score,
                    "hit_density": hit_density,
                    "block_completion": round(block_score, 6),
                    "carryover_penalty": carryover_penalty,
                    "cold_companion": cold_score,
                    "recent_frequency": round(support_score, 6),
                },
                "reasons": reasons[:4],
            }
        )
    return sorted(rows, key=lambda row: (-row["score"], row["number"]))


def _merge_visual_rows(visual_report: dict[str, Any] | None, fallback_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not visual_report:
        return fallback_rows
    rows = visual_report.get("top_visual_candidates")
    if not isinstance(rows, list) or not rows:
        return fallback_rows
    normalized = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        number = row.get("number")
        if not isinstance(number, int) or not (1 <= number <= MAX_NUMBER):
            continue
        normalized.append(
            {
                "number": number,
                "score": float(row.get("visual_score") or 0.0),
                "roles": list(row.get("roles") or ["support"]),
                "signals": dict(row.get("signals") or {}),
                "reasons": list(row.get("reasons") or []),
            }
        )
    seen = {row["number"] for row in normalized}
    normalized.extend(row for row in fallback_rows if row["number"] not in seen)
    return sorted(normalized, key=lambda row: (-row["score"], row["number"]))


def _role_index(rows: list[dict[str, Any]]) -> dict[str, list[int]]:
    index: dict[str, list[int]] = {}
    for row in rows:
        for role in row["roles"]:
            index.setdefault(role, []).append(row["number"])
    return index


def _find_row(rows: list[dict[str, Any]], number: int) -> dict[str, Any]:
    for row in rows:
        if row["number"] == number:
            return row
    return {"number": number, "roles": ["support"], "score": 0.0, "signals": {}, "reasons": []}


def _complete_ticket(seed: list[int], rows: list[dict[str, Any]], previous_numbers: set[int], max_carryover: int = 1) -> list[int]:
    ticket = _unique(seed)
    for row in rows:
        number = row["number"]
        if number in ticket:
            continue
        would_carry = number in previous_numbers
        current_carry = len(set(ticket) & previous_numbers)
        justified = bool({"bridge_pair_lag", "gap_echo"} & set(row["roles"]))
        if would_carry and current_carry >= max_carryover and not justified:
            continue
        ticket.append(number)
        if len(ticket) == DRAW_SIZE:
            break
    return sorted(ticket[:DRAW_SIZE])


def _composition(numbers: list[int], previous_numbers: set[int]) -> dict[str, Any]:
    parity = parity_counts(numbers)
    return {
        "parity": parity,
        "sum": sum(numbers),
        "blocks": block_counts(numbers),
        "immediate_overlap_previous_draw": len(set(numbers) & previous_numbers),
    }


def _ticket(
    ticket_type: str,
    numbers: list[int],
    rows: list[dict[str, Any]],
    previous_numbers: set[int],
    index: int,
    reason: str,
) -> dict[str, Any]:
    roles: dict[str, list[str]] = {}
    reasons: dict[str, list[str]] = {}
    for position, number in enumerate(numbers):
        row = _find_row(rows, number)
        number_roles = list(row["roles"])
        if position == 0:
            number_roles = _unique_text(["anchor"] + number_roles)
        elif "support" not in number_roles:
            number_roles = _unique_text(["support"] + number_roles)
        roles[str(number)] = number_roles
        reasons[str(number)] = row.get("reasons") or ["Selected by V4.3 composition role balance."]
    return {
        "ticket_id": f"{ticket_type}_{index}",
        "ticket_type": ticket_type,
        "numbers": numbers,
        "roles": roles,
        "reasons": reasons,
        "composition": _composition(numbers, previous_numbers),
        "reason": reason,
        "risk_notes": [
            "Review-default composition slate.",
            "Outcome-neutral review layer.",
        ],
    }


def _unique_text(values: list[str]) -> list[str]:
    output: list[str] = []
    for value in values:
        if value not in output:
            output.append(value)
    return output


def compose_slate_from_rows(rows: list[dict[str, Any]], previous_draw: list[int]) -> list[dict[str, Any]]:
    previous_numbers = set(previous_draw)
    role_index = _role_index(rows)
    top = [row["number"] for row in rows]
    active_blocks = Counter(_block_name(number) for number in role_index.get("activated_block", []))
    focus_block = active_blocks.most_common(1)[0][0] if active_blocks else "21_30"
    focus_numbers = [row["number"] for row in rows if _block_name(row["number"]) == focus_block]
    bridge = role_index.get("bridge_pair_lag", [])
    gap = role_index.get("gap_echo", [])
    cold = role_index.get("cold_companion", [])
    v42 = role_index.get("v42_signal_optional", [])

    seeds = [
        ("composition_main", _unique((bridge[:2] + focus_numbers[:2] + gap[:1] + cold[:1] + top[:6]))),
        ("activated_block_main", _unique((focus_numbers[:3] + bridge[:2] + top[:6]))),
        ("pair_lag_bridge", _unique((bridge[:3] + gap[:2] + focus_numbers[:2] + top[:6]))),
        ("balanced_hybrid", _unique((top[:2] + focus_numbers[:2] + gap[:1] + v42[:1] + cold[:1] + top[:10]))),
        ("contrarian_controlled", _unique((cold[:1] + gap[:2] + bridge[:1] + top[8:18] + top[:6]))),
        ("cold_companion_high_edge", _unique((cold[:2] + bridge[:2] + focus_numbers[:2] + top[:8]))),
    ]

    tickets: list[dict[str, Any]] = []
    used: list[set[int]] = []
    for idx, (ticket_type, seed) in enumerate(seeds, start=1):
        offset = min((idx - 1) * 4, max(len(rows) - 1, 0))
        fill_rows = rows[offset:] + rows[:offset]
        numbers = _complete_ticket(seed, fill_rows, previous_numbers)
        if len(numbers) != DRAW_SIZE:
            continue
        if used and any(set(numbers) == existing for existing in used):
            continue
        used.append(set(numbers))
        tickets.append(
            _ticket(
                ticket_type,
                numbers,
                rows,
                previous_numbers,
                idx,
                "Composed by V4.3 roles: bridge/block/gap/cold companion with parity and sum as soft checks.",
            )
        )
    if len(tickets) < 5:
        used_types = {ticket["ticket_type"] for ticket in tickets}
        for idx, ticket_type in enumerate(TICKET_TYPES, start=1):
            if ticket_type in used_types:
                continue
            offset = min(idx * 5, max(len(rows) - 1, 0))
            fill_rows = rows[offset:] + rows[:offset]
            seed = [row["number"] for row in fill_rows[:10]]
            numbers = _complete_ticket(seed, fill_rows, previous_numbers, max_carryover=2)
            if len(numbers) != DRAW_SIZE or any(set(numbers) == existing for existing in used):
                continue
            used.append(set(numbers))
            tickets.append(
                _ticket(
                    ticket_type,
                    numbers,
                    rows,
                    previous_numbers,
                    idx,
                    "Fallback V4.3 role composition variant to keep the review slate broad but still role-scored.",
                )
            )
            if len(tickets) >= 5:
                break
    return tickets[:6]


def _load_json(path: str | Path) -> dict[str, Any] | None:
    json_path = Path(path)
    if not json_path.exists():
        return None
    try:
        return json.loads(json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _hits(ticket: list[int], target: list[int]) -> int:
    return len(set(ticket) & set(target))


def _pattern_match(ticket: list[int], target: list[int]) -> bool:
    ticket_blocks = block_counts(ticket)
    target_blocks = block_counts(target)
    return sum(abs(ticket_blocks[key] - target_blocks[key]) for key in BLOCKS) <= 4


def walk_forward_validation(draws: list[dict[str, Any]], ranking: list[int], pair_lag_mode: str | None = None) -> dict[str, Any]:
    if len(draws) < 35:
        return {"available": False, "reason": "insufficient history for walk-forward validation"}
    start = max(30, len(draws) - 60)
    ticket_hits: list[int] = []
    best_hits: list[int] = []
    ge1 = ge2 = ge3 = zeros = 0
    role_hits: Counter[str] = Counter()
    role_total: Counter[str] = Counter()
    carry_hits = carry_total = 0
    pattern_matches = 0
    v42_rescues = 0

    for index in range(start, len(draws)):
        pre = draws[:index]
        target = draws[index]["numbers"]
        rows = _candidate_rows_from_draws(pre, ranking, pair_lag_mode=pair_lag_mode)
        slate = compose_slate_from_rows(rows, pre[-1]["numbers"])
        if not slate:
            continue
        draw_best = 0
        for ticket in slate:
            hits = _hits(ticket["numbers"], target)
            ticket_hits.append(float(hits))
            draw_best = max(draw_best, hits)
            ge1 += int(hits >= 1)
            ge2 += int(hits >= 2)
            ge3 += int(hits >= 3)
            zeros += int(hits == 0)
            pattern_matches += int(_pattern_match(ticket["numbers"], target))
            for number in ticket["numbers"]:
                for role in ticket["roles"].get(str(number), []):
                    role_total[role] += 1
                    role_hits[role] += int(number in target)
                if number in set(pre[-1]["numbers"]):
                    carry_total += 1
                    carry_hits += int(number in target)
        best_hits.append(float(draw_best))
        if ranking:
            outside_top10 = set(target) - set(ranking[:10])
            selected = set(number for ticket in slate for number in ticket["numbers"])
            v42_rescues += len(outside_top10 & selected)

    total_tickets = max(len(ticket_hits), 1)
    total_draws = max(len(best_hits), 1)
    return {
        "available": True,
        "draws_evaluated": len(best_hits),
        "avg_hits_per_ticket": _avg(ticket_hits),
        "best_ticket_hits_per_draw": _avg(best_hits),
        "hit_ge_1_rate": round(ge1 / total_tickets, 6),
        "hit_ge_2_rate": round(ge2 / total_tickets, 6),
        "hit_ge_3_rate": round(ge3 / total_tickets, 6),
        "zero_rate": round(zeros / total_tickets, 6),
        "rescued_winners_outside_v42_top10": v42_rescues if ranking else None,
        "activated_block_hit_rate": round(role_hits["activated_block"] / role_total["activated_block"], 6) if role_total["activated_block"] else 0.0,
        "pair_lag_bridge_hit_rate": round(role_hits["bridge_pair_lag"] / role_total["bridge_pair_lag"], 6) if role_total["bridge_pair_lag"] else 0.0,
        "immediate_carryover_hit_rate": round(carry_hits / carry_total, 6) if carry_total else 0.0,
        "composition_pattern_match_rate": round(pattern_matches / total_tickets, 6),
    }


def build_slate(
    csv_path: str | Path = "revancha.csv",
    audit_path: str | Path = "v4_winner_composition_audit.json",
    visual_path: str | Path = "v4_visual_pattern_output.json",
    resultados_path: str | Path = "resultados.json",
) -> dict[str, Any]:
    draws = read_revancha_csv(csv_path)
    if not draws:
        raise SystemExit(f"No valid Revancha draws found in {csv_path}.")
    ranking, v42_available, v42_warning = load_v42_ranking(resultados_path)
    audit = _load_json(audit_path)
    visual = _load_json(visual_path)
    pair_lag_mode = visual.get("pair_lag_mode") if isinstance(visual, dict) else pair_lag_validation(draws).get("status")
    rows = _merge_visual_rows(visual, _candidate_rows_from_draws(draws, ranking, pair_lag_mode=pair_lag_mode))
    slate = compose_slate_from_rows(rows, draws[-1]["numbers"])
    warnings = []
    if v42_warning:
        warnings.append(v42_warning)
    if audit is None:
        warnings.append("Composition audit not available; engine used direct CSV features.")
    if visual is None:
        warnings.append("Visual pattern output not available; engine recomputed direct CSV features.")
    validation = walk_forward_validation(draws, ranking, pair_lag_mode=pair_lag_mode)

    return {
        "generated_at": utc_now(),
        "engine_version": ENGINE_VERSION,
        "source_policy": {
            "primary_source": str(csv_path),
            "v42_signal_available": v42_available,
            "v42_signal_used_as": "auxiliary_optional" if v42_available else "not_used",
            "fallback_mode": None if v42_available else "csv_visual_composition_only",
            "pair_lag_mode": pair_lag_mode,
        },
        "production_status": PRODUCTION_STATUS,
        "disclaimer": DISCLAIMER,
        "latest_draw": draws[-1]["draw_id"],
        "slate": slate,
        "validation_summary": validation,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build V4.3 hybrid composition slate.")
    parser.add_argument("--csv", default="revancha.csv")
    parser.add_argument("--audit", default="v4_winner_composition_audit.json")
    parser.add_argument("--visual", default="v4_visual_pattern_output.json")
    parser.add_argument("--resultados", default="resultados.json")
    parser.add_argument("--output", default="v4_hybrid_composition_slate.json")
    args = parser.parse_args()
    report = build_slate(args.csv, args.audit, args.visual, args.resultados)
    Path(args.output).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {args.output}; tickets={len(report['slate'])} production_status={report['production_status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
