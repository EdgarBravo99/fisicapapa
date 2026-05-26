# -*- coding: utf-8 -*-
"""Final V4.4 combination constructor: formed tickets, not top-score picks."""

from __future__ import annotations

import argparse
import itertools
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from v4_history_common import (
    BLOCK_ORDER,
    DRAW_SIZE,
    MAX_NUMBER,
    PRODUCTION_STATUS,
    SUM_BAND_ES,
    block_counts,
    block_signature,
    file_sha256,
    parity_label,
    presence_signature,
    read_history_csv,
    sum_band,
    utc_now,
    visual_structure_label_es,
    write_json,
)


ENGINE_VERSION = "v4.4-combination-constructor"
TICKET_TYPES = [
    "pair_sum_structure",
    "recent_signature_fit",
    "block_completion_main",
    "pair_companion_bridge",
    "controlled_contrarian",
]
SIGNAL_WEIGHTS = {
    "gap_echo": 1.2,
    "signature_history": 1.05,
    "pair_lag_candidate": 1.1,
    "pair_lag_trigger": 0.85,
    "pair_companion": 1.15,
    "block_completion": 1.0,
    "recent_frequency": 0.55,
    "winner_profile_fit": 0.45,
    "structure_completion": 0.9,
    "zone_fit": 0.7,
}


def load_json(path: str) -> dict[str, Any]:
    json_path = Path(path)
    if not json_path.exists():
        raise SystemExit(f"Missing required constructor input: {path}")
    data = json.loads(json_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"Expected JSON object in {path}")
    if data.get("production_status") != PRODUCTION_STATUS:
        raise SystemExit(f"{path} must have production_status={PRODUCTION_STATUS}")
    return data


def add_signal(signals: dict[int, set[str]], number: int, signal: str) -> None:
    if 1 <= int(number) <= MAX_NUMBER:
        signals[int(number)].add(signal)


def pair_key(a: int, b: int) -> tuple[int, int]:
    return tuple(sorted((int(a), int(b))))


def latest_numbers_from_history() -> list[int]:
    matrix_path = Path("v4_history_matrix.json")
    if matrix_path.exists():
        matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
        rows = matrix.get("matrix") or []
        if rows:
            return [index + 1 for index, value in enumerate(rows[-1]) if int(value) == 1]
    draws = read_history_csv("revancha.csv")
    return draws[-1]["numbers"] if draws else []


def build_signal_pool(inputs: dict[str, dict[str, Any]]) -> tuple[dict[int, set[str]], dict[int, float], set[tuple[int, int]], set[tuple[int, int]]]:
    signals: dict[int, set[str]] = defaultdict(set)
    weights: dict[int, float] = defaultdict(float)
    pair_companions: set[tuple[int, int]] = set()
    pair_lag_pairs: set[tuple[int, int]] = set()

    gap = inputs["gap"]
    for raw_number, row in (gap.get("numbers") or {}).items():
        number = int(raw_number)
        score = float(row.get("gap_echo_score") or 0.0)
        if row.get("in_active_window") or number in gap.get("active_candidates", []) or score >= 0.58:
            add_signal(signals, number, "gap_echo")
            weights[number] += score * SIGNAL_WEIGHTS["gap_echo"]

    signature = inputs["signature"]
    for raw_number, row in (signature.get("numbers_after") or {}).items():
        number = int(raw_number)
        count = int(row.get("count") or 0)
        if count > 0:
            add_signal(signals, number, "signature_history")
            add_signal(signals, number, "structure_completion")
            weights[number] += min(count / 10, 1.0) * (SIGNAL_WEIGHTS["signature_history"] + 0.25)

    pair_lag = inputs["pair_lag"]
    for row in pair_lag.get("signals", [])[:220]:
        trigger = int(row["trigger"])
        candidate = int(row["candidate"])
        score = float(row.get("pair_lag_score") or 0.0)
        add_signal(signals, trigger, "pair_lag_trigger")
        add_signal(signals, candidate, "pair_lag_candidate")
        weights[trigger] += score * SIGNAL_WEIGHTS["pair_lag_trigger"]
        weights[candidate] += score * SIGNAL_WEIGHTS["pair_lag_candidate"]
        pair_lag_pairs.add((trigger, candidate))
    for number in pair_lag.get("active_candidates", []):
        add_signal(signals, int(number), "pair_lag_candidate")
        weights[int(number)] += 0.35

    block_completion = inputs["block_completion"]
    for row in block_completion.get("groups", []):
        score = float(row.get("block_completion_score") or 0.0)
        for number in row.get("missing", []):
            add_signal(signals, int(number), "block_completion")
            weights[int(number)] += max(score, 0.12) * SIGNAL_WEIGHTS["block_completion"]
        for number in row.get("recent_seen", []):
            add_signal(signals, int(number), "structure_completion")
            weights[int(number)] += 0.18
    for row in block_completion.get("candidates", []):
        number = int(row.get("number") if isinstance(row, dict) else row)
        add_signal(signals, number, "block_completion")
        weights[number] += 0.2

    recent = inputs["recent"]
    for row in recent.get("pair_companion_profile", {}).get("pair_companion_candidates", [])[:60]:
        pair = row.get("pair") or []
        if len(pair) == 2:
            a, b = int(pair[0]), int(pair[1])
            pair_companions.add(pair_key(a, b))
            add_signal(signals, a, "pair_companion")
            add_signal(signals, b, "pair_companion")
            score = float(row.get("pair_companion_score") or 0.0)
            weights[a] += max(score, 0.05) * SIGNAL_WEIGHTS["pair_companion"]
            weights[b] += max(score, 0.05) * SIGNAL_WEIGHTS["pair_companion"]
    for row in recent.get("top_recent_numbers", [])[:28]:
        number = int(row["number"])
        add_signal(signals, number, "recent_frequency")
        weights[number] += float(row.get("recent_frequency_score") or 0.0) * SIGNAL_WEIGHTS["recent_frequency"]

    dominant_presence = recent.get("presence_signature_profile", {}).get("dominant_presence_signature")
    winner_presence = inputs["winner"].get("presence_signature_profile", {}).get("dominant_presence_signature")
    target_presence = str(dominant_presence or winner_presence or "1-1-1-0-1").split("-")
    for index, flag in enumerate(target_presence[: len(BLOCK_ORDER)]):
        if flag == "1":
            block = BLOCK_ORDER[index]
            for number in range(1, MAX_NUMBER + 1):
                if number in set(range_from_block(block)):
                    add_signal(signals, number, "zone_fit")
                    weights[number] += 0.04
    for number in list(signals):
        add_signal(signals, number, "winner_profile_fit")
        weights[number] += 0.03

    return signals, weights, pair_companions, pair_lag_pairs


def range_from_block(block: str) -> range:
    if block == "1_10":
        return range(1, 11)
    if block == "11_20":
        return range(11, 21)
    if block == "21_30":
        return range(21, 31)
    if block == "31_40":
        return range(31, 41)
    return range(41, 57)


def candidate_score(number: int, signals: dict[int, set[str]], weights: dict[int, float]) -> float:
    return round(weights[number] + len(signals[number]) * 0.08, 6)


def ticket_pair_counts(numbers: list[int], companion_pairs: set[tuple[int, int]], lag_pairs: set[tuple[int, int]]) -> tuple[int, int]:
    companion = sum(1 for pair in itertools.combinations(numbers, 2) if pair_key(pair[0], pair[1]) in companion_pairs)
    lag = 0
    number_set = set(numbers)
    for trigger, candidate in lag_pairs:
        if trigger in number_set and candidate in number_set:
            lag += 1
    return companion, lag


def target_signature_counts(signature_value: str | None) -> dict[str, int]:
    values = [int(value) for value in str(signature_value or "1-1-1-0-1").split("-") if value.isdigit()]
    counts: dict[str, int] = {}
    for index, block in enumerate(BLOCK_ORDER):
        counts[block] = 1 if index < len(values) and values[index] > 0 else 0
    return counts


def immediate_overlap_label(overlap: int) -> tuple[str, str, list[str]]:
    if overlap == 0:
        return "sin repetidos inmediatos", "No se usaron repetidos inmediatos porque el pool mantuvo señales suficientes.", []
    if overlap == 1:
        return "1 repetido inmediato dentro de rango histórico normal", "Se permitió 1 repetido inmediato por soporte de señales activas.", []
    if overlap == 2:
        return "2 repetidos inmediatos permitidos por soporte de señales activas", "Se permitieron 2 repetidos inmediatos por soporte de perfil reciente o relación interna.", []
    return f"{overlap} repetidos inmediatos: revisar riesgo estructural", "Se conservaron repetidos altos solo porque mantienen señales activas.", ["Revisar repetidos inmediatos altos por posible concentración estructural."]


def composition_for_ticket(
    numbers: list[int],
    latest_numbers: list[int],
    inputs: dict[str, dict[str, Any]],
    companion_pairs: set[tuple[int, int]],
    lag_pairs: set[tuple[int, int]],
) -> dict[str, Any]:
    total = sum(numbers)
    band = sum_band(total)
    parity = parity_label(numbers)
    presence = presence_signature(numbers)
    block_sig = block_signature(numbers)
    overlap = len(set(numbers) & set(latest_numbers))
    label, reason, overlap_risks = immediate_overlap_label(overlap)
    companion_count, lag_count = ticket_pair_counts(numbers, companion_pairs, lag_pairs)
    winner = inputs["winner"]
    recent = inputs["recent"]
    winner_presence = winner.get("presence_signature_profile", {}).get("presence_signature_distribution", {})
    recent_presence = recent.get("presence_signature_profile", {}).get("presence_signature_distribution", {})
    winner_bands = winner.get("sum_profile", {}).get("sum_band_distribution", {})
    recent_bands = recent.get("sum_profile", {}).get("sum_band_distribution", {})
    return {
        "parity": parity,
        "sum": total,
        "sum_band": band,
        "sum_band_es": SUM_BAND_ES.get(band, band),
        "block_signature": block_sig,
        "block_presence_signature": presence,
        "visual_structure_label_es": visual_structure_label_es(presence),
        "blocks": block_counts(numbers),
        "immediate_overlap_previous_draw": overlap,
        "immediate_overlap_label_es": label,
        "immediate_overlap_reason_es": reason,
        "pair_companion_count": companion_count,
        "pair_lag_relation_count": lag_count,
        "matches_winner_profile": bool(winner_presence.get(presence) or winner_bands.get(band)),
        "matches_recent_profile": bool(recent_presence.get(presence) or recent_bands.get(band)),
        "overlap_risk_notes_es": overlap_risks,
    }


def pick_ticket(
    ticket_type: str,
    ordered_candidates: list[int],
    signals: dict[int, set[str]],
    weights: dict[int, float],
    latest_numbers: list[int],
    inputs: dict[str, dict[str, Any]],
    companion_pairs: set[tuple[int, int]],
    lag_pairs: set[tuple[int, int]],
    previous_tickets: list[list[int]],
    offset: int,
) -> list[int]:
    chosen: list[int] = []
    candidates = ordered_candidates[offset:] + ordered_candidates[:offset]
    if ticket_type == "pair_sum_structure":
        for a, b in companion_pairs:
            if a in candidates and b in candidates:
                chosen.extend([a, b])
                break
        for trigger, candidate in lag_pairs:
            if trigger in candidates and candidate in candidates:
                chosen.extend([trigger, candidate])
                break
    elif ticket_type == "pair_companion_bridge":
        for a, b in list(companion_pairs)[:3]:
            chosen.extend([a, b])
    elif ticket_type == "block_completion_main":
        for row in inputs["block_completion"].get("groups", [])[:5]:
            chosen.extend(int(number) for number in row.get("missing", []))
            chosen.extend(int(number) for number in row.get("recent_seen", [])[:2])
    elif ticket_type == "recent_signature_fit":
        target = target_signature_counts(inputs["recent"].get("presence_signature_profile", {}).get("dominant_presence_signature"))
        for number in candidates:
            block = next(block for block in BLOCK_ORDER if number in range_from_block(block))
            if target.get(block):
                chosen.append(number)
    elif ticket_type == "controlled_contrarian":
        chosen.extend(list(reversed(candidates[-18:])))

    selected: list[int] = []
    for number in chosen + candidates:
        if number not in signals or not signals[number] or number in selected:
            continue
        if len(selected) >= DRAW_SIZE:
            break
        selected.append(number)
    if len(selected) < DRAW_SIZE:
        raise RuntimeError("pool insuficiente para formar boleto con señales activas")
    return sorted(selected[:DRAW_SIZE])


def build_ticket(
    ticket_id: str,
    ticket_type: str,
    numbers: list[int],
    signals: dict[int, set[str]],
    latest_numbers: list[int],
    inputs: dict[str, dict[str, Any]],
    companion_pairs: set[tuple[int, int]],
    lag_pairs: set[tuple[int, int]],
    relaxation_notes: list[str],
) -> dict[str, Any]:
    composition = composition_for_ticket(numbers, latest_numbers, inputs, companion_pairs, lag_pairs)
    signal_map = {str(number): sorted(signals[number]) for number in numbers}
    trace = [
        "Se inició con números que tienen al menos una señal activa real.",
        "Se revisó relación interna de pares pair_lag y pair_companion.",
        "Se ajustó suma, paridad y firma visual contra perfiles histórico y reciente.",
        "Se midieron repetidos inmediatos sin prohibirlos automáticamente.",
        "Se mantuvo diversidad frente a los otros boletos del conjunto.",
        *relaxation_notes,
        "Se mantuvo estado review_default.",
    ]
    risks = [
        "Revisar que la estructura no dependa de una sola familia de señales.",
        "Usar como formación de revisión, no como promesa de resultado.",
        *composition.pop("overlap_risk_notes_es", []),
    ]
    if composition["sum_band"] in {"extreme_high", "low_tail"}:
        risks.append("La banda de suma queda en una cola histórica y requiere revisión contextual.")
    if composition["pair_companion_count"] == 0 and composition["pair_lag_relation_count"] == 0:
        risks.append("La relación interna de pares es débil en este boleto.")
    reason = "Boleto construido desde señales activas, relación de pares, suma objetivo y formación de estructura."
    thesis = (
        f"Composición {ticket_type} con firma {composition['block_signature']}, "
        f"presencia {composition['block_presence_signature']} y banda {composition['sum_band_es']}."
    )
    return {
        "ticket_id": ticket_id,
        "ticket_type": ticket_type,
        "numbers": numbers,
        "signals": signal_map,
        "composition": composition,
        "construction_trace_es": trace,
        "reason_es": reason,
        "thesis_es": thesis,
        "risk_notes_es": risks,
        "production_status": PRODUCTION_STATUS,
    }


def build_constructor_output(paths: dict[str, str]) -> dict[str, Any]:
    inputs = {
        "winner": load_json(paths["winner"]),
        "gap": load_json(paths["gap"]),
        "pair_lag": load_json(paths["pair_lag"]),
        "block_completion": load_json(paths["block_completion"]),
        "signature": load_json(paths["signature"]),
        "recent": load_json(paths["recent"]),
    }
    latest_numbers = latest_numbers_from_history()
    signals, weights, companion_pairs, lag_pairs = build_signal_pool(inputs)
    pool = [number for number in range(1, MAX_NUMBER + 1) if signals.get(number)]
    if len(pool) < 18:
        raise SystemExit(f"Pool insuficiente: {len(pool)} números con señales activas.")
    ordered = sorted(pool, key=lambda number: (-candidate_score(number, signals, weights), number))

    tickets: list[dict[str, Any]] = []
    raw_numbers: list[list[int]] = []
    relaxation_summary: list[str] = []
    attempts = 0
    for ticket_type in TICKET_TYPES:
        found: list[int] | None = None
        local_notes: list[str] = []
        for offset in range(0, min(len(ordered), 35)):
            attempts += 1
            candidate = pick_ticket(ticket_type, ordered, signals, weights, latest_numbers, inputs, companion_pairs, lag_pairs, raw_numbers, offset)
            if any(set(candidate) == set(existing) for existing in raw_numbers):
                continue
            overlaps = [len(set(candidate) & set(existing)) for existing in raw_numbers]
            if overlaps and max(overlaps) > 3:
                local_notes = ["Se usó offset alterno para mantener máximo 3 números compartidos entre boletos."]
                continue
            found = candidate
            break
        if found is None:
            for offset in range(35, min(len(ordered), 55)):
                candidate = pick_ticket(ticket_type, ordered, signals, weights, latest_numbers, inputs, companion_pairs, lag_pairs, raw_numbers, offset)
                if not any(set(candidate) == set(existing) for existing in raw_numbers):
                    found = candidate
                    local_notes = ["Se relajó diversidad de tesis para completar 5 boletos con señales activas."]
                    relaxation_summary.extend(local_notes)
                    break
        if found is None:
            raise SystemExit("No se pudieron construir 5 boletos sin inventar señales.")
        raw_numbers.append(found)
        tickets.append(build_ticket(f"constructor_{len(tickets) + 1}", ticket_type, found, signals, latest_numbers, inputs, companion_pairs, lag_pairs, local_notes))

    immediate_distribution = Counter(str(ticket["composition"]["immediate_overlap_previous_draw"]) for ticket in tickets)
    presence_distribution = Counter(ticket["composition"]["block_presence_signature"] for ticket in tickets)
    pair_usage = sum(ticket["composition"]["pair_companion_count"] for ticket in tickets)
    lag_usage = sum(ticket["composition"]["pair_lag_relation_count"] for ticket in tickets)
    structure_usage = sum(1 for ticket in tickets if "block_completion" in set(signal for values in ticket["signals"].values() for signal in values))
    recent = inputs["recent"]
    winner = inputs["winner"]
    source_files = paths | {"history_matrix": "v4_history_matrix.json", "csv": "revancha.csv"}
    source_sha256 = {}
    for key, path in source_files.items():
        if Path(path).exists():
            source_sha256[key] = file_sha256(path)
    return {
        "generated_at": utc_now(),
        "engine_version": ENGINE_VERSION,
        "production_status": PRODUCTION_STATUS,
        "latest_draw": recent["latest_draw"],
        "target_draw": int(recent["latest_draw"]) + 1,
        "source_files": source_files,
        "source_sha256": source_sha256,
        "recent_composition_profile_used": {
            "window": recent["window"],
            "dominant_sum_band": recent["sum_profile"]["dominant_sum_band"],
            "dominant_parity": recent["parity_profile"]["dominant_parity"],
            "dominant_presence_signature": recent["presence_signature_profile"]["dominant_presence_signature"],
            "dominant_immediate_overlap": recent["immediate_overlap_profile"]["dominant_immediate_overlap"],
        },
        "slate_structure_summary": {
            "recent_alignment_summary_es": "El conjunto fue formado usando relación de pares, suma objetivo y cierre de estructura observados en las últimas 30 combinaciones.",
            "pair_companion_usage_count": pair_usage,
            "pair_lag_usage_count": lag_usage,
            "structure_completion_usage_count": structure_usage,
            "immediate_overlap_distribution": dict(immediate_distribution),
            "block_presence_distribution": dict(presence_distribution),
            "diversity_summary_es": "Los boletos se formaron con tesis distintas y control de máximo 3 números compartidos cuando el pool lo permitió.",
            "relaxation_summary_es": " ".join(relaxation_summary) if relaxation_summary else "No se requirió relajación fuerte de restricciones.",
            "winner_profile_reference_es": f"Perfil histórico dominante: {winner['sum_profile']['dominant_sum_band']} y {winner['parity_profile']['dominant_parity']}.",
        },
        "tickets": tickets,
        "slate": tickets,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build V4.4 final combination slate.")
    parser.add_argument("--winner", default="v4_winner_profile.json")
    parser.add_argument("--gap", default="v4_gap_echo_output.json")
    parser.add_argument("--pair-lag", default="v4_pair_lag_signals.json")
    parser.add_argument("--block-completion", default="v4_block_completion_signals.json")
    parser.add_argument("--signature", default="v4_signature_history.json")
    parser.add_argument("--recent", default="v4_recent_composition_profile.json")
    parser.add_argument("--output", default="v4_combination_slate.json")
    args = parser.parse_args()
    report = build_constructor_output(
        {
            "winner": args.winner,
            "gap": args.gap,
            "pair_lag": args.pair_lag,
            "block_completion": args.block_completion,
            "signature": args.signature,
            "recent": args.recent,
        }
    )
    write_json(args.output, report)
    print(f"Wrote {args.output}; tickets={len(report['tickets'])} target_draw={report['target_draw']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
