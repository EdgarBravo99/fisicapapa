# -*- coding: utf-8 -*-
"""Build a read-only diversity audit for current top combinations.

This tool reads only resultados.json and writes a diagnostic MMR selection.
It does not modify scores, rankings, CSV files, memory files, or resultados.json.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MAX_NUMBER = 56
VERSION = "V4.4-decision-audit-pack"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_int(value: Any) -> int | None:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None


def _combo_numbers(row: Any) -> list[int]:
    if isinstance(row, dict):
        raw = row.get("numbers") or row.get("combo") or row.get("combination") or []
    else:
        raw = row
    if not isinstance(raw, list):
        return []
    numbers: list[int] = []
    for value in raw:
        parsed = _parse_int(value)
        if parsed is not None and 1 <= parsed <= MAX_NUMBER and parsed not in numbers:
            numbers.append(parsed)
    return sorted(numbers) if len(numbers) == 6 else []


def _combo_score(row: dict[str, Any]) -> float:
    for key in ("score_percent", "net_score", "score", "confidence"):
        value = row.get(key)
        try:
            score = float(value)
        except (TypeError, ValueError):
            continue
        if key == "net_score" and 0 <= score <= 1:
            return score * 100.0
        return score
    return 0.0


def _jaccard(left: list[int], right: list[int]) -> float:
    left_set = set(left)
    right_set = set(right)
    union = left_set | right_set
    if not union:
        return 0.0
    return len(left_set & right_set) / len(union)


def _overlap(left: list[int], right: list[int]) -> int:
    return len(set(left) & set(right))


def _avg_pairwise_jaccard(combos: list[list[int]]) -> float:
    if len(combos) < 2:
        return 0.0
    total = 0.0
    pairs = 0
    for index, combo in enumerate(combos):
        for other in combos[index + 1 :]:
            total += _jaccard(combo, other)
            pairs += 1
    return round(total / pairs, 6) if pairs else 0.0


def _pool_entropy(combos: list[list[int]]) -> float:
    counts = Counter(number for combo in combos for number in combo)
    total = sum(counts.values())
    if not total:
        return 0.0
    entropy = -sum((count / total) * math.log(count / total) for count in counts.values())
    return round(entropy / math.log(MAX_NUMBER), 6)


def _normalize_scores(scores: list[float]) -> list[float]:
    if not scores:
        return []
    low = min(scores)
    high = max(scores)
    if math.isclose(low, high):
        return [1.0 for _ in scores]
    return [(score - low) / (high - low) for score in scores]


def _selection_reason(max_overlap: int, relaxed: bool, insufficient_pool: bool) -> str:
    if relaxed:
        return "overlap_relaxed"
    if insufficient_pool:
        return "insufficient_pool"
    return "mmr_selected"


def select_diverse_combos(
    rows: list[dict[str, Any]],
    k: int,
    lambda_param: float,
    preferred_overlap: int = 4,
    relaxed_overlap: int = 5,
) -> tuple[list[dict[str, Any]], list[str]]:
    combos = [_combo_numbers(row) for row in rows]
    scores = [_combo_score(row) for row in rows]
    normalized_scores = _normalize_scores(scores)
    candidates = [
        {
            "rank_original": index + 1,
            "row": rows[index],
            "numbers": combos[index],
            "original_score": scores[index],
            "normalized_score": normalized_scores[index],
        }
        for index in range(len(rows))
        if combos[index]
    ]
    notes: list[str] = []
    if not candidates:
        return [], ["No valid top_combinations were found."]
    if len(candidates) < k:
        notes.append(f"Only {len(candidates)} valid combinations available for k={k}.")

    selected: list[dict[str, Any]] = []
    first = candidates[0].copy()
    first.update(
        {
            "rank_diversified": 1,
            "mmr_score": round(first["normalized_score"], 6),
            "max_overlap_with_previous": 0,
            "max_jaccard_with_previous": 0.0,
            "selection_reason": "top_rank_anchor",
        }
    )
    selected.append(first)
    remaining = candidates[1:]

    while remaining and len(selected) < k:
        selected_numbers = [row["numbers"] for row in selected]
        scored: list[tuple[float, int, float, dict[str, Any]]] = []
        for candidate in remaining:
            max_jaccard = max(_jaccard(candidate["numbers"], combo) for combo in selected_numbers)
            max_overlap = max(_overlap(candidate["numbers"], combo) for combo in selected_numbers)
            mmr = lambda_param * candidate["normalized_score"] - (1 - lambda_param) * max_jaccard
            scored.append((mmr, max_overlap, max_jaccard, candidate))

        viable = [row for row in scored if row[1] <= preferred_overlap]
        relaxed = False
        insufficient = False
        if not viable:
            viable = [row for row in scored if row[1] <= relaxed_overlap]
            relaxed = bool(viable)
        if not viable:
            viable = scored
            insufficient = True

        best = max(viable, key=lambda row: (row[0], -row[1], row[3]["normalized_score"], -row[3]["rank_original"]))
        chosen = best[3].copy()
        chosen.update(
            {
                "rank_diversified": len(selected) + 1,
                "mmr_score": round(best[0], 6),
                "max_overlap_with_previous": best[1],
                "max_jaccard_with_previous": round(best[2], 6),
                "selection_reason": _selection_reason(best[1], relaxed, insufficient),
            }
        )
        selected.append(chosen)
        remaining = [row for row in remaining if row["rank_original"] != chosen["rank_original"]]

    return selected, notes


def _overlap_matrix(combos: list[list[int]]) -> list[list[float]]:
    return [[round(_jaccard(left, right), 6) for right in combos] for left in combos]


def build_report(input_path: str | Path, k: int, lambda_param: float) -> dict[str, Any]:
    source = Path(input_path)
    data = json.loads(source.read_text(encoding="utf-8"))
    rows = data.get("top_combinations")
    if not isinstance(rows, list):
        rows = []
    top_rows = [row for row in rows if isinstance(row, dict)]
    original_combos = [_combo_numbers(row) for row in top_rows[:k]]
    original_combos = [combo for combo in original_combos if combo]
    selected, notes = select_diverse_combos(top_rows, k, lambda_param)
    diversified_combos = [row["numbers"] for row in selected]

    report_rows = []
    for row in selected:
        report_rows.append(
            {
                "rank_diversified": row["rank_diversified"],
                "rank_original": row["rank_original"],
                "numbers": row["numbers"],
                "original_score": round(float(row["original_score"]), 6),
                "normalized_score": round(float(row["normalized_score"]), 6),
                "mmr_score": row["mmr_score"],
                "max_overlap_with_previous": row["max_overlap_with_previous"],
                "max_jaccard_with_previous": row["max_jaccard_with_previous"],
                "selection_reason": row["selection_reason"],
            }
        )

    original_jaccard = _avg_pairwise_jaccard(original_combos)
    diversified_jaccard = _avg_pairwise_jaccard(diversified_combos)
    unique_original = len(set(number for combo in original_combos for number in combo))
    unique_diversified = len(set(number for combo in diversified_combos for number in combo))
    if original_jaccard >= 0.35:
        notes.append("High overlap detected in current top_combinations.")
    if len(original_combos) >= k and unique_original < min(MAX_NUMBER, k * 4):
        notes.append("Top combinations use a narrow number pool; consider reviewing generator diversity.")
    if len(top_rows) >= k and diversified_jaccard > original_jaccard:
        notes.append("Diversified overlap is not lower than original top-k; top_combinations may already be constrained or too small.")
    if len(top_rows) >= k and diversified_jaccard == original_jaccard:
        notes.append("MMR could not improve overlap using only top_combinations.")

    return {
        "version": VERSION,
        "generated_at": _utc_now(),
        "source_file": str(source),
        "score_kind": data.get("score_kind") or data.get("v4_score_kind") or "N/D",
        "lambda_used": lambda_param,
        "k": k,
        "pool_size": len(top_rows),
        "pool_entropy": _pool_entropy([_combo_numbers(row) for row in top_rows if _combo_numbers(row)]),
        "average_pairwise_jaccard_original": original_jaccard,
        "average_pairwise_jaccard_diversified": diversified_jaccard,
        "unique_numbers_original_top_k": unique_original,
        "unique_numbers_diversified": unique_diversified,
        "diversity_gain": round(original_jaccard - diversified_jaccard, 6),
        "diversified_combinations": report_rows,
        "overlap_matrix": _overlap_matrix(diversified_combos),
        "quality_notes": notes,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build V4.4 diversity audit from resultados.json.")
    parser.add_argument("--input", default="resultados.json")
    parser.add_argument("--output", default="v4_diversity_output.json")
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--lambda-param", type=float, default=0.7)
    args = parser.parse_args()

    report = build_report(args.input, max(1, args.k), min(1.0, max(0.0, args.lambda_param)))
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {args.output} with {len(report['diversified_combinations'])} diversified combinations.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
