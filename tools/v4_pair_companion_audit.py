# -*- coding: utf-8 -*-
"""Same-draw pair and companion audit for V4.3 harmonic composition."""

from __future__ import annotations

import argparse
import itertools
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from v4_winner_composition_audit import BLOCKS, MAX_NUMBER, block_counts, read_revancha_csv, utc_now


ROOT = Path(__file__).resolve().parents[1]
BRIDGE_BLOCKS = {
    frozenset(("21_30", "41_56")),
    frozenset(("11_20", "41_56")),
    frozenset(("1_10", "21_30")),
    frozenset(("11_20", "21_30")),
}


def _pair_key(pair: tuple[int, int] | list[int]) -> str:
    a, b = sorted((int(pair[0]), int(pair[1])))
    return f"{a:02d}-{b:02d}"


def _block_name(number: int) -> str:
    for name, values in BLOCKS.items():
        if number in values:
            return name
    return "unknown"


def _load_json(path: str | Path) -> dict[str, Any] | None:
    json_path = Path(path)
    if not json_path.exists():
        return None
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _expected_pair_count(number_counts: Counter[int], draws_count: int, a: int, b: int) -> float:
    if draws_count <= 0:
        return 0.0
    return (number_counts[a] / draws_count) * (number_counts[b] / draws_count) * draws_count


def _confidence(observed: int, lift: float, min_observed: int) -> str:
    if observed < min_observed:
        return "low"
    if observed >= max(min_observed + 1, 4) and lift >= 1.25:
        return "high"
    if lift >= 1.12:
        return "medium"
    return "low"


def _top_triplets(draws: list[dict[str, Any]], min_support: int = 2) -> list[dict[str, Any]]:
    counts: Counter[tuple[int, int, int]] = Counter()
    for draw in draws:
        for triplet in itertools.combinations(draw["numbers"], 3):
            counts[tuple(sorted(triplet))] += 1
    rows = []
    for triplet, count in counts.most_common(25):
        if count < min_support:
            continue
        rows.append(
            {
                "numbers": list(triplet),
                "observed_count": count,
                "blocks": block_counts(list(triplet)),
                "support_type": "recurring_triplet",
            }
        )
    return rows[:12]


def _ticket_pair_audit(ticket: dict[str, Any], pair_lookup: dict[str, dict[str, Any]], clusters: list[dict[str, Any]]) -> dict[str, Any]:
    numbers = [int(number) for number in ticket.get("numbers", []) if isinstance(number, int)]
    pairs = [_pair_key(pair) for pair in itertools.combinations(numbers, 2)]
    strong_pairs = [pair_lookup[key] for key in pairs if pair_lookup.get(key, {}).get("confidence") in {"medium", "high"}]
    weak_pairs = [pair_lookup[key] for key in pairs if pair_lookup.get(key, {}).get("confidence") == "low"]
    anti_pairs = [pair_lookup[key] for key in pairs if pair_lookup.get(key, {}).get("pair_type") == "anti_pair"]
    block_bridges = [row for row in strong_pairs if row.get("is_block_bridge")]
    cluster_hits = []
    number_set = set(numbers)
    for cluster in clusters:
        members = set(cluster.get("numbers") or [])
        if len(members & number_set) >= 3:
            cluster_hits.append(cluster)
    possible = max(len(pairs), 1)
    co_travel_score = round(
        (sum(float(row.get("lift", 0.0)) for row in strong_pairs) + len(block_bridges) * 0.35 + len(cluster_hits) * 0.45)
        / possible,
        6,
    )
    harmonic_notes = []
    if strong_pairs:
        harmonic_notes.append(f"{len(strong_pairs)} same-draw companion pairs support this ticket.")
    if block_bridges:
        harmonic_notes.append(f"{len(block_bridges)} pairs bridge complementary blocks.")
    if cluster_hits:
        harmonic_notes.append(f"{len(cluster_hits)} recurring companion clusters are present.")
    risk_notes = []
    if anti_pairs:
        risk_notes.append(f"{len(anti_pairs)} historically weak pair relationships present.")
    return {
        "ticket_id": ticket.get("ticket_id"),
        "ticket_type": ticket.get("ticket_type"),
        "numbers": numbers,
        "co_travel_score": co_travel_score,
        "anti_pair_risk_count": len(anti_pairs),
        "strong_pairs": strong_pairs[:8],
        "weak_pairs": weak_pairs[:8],
        "block_bridge_pairs": block_bridges[:8],
        "cluster_companions": cluster_hits[:6],
        "harmonic_notes": harmonic_notes,
        "risk_notes": risk_notes,
    }


def build_pair_companion_audit(
    csv_path: str | Path = "revancha.csv",
    slate_path: str | Path = "v4_hybrid_composition_slate.json",
    visual_path: str | Path = "v4_visual_pattern_output.json",
    alpha: float = 1.0,
    min_observed_count: int = 3,
) -> dict[str, Any]:
    draws = read_revancha_csv(csv_path)
    if not draws:
        raise SystemExit(f"No valid Revancha draws found in {csv_path}.")
    draws_count = len(draws)
    latest_draw = draws[-1]["draw_id"]
    number_counts = Counter(number for draw in draws for number in draw["numbers"])
    pair_counts: Counter[tuple[int, int]] = Counter()
    recent_pair_counts: Counter[tuple[int, int]] = Counter()
    for draw in draws:
        for pair in itertools.combinations(draw["numbers"], 2):
            pair_counts[tuple(sorted(pair))] += 1
    for draw in draws[-15:]:
        for pair in itertools.combinations(draw["numbers"], 2):
            recent_pair_counts[tuple(sorted(pair))] += 1

    pair_rows: list[dict[str, Any]] = []
    anti_rows: list[dict[str, Any]] = []
    pair_lookup: dict[str, dict[str, Any]] = {}
    common_numbers = {number for number, count in number_counts.items() if count >= max(3, int(draws_count * 0.07))}
    for a in range(1, MAX_NUMBER + 1):
        for b in range(a + 1, MAX_NUMBER + 1):
            observed = pair_counts[(a, b)]
            expected = _expected_pair_count(number_counts, draws_count, a, b)
            lift = round((observed + alpha) / (expected + alpha), 6)
            confidence = _confidence(observed, lift, min_observed_count)
            blocks = sorted({_block_name(a), _block_name(b)})
            is_bridge = frozenset(blocks) in BRIDGE_BLOCKS
            row = {
                "pair": [a, b],
                "pair_key": _pair_key((a, b)),
                "observed_count": observed,
                "expected_count": round(expected, 6),
                "lift": lift,
                "confidence": confidence,
                "recent_pair_activation": recent_pair_counts[(a, b)],
                "blocks": blocks,
                "is_block_bridge": is_bridge,
                "pair_type": "co_travel",
            }
            pair_lookup[row["pair_key"]] = row
            if observed >= min_observed_count and lift >= 1.12:
                pair_rows.append(row)
            if a in common_numbers and b in common_numbers and observed <= 1 and lift < 0.72:
                anti_row = dict(row)
                anti_row["pair_type"] = "anti_pair"
                anti_rows.append(anti_row)
                pair_lookup[row["pair_key"]] = anti_row

    pair_rows.sort(key=lambda row: (-row["lift"], -row["observed_count"], row["pair"]))
    block_bridge_rows = [row for row in pair_rows if row["is_block_bridge"]]
    anti_rows.sort(key=lambda row: (row["observed_count"], row["lift"], row["pair"]))
    clusters = _top_triplets(draws)
    slate = _load_json(slate_path)
    tickets = slate.get("slate", []) if isinstance(slate, dict) and isinstance(slate.get("slate"), list) else []
    ticket_audit = [_ticket_pair_audit(ticket, pair_lookup, clusters) for ticket in tickets]
    visual = _load_json(visual_path)
    warnings = []
    if not tickets:
        warnings.append("No V4.3 slate available; ticket pair audit skipped.")
    if visual is None:
        warnings.append("Visual pattern output unavailable; pair audit used CSV history only.")

    return {
        "generated_at": utc_now(),
        "source": str(csv_path),
        "draws_used": draws_count,
        "latest_draw": latest_draw,
        "pair_policy": {
            "min_observed_count": min_observed_count,
            "alpha": alpha,
            "lift_formula": "(observed + alpha) / (expected + alpha)",
            "no_outcome_certainty_claims": True,
        },
        "top_co_travel_pairs": pair_rows[:40],
        "top_block_bridge_pairs": block_bridge_rows[:30],
        "anti_pairs": anti_rows[:30],
        "cluster_companions": clusters,
        "ticket_pair_audit": ticket_audit,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit same-draw companion pairs for V4.3 composition.")
    parser.add_argument("--csv", default="revancha.csv")
    parser.add_argument("--slate", default="v4_hybrid_composition_slate.json")
    parser.add_argument("--visual", default="v4_visual_pattern_output.json")
    parser.add_argument("--alpha", type=float, default=1.0)
    parser.add_argument("--min-observed-count", type=int, default=3)
    parser.add_argument("--output", default="v4_pair_companion_audit.json")
    args = parser.parse_args()
    report = build_pair_companion_audit(args.csv, args.slate, args.visual, args.alpha, args.min_observed_count)
    Path(args.output).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {args.output}; latest_draw={report['latest_draw']} pairs={len(report['top_co_travel_pairs'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
