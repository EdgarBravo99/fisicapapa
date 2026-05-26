# -*- coding: utf-8 -*-
"""Compare a frozen V4.3 pre-draw slate snapshot against an official draw."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from v4_winner_composition_audit import block_counts, read_revancha_csv, utc_now


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_DIR = ROOT / "v4_predraw_slate_snapshots"
BLOCK_ORDER = ["1_10", "11_20", "21_30", "31_40", "41_56"]
VISUAL_STRUCTURE_LABELS_ES = {
    "0-0-1-0-1": "Activacion media-alta: presencia en 21_30 y 41_56",
    "0-1-1-0-1": "Puente 11_20 + 21_30 + 41_56",
    "0-1-0-0-1": "Puente bajo-medio con bloque alto",
    "1-0-1-0-1": "Triangulo 1_10 + 21_30 + 41_56",
    "1-1-1-0-0": "Escalera baja-media hasta 21_30",
    "0-1-1-1-0": "Centro extendido 11_20 + 21_30 + 31_40",
}
ROLE_SUMMARY_KEYS = {
    "activated_block": "activated_block_hit_summary",
    "bridge_pair_lag": "pair_lag_support_hit_summary",
    "pair_lag_support": "pair_lag_support_hit_summary",
    "co_travel_companion": "co_travel_companion_hit_summary",
    "block_bridge_pair": "block_bridge_pair_hit_summary",
    "harmonic_cluster": "harmonic_cluster_hit_summary",
    "gap_echo": "gap_echo_hit_summary",
    "cold_companion": "cold_companion_hit_summary",
}


def _signature(values: list[int]) -> str:
    return "-".join(str(int(value)) for value in values)


def _visual_structure_label_es(presence_signature: str) -> str:
    return VISUAL_STRUCTURE_LABELS_ES.get(presence_signature, f"Presencia visual {presence_signature}")


def _structure_fields(numbers: list[int]) -> dict[str, Any]:
    blocks = block_counts(numbers)
    block_vector = [int(blocks.get(block, 0) or 0) for block in BLOCK_ORDER]
    presence_vector = [1 if value > 0 else 0 for value in block_vector]
    presence_signature = _signature(presence_vector)
    return {
        "block_signature": _signature(block_vector),
        "block_presence_signature": presence_signature,
        "visual_structure_label_es": _visual_structure_label_es(presence_signature),
    }


def _load_json(path: str | Path) -> dict[str, Any]:
    json_path = Path(path)
    with json_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Expected object in {json_path}")
    return data


def _snapshot_path(target_draw: int) -> Path:
    return SNAPSHOT_DIR / f"v4_predraw_slate_target_{target_draw}.json"


def _target_draw_from_snapshot(snapshot: dict[str, Any]) -> int | None:
    value = snapshot.get("target_draw")
    return value if isinstance(value, int) else None


def _parse_date(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def _leakage_check(snapshot: dict[str, Any], raw_draw: dict[str, Any]) -> dict[str, Any]:
    draw_date = _parse_date(raw_draw.get("FECHA") or raw_draw.get("date") or raw_draw.get("draw_date"))
    created_at = _parse_date(snapshot.get("snapshot_created_at"))
    if draw_date is None:
        return {
            "checked": False,
            "status": "unknown",
            "reason": "WARNING: CSV has no draw timestamp/date; cannot verify whether snapshot was created before result availability.",
        }
    if created_at is None:
        return {"checked": False, "status": "unknown", "reason": "Snapshot timestamp is unavailable or invalid."}
    if created_at.date() > draw_date.date():
        return {
            "checked": True,
            "status": "warning",
            "reason": "WARNING: snapshot may have been created after draw result was available.",
        }
    return {"checked": True, "status": "ok", "reason": "Snapshot timestamp is not after draw date."}


def _summary_from_counts(hit_counts: Counter[str], total_counts: Counter[str]) -> dict[str, Any]:
    return {
        key: {
            "hits": hit_counts[key],
            "total": total_counts[key],
            "hit_rate": round(hit_counts[key] / total_counts[key], 6) if total_counts[key] else 0.0,
        }
        for key in sorted(total_counts)
    }


def _actual_pair_profile(numbers: list[int]) -> dict[str, Any]:
    ordered = sorted(numbers)
    consecutive_pairs = [pair for pair in zip(ordered, ordered[1:]) if pair[1] - pair[0] == 1]
    block_profile = block_counts(ordered)
    return {
        "numbers": ordered,
        "blocks": block_profile,
        "consecutive_pair_count": len(consecutive_pairs),
        "consecutive_pairs": [list(pair) for pair in consecutive_pairs],
        "sum": sum(ordered),
    }


def build_post_draw_audit(
    target_draw: int | None = None,
    snapshot_path: str | Path | None = None,
    csv_path: str | Path = "revancha.csv",
) -> dict[str, Any]:
    if snapshot_path is not None:
        snapshot = _load_json(snapshot_path)
        inferred_target = _target_draw_from_snapshot(snapshot)
        final_target = int(target_draw or inferred_target or 0)
    else:
        if target_draw is None:
            raise ValueError("--target-draw is required when --snapshot is not provided.")
        final_target = int(target_draw)
        snapshot = _load_json(_snapshot_path(final_target))
    if final_target <= 0:
        raise ValueError("Unable to determine target draw.")

    draws = read_revancha_csv(csv_path)
    target = next((draw for draw in draws if draw["draw_id"] == final_target), None)
    if target is None:
        raise LookupError("target draw not found in revancha.csv")

    actual_numbers = target["numbers"]
    tickets = snapshot.get("slate", []) if isinstance(snapshot.get("slate"), list) else []
    ticket_results = []
    role_hits: Counter[str] = Counter()
    role_total: Counter[str] = Counter()
    role_missed: Counter[str] = Counter()
    type_hits: dict[str, list[int]] = defaultdict(list)
    hit_counts: list[int] = []
    target_set = set(actual_numbers)
    actual_structure = _structure_fields(actual_numbers)

    for ticket in tickets:
        numbers = ticket.get("numbers") if isinstance(ticket, dict) else []
        numbers = [int(number) for number in numbers if isinstance(number, int)]
        hit_numbers = sorted(set(numbers) & target_set)
        missed_numbers = sorted(set(numbers) - target_set)
        hits = len(hit_numbers)
        hit_counts.append(hits)
        ticket_type = str(ticket.get("ticket_type", "unknown"))
        type_hits[ticket_type].append(hits)
        roles = ticket.get("roles") if isinstance(ticket.get("roles"), dict) else {}
        composition = ticket.get("composition") if isinstance(ticket.get("composition"), dict) else {}
        ticket_structure = {
            "block_signature": composition.get("block_signature"),
            "block_presence_signature": composition.get("block_presence_signature"),
            "visual_structure_label_es": composition.get("visual_structure_label_es"),
        }
        fallback_structure = _structure_fields(numbers)
        for key, value in fallback_structure.items():
            if not ticket_structure.get(key):
                ticket_structure[key] = value
        for number in numbers:
            for role in roles.get(str(number), ["support"]):
                role_total[role] += 1
                if number in target_set:
                    role_hits[role] += 1
                else:
                    role_missed[role] += 1
        ticket_results.append(
            {
                "ticket_id": ticket.get("ticket_id"),
                "ticket_type": ticket_type,
                "numbers": numbers,
                "hits": hits,
                "hit_numbers": hit_numbers,
                "missed_numbers": missed_numbers,
                "sum_band": ticket.get("composition", {}).get("sum_band"),
                "sum_band_es": ticket.get("composition", {}).get("sum_band_es"),
                "block_signature": ticket_structure["block_signature"],
                "block_presence_signature": ticket_structure["block_presence_signature"],
                "visual_structure_label_es": ticket_structure["visual_structure_label_es"],
                "actual_draw_matched_ticket_presence_signature": actual_structure["block_presence_signature"] == ticket_structure["block_presence_signature"],
                "harmonic_coherence": ticket.get("composition", {}).get("harmonic_coherence", {}),
            }
        )

    ticket_type_summary = {
        key: {
            "tickets": len(values),
            "avg_hits": round(sum(values) / len(values), 6) if values else 0.0,
            "best_hits": max(values) if values else 0,
        }
        for key, values in sorted(type_hits.items())
    }
    role_hit_summary = _summary_from_counts(role_hits, role_total)
    role_missed_summary = _summary_from_counts(role_missed, role_total)
    specialized = {output_key: role_hit_summary.get(role, {"hits": 0, "total": 0, "hit_rate": 0.0}) for role, output_key in ROLE_SUMMARY_KEYS.items()}
    carry_roles = ("immediate_carryover", "carryover")
    specialized["immediate_carryover_hit_summary"] = {
        "hits": sum(role_hits[role] for role in carry_roles),
        "total": sum(role_total[role] for role in carry_roles),
        "hit_rate": round(sum(role_hits[role] for role in carry_roles) / sum(role_total[role] for role in carry_roles), 6)
        if sum(role_total[role] for role in carry_roles)
        else 0.0,
    }

    best_hits = max(hit_counts) if hit_counts else 0
    slate_blocks = Counter()
    for ticket in ticket_results:
        for block, count in block_counts(ticket["numbers"]).items():
            slate_blocks[block] += count
    actual_blocks = block_counts(actual_numbers)
    matched_blocks = sum(min(actual_blocks[block], slate_blocks[block]) for block in actual_blocks)

    structure_matches = sum(1 for ticket in ticket_results if ticket.get("actual_draw_matched_ticket_presence_signature"))

    return {
        "version": "V4.3-post-draw-audit",
        "generated_at": utc_now(),
        "mode": "diagnostic_only",
        "target_draw": final_target,
        "snapshot_source_latest_draw": snapshot.get("source_latest_draw"),
        "actual_numbers": actual_numbers,
        "leakage_check": _leakage_check(snapshot, target.get("raw", {})),
        "ticket_results": ticket_results,
        "best_ticket_hits": best_hits,
        "avg_hits": round(sum(hit_counts) / len(hit_counts), 6) if hit_counts else 0.0,
        "zero_ticket_count": sum(1 for value in hit_counts if value == 0),
        "hit_ge_1_count": sum(1 for value in hit_counts if value >= 1),
        "hit_ge_2_count": sum(1 for value in hit_counts if value >= 2),
        "hit_ge_3_count": sum(1 for value in hit_counts if value >= 3),
        "role_hit_summary": role_hit_summary,
        "role_missed_summary": role_missed_summary,
        "ticket_type_hit_summary": ticket_type_summary,
        **specialized,
        "sum_band_result": {
            "actual_sum": sum(actual_numbers),
            "ticket_sum_bands": Counter(str(ticket.get("sum_band", "unknown")) for ticket in ticket_results),
        },
        "actual_draw_block_profile": actual_blocks,
        "actual_draw_block_signature": actual_structure["block_signature"],
        "actual_draw_block_presence_signature": actual_structure["block_presence_signature"],
        "actual_draw_visual_structure_label_es": actual_structure["visual_structure_label_es"],
        "actual_draw_pair_co_travel_profile": _actual_pair_profile(actual_numbers),
        "actual_draw_matched_slate_thesis": matched_blocks >= 4 or best_hits >= 2,
        "new_harmonic_pattern_to_review": best_hits < 2,
        "post_draw_summary_es": f"El sorteo {final_target} tuvo mejor boleto con {best_hits} matches y promedio {round(sum(hit_counts) / len(hit_counts), 3) if hit_counts else 0.0}.",
        "structure_match_summary_es": (
            f"La estructura real fue {actual_structure['block_presence_signature']}: {actual_structure['visual_structure_label_es']}. "
            f"{structure_matches} boletos compartieron esa presencia visual."
        ),
        "recommendation": "diagnostic_only",
        "warnings": [],
    }


def append_log(report: dict[str, Any], path: str | Path = "v4_post_draw_audit_log.jsonl") -> None:
    with Path(path).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(report, ensure_ascii=False) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit a frozen pre-draw V4.3 slate against a target draw.")
    parser.add_argument("--target-draw", type=int, default=None)
    parser.add_argument("--snapshot", default=None)
    parser.add_argument("--csv", default="revancha.csv")
    parser.add_argument("--output", default="v4_post_draw_audit.json")
    parser.add_argument("--append-log", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--log", default="v4_post_draw_audit_log.jsonl")
    args = parser.parse_args()

    try:
        report = build_post_draw_audit(args.target_draw, args.snapshot, args.csv)
    except (FileNotFoundError, ValueError, LookupError, json.JSONDecodeError) as exc:
        print(f"[v4-post-draw-audit] {exc}")
        return 1

    Path(args.output).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    if args.append_log:
        append_log(report, args.log)
    print(f"Wrote {args.output}; target_draw={report['target_draw']} best_ticket_hits={report['best_ticket_hits']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
