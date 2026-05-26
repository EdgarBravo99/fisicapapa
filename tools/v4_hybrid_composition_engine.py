# -*- coding: utf-8 -*-
"""V4.3 Hybrid Composition Engine: role-based Revancha ticket slate."""

from __future__ import annotations

import argparse
import itertools
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
VISUAL_STRUCTURE_CONTRACT_VERSION = "v4.3-structure-signature-v1"
TICKET_TYPES = [
    "composition_main",
    "activated_block_main",
    "pair_lag_bridge",
    "pair_lag_support",
    "visual_support",
    "balanced_hybrid",
    "contrarian_controlled",
    "cold_companion_high_edge",
]

SUM_BAND_ORDER = ("low_tail", "historical_core", "upper_core", "high_tail", "extreme_high")
BLOCK_ORDER = ["1_10", "11_20", "21_30", "31_40", "41_56"]
SUM_BAND_ES = {
    "low_tail": "cola baja",
    "historical_core": "nucleo historico",
    "upper_core": "nucleo alto",
    "high_tail": "cola alta",
    "extreme_high": "extremo alto",
}
VISUAL_STRUCTURE_LABELS_ES = {
    "0-0-1-0-1": "Activacion media-alta: presencia en 21_30 y 41_56",
    "0-1-1-0-1": "Puente 11_20 + 21_30 + 41_56",
    "0-1-0-0-1": "Puente bajo-medio con bloque alto",
    "1-0-1-0-1": "Triangulo 1_10 + 21_30 + 41_56",
    "1-1-1-0-0": "Escalera baja-media hasta 21_30",
    "0-1-1-1-0": "Centro extendido 11_20 + 21_30 + 31_40",
}
ROLE_REASON_ES = {
    "anchor": "Ancla la lectura del boleto dentro de la composicion.",
    "support": "Aporta soporte dentro del balance armonico del boleto.",
    "activated_block": "Ubicado dentro de un bloque activo por activacion unica reciente.",
    "block_completion": "Completa una tesis de bloque sin modificar el motor base.",
    "bridge_pair_lag": "Tiene evidencia pair-lag validada como puente temporal.",
    "pair_lag_support": "Tiene evidencia pair-lag usada solo como soporte.",
    "gap_echo": "Presenta eco de gap compatible con su historial reciente.",
    "cold_companion": "Companion frio controlado conectado a evidencia local.",
    "v42_signal_optional": "Aporta senal V4.2 opcional como apoyo, no como fuente principal.",
    "co_travel_companion": "Aparece dentro de pares companion con soporte de co-travel.",
    "block_bridge_pair": "Participa en un par puente entre bloques complementarios.",
    "harmonic_cluster": "Forma parte de un cluster armonico recurrente.",
    "anti_pair_risk": "Incluye una marca de riesgo anti-par para revision.",
    "sum_band_guardrail": "Queda bajo guardia de banda de suma.",
    "harmonic_support": "Refuerza la coherencia armonica interna del boleto.",
}


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


def _percentile(values: list[int], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = (len(ordered) - 1) * percentile
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    weight = index - lower
    return round(ordered[lower] * (1 - weight) + ordered[upper] * weight, 6)


def _sum_policy(draws: list[dict[str, Any]]) -> dict[str, Any]:
    sums = [sum(draw["numbers"]) for draw in draws if isinstance(draw.get("numbers"), list)]
    return {
        "p10": _percentile(sums, 0.10),
        "p60": _percentile(sums, 0.60),
        "p80": _percentile(sums, 0.80),
        "p95": _percentile(sums, 0.95),
    }


def _sum_band(total: int, policy: dict[str, Any]) -> str:
    p10 = float(policy.get("p10", 0.0) or 0.0)
    p60 = float(policy.get("p60", 0.0) or 0.0)
    p80 = float(policy.get("p80", 0.0) or 0.0)
    p95 = float(policy.get("p95", 0.0) or 0.0)
    if total < p10:
        return "low_tail"
    if total < p60:
        return "historical_core"
    if total < p80:
        return "upper_core"
    if total < p95:
        return "high_tail"
    return "extreme_high"


def _sum_band_es(band: str | None) -> str:
    return SUM_BAND_ES.get(str(band or ""), str(band or "desconocida"))


def _block_vector(block_profile: dict[str, int]) -> list[int]:
    return [int(block_profile.get(block, 0) or 0) for block in BLOCK_ORDER]


def _signature(values: list[int]) -> str:
    return "-".join(str(int(value)) for value in values)


def _presence_vector(block_profile: dict[str, int]) -> list[int]:
    return [1 if int(block_profile.get(block, 0) or 0) > 0 else 0 for block in BLOCK_ORDER]


def _visual_structure_label_es(presence_signature: str) -> str:
    return VISUAL_STRUCTURE_LABELS_ES.get(presence_signature, f"Presencia visual {presence_signature}")


def _immediate_overlap_label_es(overlap: int) -> str:
    if overlap <= 0:
        return "sin repetidos inmediatos"
    if overlap == 1:
        return "1 repetido inmediato controlado"
    return f"{overlap} repetidos inmediatos: revisar riesgo"


def _parity_signature(parity: dict[str, int]) -> str:
    even = int(parity.get("even", 0) or 0)
    odd = int(parity.get("odd", 0) or 0)
    return f"{even} pares / {odd} impares"


def _structure_fields(numbers: list[int], previous_numbers: set[int] | None = None) -> dict[str, Any]:
    block_profile = block_counts(numbers)
    vector = _block_vector(block_profile)
    presence = _presence_vector(block_profile)
    block_signature = _signature(vector)
    presence_signature = _signature(presence)
    overlap = len(set(numbers) & (previous_numbers or set()))
    return {
        "block_order": BLOCK_ORDER,
        "block_vector": vector,
        "block_signature": block_signature,
        "block_presence_vector": presence,
        "block_presence_signature": presence_signature,
        "visual_structure_label_es": _visual_structure_label_es(presence_signature),
        "immediate_overlap_label_es": _immediate_overlap_label_es(overlap),
    }


def _harmonic_notes_es(
    strong_pairs: list[dict[str, Any]],
    block_bridges: list[dict[str, Any]],
    clusters: list[dict[str, Any]],
    band: str,
    anti_pairs: list[dict[str, Any]],
) -> list[str]:
    notes: list[str] = []
    if strong_pairs:
        notes.append(f"{len(strong_pairs)} par companion apoya la coherencia interna.")
    if block_bridges:
        notes.append(f"{len(block_bridges)} pares puente conectan bloques complementarios.")
    if clusters:
        notes.append(f"{len(clusters)} clusters companion recurrentes estan presentes.")
    if band in {"high_tail", "extreme_high", "low_tail"}:
        notes.append(f"Guardia de banda de suma: {_sum_band_es(band)} ({band}).")
    if anti_pairs:
        notes.append(f"{len(anti_pairs)} marcador de riesgo anti-par.")
    return notes


def _reason_es_from_roles(number: int, roles: list[str], row: dict[str, Any]) -> list[str]:
    block = _block_name(number)
    reasons: list[str] = []
    for role in roles:
        if role == "activated_block":
            reasons.append(f"Ubicado dentro del bloque activo {block} por activacion unica reciente.")
        elif role == "sum_band_guardrail":
            continue
        elif role in ROLE_REASON_ES:
            reasons.append(ROLE_REASON_ES[role])
    signals = row.get("signals") if isinstance(row.get("signals"), dict) else {}
    if "gap_echo" in roles and signals.get("gap_echo") is not None:
        reasons.append(f"Eco de gap con soporte diagnostico {round(float(signals.get('gap_echo') or 0.0), 3)}.")
    if not reasons:
        reasons.append("Seleccionado por balance de roles V4.3 y coherencia del boleto.")
    return _unique_text(reasons)[:5]


def _ticket_spanish_contract(
    ticket_type: str,
    numbers: list[int],
    composition: dict[str, Any],
    roles: dict[str, list[str]],
    reasons_es: dict[str, list[str]],
    reason_es: str,
    risk_notes_es: list[str],
) -> dict[str, Any]:
    harmonic = composition.get("harmonic_coherence", {})
    block_presence_signature = composition.get("block_presence_signature", "no disponible")
    block_signature = composition.get("block_signature", "no disponible")
    visual_label = composition.get("visual_structure_label_es", f"Presencia visual {block_presence_signature}")
    sum_band = composition.get("sum_band", "desconocida")
    sum_band_es = composition.get("sum_band_es", _sum_band_es(sum_band))
    overlap_label = composition.get("immediate_overlap_label_es", "sin repetidos inmediatos")
    active_blocks = [block for block, value in composition.get("blocks", {}).items() if value]
    role_set = {role for role_list in roles.values() for role in role_list}
    strengths: list[str] = [
        f"Estructura visual {block_presence_signature}: {visual_label}.",
        f"Firma de bloques {block_signature} con presencia en {', '.join(active_blocks) if active_blocks else 'sin bloque dominante'}.",
        f"Banda de suma: {sum_band_es} ({sum_band}).",
    ]
    if "bridge_pair_lag" in role_set or "pair_lag_support" in role_set:
        strengths.append("Incluye soporte pair-lag como evidencia de revision, no como prior aplicado.")
    if "co_travel_companion" in role_set:
        strengths.append("Incluye soporte co-travel companion dentro del boleto.")
    if "gap_echo" in role_set:
        strengths.append("Incluye eco de gap en numeros seleccionados.")
    if "cold_companion" in role_set:
        strengths.append("Incluye companion frio controlado con evidencia local.")
    if harmonic.get("block_bridge_pair_count"):
        strengths.append(f"{harmonic.get('block_bridge_pair_count')} pares puente sostienen bloques complementarios.")
    if harmonic.get("cluster_support_count"):
        strengths.append(f"{harmonic.get('cluster_support_count')} clusters armonicos aparecen en el boleto.")

    why = [
        reason_es,
        f"Combina roles visibles con {visual_label}.",
        f"Mantiene disciplina de suma en {sum_band_es} y {overlap_label}.",
    ]
    headline = f"{ticket_type.replace('_', ' ')} con {visual_label}"
    decision_summary = (
        f"Boleto {ticket_type.replace('_', ' ')} con presencia visual {block_presence_signature}, "
        f"suma {sum_band} y soporte armonico en bloques {', '.join(active_blocks) if active_blocks else 'sin bloque dominante'}."
    )
    structure_summary = (
        f"Firma de bloques {block_signature}; presencia visual {block_presence_signature}; "
        f"{visual_label}; {overlap_label}."
    )
    thesis_es = (
        f"Revisar una composicion de {visual_label.lower()} con soporte de roles V4.3, "
        f"sin promesa de resultado."
    )
    return {
        "reason_es": reason_es,
        "risk_notes_es": risk_notes_es,
        "thesis_es": thesis_es,
        "decision_summary_es": decision_summary,
        "structure_summary_es": structure_summary,
        "explanation_es": {
            "headline": headline,
            "why_this_ticket": _unique_text(why),
            "strengths": _unique_text(strengths),
            "risks": risk_notes_es,
            "review_focus": f"Revisar si la estructura {block_presence_signature} y la banda {sum_band_es} siguen aportando coherencia historica.",
        },
        "reasons_es": reasons_es,
    }



def _pair_key(pair: tuple[int, int] | list[int]) -> str:
    a, b = sorted((int(pair[0]), int(pair[1])))
    return f"{a:02d}-{b:02d}"


def _pair_lookup(pair_audit: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    if not isinstance(pair_audit, dict):
        return lookup
    for section in ("top_co_travel_pairs", "top_block_bridge_pairs", "anti_pairs"):
        rows = pair_audit.get(section)
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            pair = row.get("pair")
            if isinstance(pair, list) and len(pair) == 2:
                lookup[_pair_key(pair)] = row
    return lookup


def _cluster_hits(numbers: list[int], pair_audit: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(pair_audit, dict):
        return []
    number_set = set(numbers)
    clusters = pair_audit.get("cluster_companions")
    if not isinstance(clusters, list):
        return []
    hits = []
    for cluster in clusters:
        members = set(cluster.get("numbers") or []) if isinstance(cluster, dict) else set()
        if len(members & number_set) >= 3:
            hits.append(cluster)
    return hits[:4]


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


def _harmonic_coherence(
    numbers: list[int],
    rows: list[dict[str, Any]],
    previous_numbers: set[int],
    sum_policy: dict[str, Any] | None = None,
    pair_audit: dict[str, Any] | None = None,
) -> dict[str, Any]:
    lookup = _pair_lookup(pair_audit)
    pairs = [_pair_key(pair) for pair in itertools.combinations(numbers, 2)]
    strong_pairs = [lookup[key] for key in pairs if lookup.get(key, {}).get("confidence") in {"medium", "high"}]
    anti_pairs = [lookup[key] for key in pairs if lookup.get(key, {}).get("pair_type") == "anti_pair"]
    block_bridges = [row for row in strong_pairs if row.get("is_block_bridge")]
    clusters = _cluster_hits(numbers, pair_audit)
    row_scores = [float(_find_row(rows, number).get("score", 0.0) or 0.0) for number in numbers]
    total = sum(numbers)
    band = _sum_band(total, sum_policy or {})
    block_profile = block_counts(numbers)
    max_block = max(block_profile.values()) if block_profile else 0
    parity = parity_counts(numbers)
    parity_balance = 1.0 - abs(parity["even"] - parity["odd"]) / 6
    carryover = len(set(numbers) & previous_numbers)
    co_travel_score = round(
        (sum(float(row.get("lift", 0.0)) for row in strong_pairs) + len(block_bridges) * 0.45 + len(clusters) * 0.55)
        / max(len(pairs), 1),
        6,
    )
    sum_score = {
        "historical_core": 1.0,
        "upper_core": 0.82,
        "high_tail": 0.52,
        "low_tail": 0.48,
        "extreme_high": 0.18,
    }.get(band, 0.5)
    concentration_penalty = 0.18 if max_block >= 4 and not block_bridges else 0.0
    anti_penalty = min(len(anti_pairs) * 0.08, 0.24)
    carry_penalty = 0.08 if carryover > 1 else 0.0
    score = (
        _avg(row_scores) * 0.28
        + co_travel_score * 0.28
        + min(len(block_bridges) / 2, 1.0) * 0.16
        + min(len(clusters) / 2, 1.0) * 0.10
        + sum_score * 0.12
        + parity_balance * 0.06
        - concentration_penalty
        - anti_penalty
        - carry_penalty
    )
    notes = []
    if strong_pairs:
        notes.append(f"{len(strong_pairs)} companion pairs support internal coherence.")
    if block_bridges:
        notes.append(f"{len(block_bridges)} bridge pairs connect complementary blocks.")
    if clusters:
        notes.append(f"{len(clusters)} recurring companion clusters present.")
    if band in {"high_tail", "extreme_high", "low_tail"}:
        notes.append(f"Sum band guardrail: {band}.")
    if anti_pairs:
        notes.append(f"{len(anti_pairs)} anti-pair risk markers.")
    notes_es = _harmonic_notes_es(strong_pairs, block_bridges, clusters, band, anti_pairs)
    return {
        "score": round(max(score, 0.0), 6),
        "co_travel_score": co_travel_score,
        "anti_pair_risk_count": len(anti_pairs),
        "block_bridge_pair_count": len(block_bridges),
        "cluster_support_count": len(clusters),
        "sum_band": band,
        "strong_pairs": [row.get("pair") for row in strong_pairs[:6]],
        "anti_pairs": [row.get("pair") for row in anti_pairs[:6]],
        "block_bridge_pairs": [row.get("pair") for row in block_bridges[:6]],
        "clusters": [row.get("numbers") for row in clusters],
        "notes": notes,
        "notes_es": notes_es,
    }


def _composition(
    numbers: list[int],
    previous_numbers: set[int],
    rows: list[dict[str, Any]] | None = None,
    sum_policy: dict[str, Any] | None = None,
    pair_audit: dict[str, Any] | None = None,
) -> dict[str, Any]:
    parity = parity_counts(numbers)
    total = sum(numbers)
    harmonic = _harmonic_coherence(numbers, rows or [], previous_numbers, sum_policy, pair_audit)
    structure = _structure_fields(numbers, previous_numbers)
    overlap = len(set(numbers) & previous_numbers)
    return {
        "parity": parity,
        "parity_signature": _parity_signature(parity),
        "sum": total,
        "sum_band": harmonic["sum_band"],
        "sum_band_es": _sum_band_es(harmonic["sum_band"]),
        "blocks": block_counts(numbers),
        "immediate_overlap_previous_draw": overlap,
        "immediate_overlap_label_es": _immediate_overlap_label_es(overlap),
        "harmonic_coherence": harmonic,
        **structure,
    }


def _ticket(
    ticket_type: str,
    numbers: list[int],
    rows: list[dict[str, Any]],
    previous_numbers: set[int],
    index: int,
    reason: str,
    sum_policy: dict[str, Any] | None = None,
    pair_audit: dict[str, Any] | None = None,
    pair_lag_mode: str | None = None,
) -> dict[str, Any]:
    roles: dict[str, list[str]] = {}
    reasons: dict[str, list[str]] = {}
    reasons_es: dict[str, list[str]] = {}
    harmonic = _harmonic_coherence(numbers, rows, previous_numbers, sum_policy, pair_audit)
    pair_numbers: set[int] = set()
    bridge_numbers: set[int] = set()
    anti_numbers: set[int] = set()
    cluster_numbers: set[int] = set()
    for pair in harmonic.get("strong_pairs", []):
        pair_numbers.update(int(number) for number in pair if isinstance(number, int))
    for pair in harmonic.get("block_bridge_pairs", []):
        bridge_numbers.update(int(number) for number in pair if isinstance(number, int))
    for pair in harmonic.get("anti_pairs", []):
        anti_numbers.update(int(number) for number in pair if isinstance(number, int))
    for cluster in harmonic.get("clusters", []):
        cluster_numbers.update(int(number) for number in cluster if isinstance(number, int))
    for position, number in enumerate(numbers):
        row = _find_row(rows, number)
        number_roles = list(row["roles"])
        if number in pair_numbers:
            number_roles.append("co_travel_companion")
        if number in bridge_numbers:
            number_roles.append("block_bridge_pair")
        if number in cluster_numbers:
            number_roles.append("harmonic_cluster")
        if number in anti_numbers:
            number_roles.append("anti_pair_risk")
        if harmonic.get("sum_band") in {"high_tail", "extreme_high", "low_tail"}:
            number_roles.append("sum_band_guardrail")
        if float(harmonic.get("score", 0.0) or 0.0) >= 0.35:
            number_roles.append("harmonic_support")
        if position == 0:
            number_roles = _unique_text(["anchor"] + number_roles)
        elif "support" not in number_roles:
            number_roles = _unique_text(["support"] + number_roles)
        roles[str(number)] = number_roles
        reasons[str(number)] = row.get("reasons") or ["Selected by V4.3 composition role balance."]
        reasons_es[str(number)] = _reason_es_from_roles(number, number_roles, row)
    composition = _composition(numbers, previous_numbers, rows, sum_policy, pair_audit)
    reason_es = (
        "Variante armonica de respaldo para mantener amplitud y coherencia del conjunto."
        if "Fallback" in reason
        else "Compuesto por roles armonicos V4.3: activacion de bloques, soporte de pares, eco de gap, companions y disciplina de suma."
    )
    if pair_lag_mode == "support_only":
        reason_es += " El pair-lag queda como soporte, no como promotor principal."
    elif pair_lag_mode == "promoter":
        reason_es += " El pair-lag esta validado como puente promotor dentro de este corte."
    elif pair_lag_mode:
        reason_es += f" El pair-lag esta en modo {pair_lag_mode}."
    risk_notes_es = [
        "Conjunto en modo revision.",
        "Capa de revision sin promesa de resultado.",
        *composition.get("harmonic_coherence", {}).get("notes_es", [])[:3],
    ]
    spanish = _ticket_spanish_contract(ticket_type, numbers, composition, roles, reasons_es, reason_es, risk_notes_es)
    return {
        "ticket_id": f"{ticket_type}_{index}",
        "ticket_type": ticket_type,
        "numbers": numbers,
        "roles": roles,
        "reasons": reasons,
        "reasons_es": spanish["reasons_es"],
        "composition": composition,
        "reason": reason,
        "reason_es": spanish["reason_es"],
        "thesis_es": spanish["thesis_es"],
        "decision_summary_es": spanish["decision_summary_es"],
        "structure_summary_es": spanish["structure_summary_es"],
        "explanation_es": spanish["explanation_es"],
        "risk_notes": [
            "Review-default composition slate.",
            "Outcome-neutral review layer.",
            *harmonic.get("notes", [])[:3],
        ],
        "risk_notes_es": spanish["risk_notes_es"],
    }


def _pair_lag_ticket_type(pair_lag_mode: str | None) -> str:
    if pair_lag_mode == "promoter":
        return "pair_lag_bridge"
    if pair_lag_mode == "support_only":
        return "pair_lag_support"
    return "visual_support"


def _unique_text(values: list[str]) -> list[str]:
    output: list[str] = []
    for value in values:
        if value not in output:
            output.append(value)
    return output


def compose_slate_from_rows(
    rows: list[dict[str, Any]],
    previous_draw: list[int],
    pair_lag_mode: str | None = None,
    sum_policy: dict[str, Any] | None = None,
    pair_audit: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
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
    pair_ticket_type = _pair_lag_ticket_type(pair_lag_mode)

    seeds = [
        ("composition_main", _unique((bridge[:2] + focus_numbers[:2] + gap[:1] + cold[:1] + top[:6]))),
        ("activated_block_main", _unique((focus_numbers[:3] + bridge[:2] + top[:6]))),
        (pair_ticket_type, _unique((bridge[:3] + gap[:2] + focus_numbers[:2] + top[:6]))),
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
                "Composed by V4.3 harmonic roles: block activation, pair support, gap echo, companions, and sum discipline.",
                sum_policy,
                pair_audit,
                pair_lag_mode,
            )
        )
    if len(tickets) < 5:
        used_types = {ticket["ticket_type"] for ticket in tickets}
        fallback_types = [
            "composition_main",
            "activated_block_main",
            pair_ticket_type,
            "balanced_hybrid",
            "contrarian_controlled",
            "cold_companion_high_edge",
        ]
        for idx, ticket_type in enumerate(fallback_types, start=1):
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
                    "Fallback V4.3 harmonic composition variant to keep the review slate broad and coherent.",
                    sum_policy,
                    pair_audit,
                    pair_lag_mode,
                )
            )
            if len(tickets) >= 5:
                break
    tickets = _apply_slate_harmonic_order(tickets)
    return tickets[:6]


def _apply_slate_harmonic_order(tickets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not tickets:
        return tickets
    extreme_seen = 0
    scored = []
    used_theses: Counter[str] = Counter()
    for ticket in tickets:
        composition = ticket.get("composition", {})
        harmonic = composition.get("harmonic_coherence", {}) if isinstance(composition, dict) else {}
        band = composition.get("sum_band", "unknown") if isinstance(composition, dict) else "unknown"
        block_key = "|".join(f"{key}:{value}" for key, value in sorted((composition.get("blocks") or {}).items())) if isinstance(composition, dict) else ""
        thesis_key = f"{band}|{block_key}"
        diversity_penalty = min(used_theses[thesis_key] * 0.05, 0.20)
        extreme_penalty = 0.16 if band == "extreme_high" and extreme_seen >= 1 else 0.0
        if band == "extreme_high":
            extreme_seen += 1
        score = float(harmonic.get("score", 0.0) or 0.0) - diversity_penalty - extreme_penalty
        ticket["selection_score"] = round(score, 6)
        if extreme_penalty:
            ticket.setdefault("risk_notes", []).append("Extreme-high sum kept only as a limited review thesis.")
            ticket.setdefault("risk_notes_es", []).append("Suma extremo alto conservada solo como tesis limitada de revision.")
        used_theses[thesis_key] += 1
        scored.append(ticket)
    return sorted(scored, key=lambda ticket: (-float(ticket.get("selection_score", 0.0) or 0.0), ticket.get("ticket_id", "")))


def _slate_structure_summary(tickets: list[dict[str, Any]], pair_lag_mode: str | None) -> dict[str, Any]:
    presence_distribution: Counter[str] = Counter()
    signature_distribution: Counter[str] = Counter()
    sum_band_distribution: Counter[str] = Counter()
    overlap_distribution: Counter[str] = Counter()
    for ticket in tickets:
        composition = ticket.get("composition") if isinstance(ticket, dict) else {}
        if not isinstance(composition, dict):
            continue
        presence_distribution[str(composition.get("block_presence_signature", "unknown"))] += 1
        signature_distribution[str(composition.get("block_signature", "unknown"))] += 1
        sum_band_distribution[str(composition.get("sum_band", "unknown"))] += 1
        overlap_distribution[str(composition.get("immediate_overlap_previous_draw", 0))] += 1
    dominant_presence = presence_distribution.most_common(1)[0][0] if presence_distribution else "unknown"
    dominant_label = _visual_structure_label_es(dominant_presence)
    summary_es = (
        f"El conjunto se concentra principalmente en la presencia visual {dominant_presence}: "
        f"{dominant_label}. Esta lectura describe arquitectura visual de revision, no promesa de resultado."
    )
    return {
        "ticket_count": len(tickets),
        "block_presence_distribution": dict(presence_distribution),
        "block_signature_distribution": dict(signature_distribution),
        "sum_band_distribution": dict(sum_band_distribution),
        "dominant_presence_signature": dominant_presence,
        "dominant_presence_label_es": dominant_label,
        "immediate_overlap_distribution": dict(overlap_distribution),
        "pair_lag_mode": pair_lag_mode,
        "summary_es": summary_es,
    }


def _apply_dominant_presence(tickets: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    dominant = summary.get("dominant_presence_signature")
    for ticket in tickets:
        composition = ticket.get("composition") if isinstance(ticket, dict) else {}
        if not isinstance(composition, dict):
            continue
        matches = bool(dominant and composition.get("block_presence_signature") == dominant)
        composition["matches_dominant_presence_signature"] = matches


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
        slate = compose_slate_from_rows(rows, pre[-1]["numbers"], pair_lag_mode=pair_lag_mode, sum_policy=_sum_policy(pre))
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
    pair_audit_path: str | Path = "v4_pair_companion_audit.json",
) -> dict[str, Any]:
    draws = read_revancha_csv(csv_path)
    if not draws:
        raise SystemExit(f"No valid Revancha draws found in {csv_path}.")
    ranking, v42_available, v42_warning = load_v42_ranking(resultados_path)
    audit = _load_json(audit_path)
    visual = _load_json(visual_path)
    pair_audit = _load_json(pair_audit_path)
    pair_lag_mode = visual.get("pair_lag_mode") if isinstance(visual, dict) else pair_lag_validation(draws).get("status")
    rows = _merge_visual_rows(visual, _candidate_rows_from_draws(draws, ranking, pair_lag_mode=pair_lag_mode))
    sum_policy = _sum_policy(draws)
    slate = compose_slate_from_rows(
        rows,
        draws[-1]["numbers"],
        pair_lag_mode=pair_lag_mode,
        sum_policy=sum_policy,
        pair_audit=pair_audit,
    )
    slate_structure_summary = _slate_structure_summary(slate, pair_lag_mode)
    _apply_dominant_presence(slate, slate_structure_summary)
    warnings = []
    if v42_warning:
        warnings.append(v42_warning)
    if audit is None:
        warnings.append("Composition audit not available; engine used direct CSV features.")
    if visual is None:
        warnings.append("Visual pattern output not available; engine recomputed direct CSV features.")
    if pair_audit is None:
        warnings.append("Pair companion audit not available; harmonic pair support degraded gracefully.")
    validation = walk_forward_validation(draws, ranking, pair_lag_mode=pair_lag_mode)
    sum_distribution = Counter(ticket.get("composition", {}).get("sum_band", "unknown") for ticket in slate)
    harmonic_scores = [
        float(ticket.get("composition", {}).get("harmonic_coherence", {}).get("score", 0.0) or 0.0)
        for ticket in slate
    ]
    pair_summary = {
        "available": pair_audit is not None,
        "top_co_travel_pairs": len(pair_audit.get("top_co_travel_pairs", [])) if isinstance(pair_audit, dict) else 0,
        "top_block_bridge_pairs": len(pair_audit.get("top_block_bridge_pairs", [])) if isinstance(pair_audit, dict) else 0,
        "anti_pairs": len(pair_audit.get("anti_pairs", [])) if isinstance(pair_audit, dict) else 0,
    }
    validation["sum_band_percentiles"] = sum_policy
    validation["slate_sum_distribution"] = dict(sum_distribution)
    validation["visual_structure_contract_version"] = VISUAL_STRUCTURE_CONTRACT_VERSION
    validation["harmonic_coherence_summary"] = {
        "avg_score": _avg(harmonic_scores),
        "min_score": min(harmonic_scores) if harmonic_scores else 0.0,
        "max_score": max(harmonic_scores) if harmonic_scores else 0.0,
    }
    validation["pair_companion_summary"] = pair_summary

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
        "slate_structure_summary": slate_structure_summary,
        "visual_structure_contract_version": VISUAL_STRUCTURE_CONTRACT_VERSION,
        "validation_summary": validation,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build V4.3 hybrid composition slate.")
    parser.add_argument("--csv", default="revancha.csv")
    parser.add_argument("--audit", default="v4_winner_composition_audit.json")
    parser.add_argument("--visual", default="v4_visual_pattern_output.json")
    parser.add_argument("--resultados", default="resultados.json")
    parser.add_argument("--pair-audit", default="v4_pair_companion_audit.json")
    parser.add_argument("--output", default="v4_hybrid_composition_slate.json")
    args = parser.parse_args()
    report = build_slate(args.csv, args.audit, args.visual, args.resultados, args.pair_audit)
    Path(args.output).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {args.output}; tickets={len(report['slate'])} production_status={report['production_status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
