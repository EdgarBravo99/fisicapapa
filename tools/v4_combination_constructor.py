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


def signal_count(numbers: list[int], signals: dict[int, set[str]], signal: str) -> int:
    return sum(1 for number in numbers if signal in signals.get(number, set()))


def profile_targets(inputs: dict[str, dict[str, Any]]) -> set[str]:
    recent = inputs["recent"]
    winner = inputs["winner"]
    return {
        str(recent.get("sum_profile", {}).get("dominant_sum_band")),
        str(winner.get("sum_profile", {}).get("dominant_sum_band")),
        str(recent.get("presence_signature_profile", {}).get("dominant_presence_signature")),
        str(recent.get("presence_signature_profile", {}).get("second_presence_signature")),
        str(winner.get("presence_signature_profile", {}).get("dominant_presence_signature")),
    }


def summarize_recent_windows(recent: dict[str, Any]) -> dict[str, Any]:
    windows = recent.get("windows")
    if not isinstance(windows, dict):
        return {
            "source": "legacy_window_30_only",
            "30": {
                "dominant_sum_band": recent.get("sum_profile", {}).get("dominant_sum_band", ""),
                "dominant_parity": recent.get("parity_profile", {}).get("dominant_parity", ""),
                "dominant_presence_signature": recent.get("presence_signature_profile", {}).get("dominant_presence_signature", ""),
                "dominant_immediate_overlap": recent.get("immediate_overlap_profile", {}).get("dominant_immediate_overlap", 0),
            },
        }
    summary: dict[str, Any] = {}
    for key in ("5", "20", "30"):
        window = windows.get(key, {})
        summary[key] = {
            "dominant_sum_band": window.get("sum_profile", {}).get("dominant_sum_band", ""),
            "dominant_parity": window.get("parity_profile", {}).get("dominant_parity", ""),
            "dominant_presence_signature": window.get("presence_signature_profile", {}).get("dominant_presence_signature", ""),
            "dominant_immediate_overlap": window.get("immediate_overlap_profile", {}).get("dominant_immediate_overlap", 0),
        }
    return summary


def recent_micro_shift_note(recent: dict[str, Any]) -> str | None:
    regime = recent.get("recent_regime_summary") or {}
    if regime.get("window_5_vs_20_shift") or regime.get("window_20_vs_30_shift"):
        return "Se detectó cambio micro en últimos 5 sorteos respecto a ventanas 20 y 30. Se conserva revisión contra ventanas mayores."
    return None


def evaluate_candidate_ticket(
    numbers: list[int],
    ticket_type: str,
    latest_numbers: list[int],
    inputs: dict[str, dict[str, Any]],
    signals: dict[int, set[str]],
    companion_pairs: set[tuple[int, int]],
    lag_pairs: set[tuple[int, int]],
    previous_tickets: list[list[int]],
    weights: dict[int, float] | None = None,
) -> dict[str, Any]:
    reasons_es: list[str] = []
    risks_es: list[str] = []
    relaxations_es: list[str] = []
    clean_numbers = [int(number) for number in numbers if isinstance(number, int) or str(number).isdigit()]
    if len(clean_numbers) != DRAW_SIZE:
        return {"accepted": False, "score": -1000.0, "reasons_es": ["El candidato no tiene exactamente 6 números."], "risk_notes_es": risks_es, "relaxation_notes_es": relaxations_es, "composition": {}}
    if len(set(clean_numbers)) != DRAW_SIZE:
        return {"accepted": False, "score": -1000.0, "reasons_es": ["El candidato contiene números repetidos internos."], "risk_notes_es": risks_es, "relaxation_notes_es": relaxations_es, "composition": {}}
    if any(number < 1 or number > MAX_NUMBER for number in clean_numbers):
        return {"accepted": False, "score": -1000.0, "reasons_es": ["El candidato contiene números fuera de rango 1-56."], "risk_notes_es": risks_es, "relaxation_notes_es": relaxations_es, "composition": {}}
    missing_signals = [number for number in clean_numbers if not signals.get(number)]
    if missing_signals:
        return {"accepted": False, "score": -1000.0, "reasons_es": [f"Números sin señales activas: {missing_signals}."], "risk_notes_es": risks_es, "relaxation_notes_es": relaxations_es, "composition": {}}

    numbers_sorted = sorted(clean_numbers)
    composition = composition_for_ticket(numbers_sorted, latest_numbers, inputs, companion_pairs, lag_pairs)
    overlaps = [len(set(numbers_sorted) & set(ticket)) for ticket in previous_tickets]
    max_overlap = max(overlaps) if overlaps else 0
    composition["overlap_with_previous_tickets"] = overlaps
    composition["diversity_ok"] = max_overlap <= 3

    structure_count = signal_count(numbers_sorted, signals, "structure_completion")
    block_count = signal_count(numbers_sorted, signals, "block_completion")
    pair_companion_count = int(composition["pair_companion_count"])
    pair_lag_relation_count = int(composition["pair_lag_relation_count"])
    profile_match = bool(composition["matches_recent_profile"] or composition["matches_winner_profile"])
    internal_pair_support = pair_companion_count > 0 or pair_lag_relation_count > 0
    structural_support = structure_count >= 3 or block_count >= 2
    immediate_overlap = int(composition["immediate_overlap_previous_draw"])
    accepted = True

    if not composition["diversity_ok"]:
        accepted = False
        risks_es.append(f"Comparte {max_overlap} números con un boleto previo.")
    if not profile_match:
        accepted = False
        risks_es.append("No coincide con perfil reciente ni perfil ganador histórico.")
    if ticket_type == "pair_companion_bridge" and pair_companion_count <= 0:
        accepted = False
        risks_es.append("La tesis pair_companion_bridge requiere al menos una relacion pair_companion interna.")
    if ticket_type == "block_completion_main" and not structural_support:
        accepted = False
        risks_es.append("La tesis block_completion_main requiere cierre estructural real antes de aceptarse.")
    if ticket_type == "controlled_contrarian":
        if structure_count < 4:
            accepted = False
            risks_es.append("La tesis contraria no alcanza 4 números con cierre estructural.")
        if not internal_pair_support:
            reasons_es.append("No se usaron pares internos; se aceptó como tesis contraria por cierre estructural y coincidencia de perfil.")
            risks_es.append("Tesis contraria con relación interna de pares débil.")
    elif not (internal_pair_support or structural_support):
        accepted = False
        risks_es.append("No tiene relación interna de pares ni cierre estructural suficiente.")

    if pair_companion_count > 0:
        reasons_es.append("Se añadió relación pair_companion observada en las últimas 30 combinaciones.")
    if pair_lag_relation_count > 0:
        reasons_es.append("Se añadió relación pair_lag trigger → candidato desde ventana histórica.")
    if structural_support:
        reasons_es.append("Se aceptó por cierre estructural con señales block_completion o structure_completion.")
    if immediate_overlap <= 1:
        reasons_es.append(f"Repetidos inmediatos controlados: {composition['immediate_overlap_label_es']}.")
    elif immediate_overlap == 2:
        if internal_pair_support and profile_match:
            reasons_es.append("Se permitieron 2 repetidos inmediatos porque ambos tenían señales activas y la estructura seguía alineada.")
        else:
            accepted = False
            risks_es.append("2 repetidos inmediatos sin relación interna o perfil suficiente.")
    elif ticket_type == "controlled_contrarian":
        risks_es.append(f"{immediate_overlap} repetidos inmediatos: riesgo fuerte aceptado solo como tesis contraria estructural.")
        relaxations_es.append("Se permitió repetición inmediata alta por tesis contraria estructural con señales activas.")
    else:
        accepted = False
        risks_es.append(f"{immediate_overlap} repetidos inmediatos rechazados fuera de tesis contraria.")

    targets = profile_targets(inputs)
    if str(composition["sum_band"]) not in targets:
        relaxations_es.append("Se permitió banda de suma adyacente para preservar señales activas y diversidad.")
    if str(composition["block_presence_signature"]) not in targets:
        relaxations_es.append("Se permitió firma de presencia alternativa para mantener diversidad entre boletos.")

    score = sum((weights or {}).get(number, 0.0) for number in numbers_sorted)
    score += pair_companion_count * 1.35
    score += pair_lag_relation_count * 0.85
    score += structure_count * 0.45
    score += block_count * 0.35
    score += 1.1 if composition["matches_recent_profile"] else 0.0
    score += 0.7 if composition["matches_winner_profile"] else 0.0
    score -= max_overlap * 0.8
    score -= max(immediate_overlap - 1, 0) * 0.55
    return {
        "accepted": accepted,
        "score": round(score, 6),
        "reasons_es": reasons_es or ["Candidato evaluado contra restricciones reales de composición."],
        "risk_notes_es": risks_es,
        "relaxation_notes_es": relaxations_es,
        "composition": composition,
    }


def complete_seed(seed: list[int], fill_candidates: list[int], signals: dict[int, set[str]]) -> list[int] | None:
    selected: list[int] = []
    for number in seed + fill_candidates:
        if number in selected or not signals.get(number):
            continue
        selected.append(number)
        if len(selected) == DRAW_SIZE:
            return sorted(selected)
    return None


def generate_candidate_numbers(
    ticket_type: str,
    ordered_candidates: list[int],
    signals: dict[int, set[str]],
    inputs: dict[str, dict[str, Any]],
    companion_pairs: set[tuple[int, int]],
    lag_pairs: set[tuple[int, int]],
    previous_tickets: list[list[int]],
) -> list[list[int]]:
    generated: list[list[int]] = []
    seen: set[tuple[int, ...]] = set()

    def add(seed: list[int], fill: list[int]) -> None:
        ticket = complete_seed(seed, fill, signals)
        if ticket is None:
            return
        key = tuple(ticket)
        if key not in seen:
            seen.add(key)
            generated.append(ticket)

    candidates = list(ordered_candidates)
    companion_list = [list(pair) for pair in companion_pairs if all(number in signals for number in pair)]
    lag_list = [[trigger, candidate] for trigger, candidate in lag_pairs if trigger in signals and candidate in signals]
    block_groups = inputs["block_completion"].get("groups", [])
    signature_numbers = [int(number) for number in inputs["signature"].get("numbers_after", {}).keys() if int(number) in signals]
    recent_numbers = [int(row["number"]) for row in inputs["recent"].get("top_recent_numbers", []) if int(row["number"]) in signals]
    diversity_fill = [number for number in candidates if all(number not in ticket for ticket in previous_tickets)]

    if ticket_type == "pair_sum_structure":
        for pair in companion_list[:18]:
            for lag in lag_list[:18]:
                add(pair + lag, signature_numbers + recent_numbers + candidates)
        for pair in companion_list[:30]:
            add(pair, signature_numbers + candidates)
    elif ticket_type == "pair_companion_bridge":
        for first, second in itertools.combinations(companion_list[:18], 2):
            add(first + second, recent_numbers + candidates)
        for pair in companion_list[:30]:
            add(pair, recent_numbers + signature_numbers + candidates)
    elif ticket_type == "block_completion_main":
        for row in block_groups[:45]:
            seed = [int(number) for number in row.get("missing", []) + row.get("recent_seen", [])[:3]]
            add(seed, signature_numbers + recent_numbers + candidates)
    elif ticket_type == "recent_signature_fit":
        target = target_signature_counts(inputs["recent"].get("presence_signature_profile", {}).get("dominant_presence_signature"))
        primary = [
            number for number in candidates
            if target.get(next(block for block in BLOCK_ORDER if number in range_from_block(block)))
        ]
        for offset in range(0, min(len(primary), 28), 2):
            add(primary[offset: offset + 4], signature_numbers + recent_numbers + candidates)
    elif ticket_type == "controlled_contrarian":
        structural = [
            number for number in reversed(candidates)
            if "structure_completion" in signals.get(number, set()) or "block_completion" in signals.get(number, set())
        ]
        for offset in range(0, min(len(structural), 34), 2):
            add(structural[offset: offset + 5], diversity_fill + signature_numbers + candidates)

    thematic_pools = [candidates, signature_numbers + candidates, recent_numbers + candidates, diversity_fill + candidates]
    for pool in thematic_pools:
        for offset in range(0, min(len(pool), 28), 3):
            add(pool[offset: offset + 3], pool[offset + 3:] + candidates)
    return generated[:800]


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
    evaluation: dict[str, Any],
) -> dict[str, Any]:
    composition = dict(evaluation["composition"])
    signal_map = {str(number): sorted(signals[number]) for number in numbers}
    trace = [*evaluation.get("reasons_es", []), *evaluation.get("relaxation_notes_es", [])]
    trace.append("Se mantuvo estado review_default.")
    risks = [
        "Revisar que la estructura no dependa de una sola familia de señales.",
        "Usar como formación de revisión, no como promesa de resultado.",
        *composition.pop("overlap_risk_notes_es", []),
        *evaluation.get("risk_notes_es", []),
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
        "constructor_acceptance_score": evaluation.get("score", 0.0),
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
    for ticket_type in TICKET_TYPES:
        candidates = generate_candidate_numbers(ticket_type, ordered, signals, inputs, companion_pairs, lag_pairs, raw_numbers)
        evaluated: list[tuple[float, list[int], dict[str, Any]]] = []
        two_overlap_count = sum(1 for ticket in tickets if int(ticket["composition"].get("immediate_overlap_previous_draw", 0)) == 2)
        for candidate in candidates:
            evaluation = evaluate_candidate_ticket(
                candidate,
                ticket_type,
                latest_numbers,
                inputs,
                signals,
                companion_pairs,
                lag_pairs,
                raw_numbers,
                weights,
            )
            if not evaluation["accepted"]:
                continue
            if two_overlap_count >= 2 and int(evaluation["composition"].get("immediate_overlap_previous_draw", 0)) == 2:
                continue
            evaluated.append((float(evaluation["score"]), candidate, evaluation))
        if not evaluated:
            raise SystemExit("No se pudieron construir 5 boletos sin inventar señales ni violar restricciones reales.")
        evaluated.sort(key=lambda item: (-item[0], item[1]))
        _, found_candidate, accepted_evaluation = evaluated[0]
        if accepted_evaluation.get("relaxation_notes_es"):
            relaxation_summary.extend(accepted_evaluation["relaxation_notes_es"])
        raw_numbers.append(found_candidate)
        ticket = build_ticket(f"constructor_{len(tickets) + 1}", ticket_type, found_candidate, signals, accepted_evaluation)
        micro_note = recent_micro_shift_note(inputs["recent"])
        if micro_note and micro_note not in ticket["construction_trace_es"]:
            ticket["construction_trace_es"].insert(-1, micro_note)
        tickets.append(ticket)

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
        "recent_windows_used": summarize_recent_windows(recent),
        "recent_regime_summary": recent.get("recent_regime_summary", {}),
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
