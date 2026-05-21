# -*- coding: utf-8 -*-
"""Compare cloned top combinations against diversified review sets."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from v4_benchmark_hardening import combo_numbers, combo_score, load_replay_records, target_numbers, utc_now

VERSION = "V4.4-diversified-vs-original-eval"


def _load(path: str | Path) -> dict[str, Any] | None:
    file_path = Path(path)
    if not file_path.exists():
        return None
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _jaccard(left: list[int], right: list[int]) -> float:
    union = set(left) | set(right)
    return len(set(left) & set(right)) / len(union) if union else 0.0


def _avg_overlap(combos: list[list[int]]) -> float:
    if len(combos) < 2:
        return 0.0
    total = 0.0
    pairs = 0
    for index, combo in enumerate(combos):
        for other in combos[index + 1 :]:
            total += _jaccard(combo, other)
            pairs += 1
    return round(total / pairs, 6) if pairs else 0.0


def _set_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    combos = [combo_numbers(row) for row in rows]
    combos = [combo for combo in combos if combo]
    scores = [combo_score(row) for row in rows if combo_numbers(row)]
    return {
        "count": len(combos),
        "average_overlap": _avg_overlap(combos),
        "unique_numbers_covered": len(set(number for combo in combos for number in combo)),
        "average_score_reference": round(sum(scores) / len(scores), 6) if scores else 0.0,
        "combinations": combos,
    }


def _best_hits_for_set(combos: list[list[int]], target: set[int]) -> int:
    return max((len(set(combo) & target) for combo in combos), default=0)


def _hit_eval(original: dict[str, Any], diversified: dict[str, Any], balanced: dict[str, Any], records: list[dict[str, Any]]) -> dict[str, Any]:
    if not records or not original["combinations"] or not diversified["combinations"]:
        return {
            "hit_evaluation_available": False,
            "reason": "Replay records do not expose comparable original/diversified combination hits.",
        }
    original_hits = []
    diversified_hits = []
    balanced_hits = []
    for record in records:
        target = set(target_numbers(record))
        original_hits.append(_best_hits_for_set(original["combinations"], target))
        diversified_hits.append(_best_hits_for_set(diversified["combinations"], target))
        balanced_hits.append(_best_hits_for_set(balanced["combinations"], target))
    count = len(records)
    return {
        "hit_evaluation_available": True,
        "records_count": count,
        "best_hits_original_avg": round(sum(original_hits) / count, 6),
        "best_hits_diversified_avg": round(sum(diversified_hits) / count, 6),
        "best_hits_balanced_avg": round(sum(balanced_hits) / count, 6),
        "diversified_minus_original": round((sum(diversified_hits) - sum(original_hits)) / count, 6),
    }


def build_eval(
    diversity_path: str = "v4_diversity_output.json",
    slate_path: str = "v4_decision_slate.json",
    replay_memory: str = "v4_replay_memory.json",
) -> dict[str, Any]:
    diversity = _load(diversity_path) or {}
    slate = _load(slate_path) or {}
    review_sets = slate.get("review_sets") if isinstance(slate.get("review_sets"), dict) else {}
    original_rows = review_sets.get("pure_rank_top") if isinstance(review_sets.get("pure_rank_top"), list) else []
    diversified_rows = review_sets.get("diversified_top") if isinstance(review_sets.get("diversified_top"), list) else []
    if not diversified_rows and isinstance(diversity.get("diversified_combinations"), list):
        diversified_rows = diversity.get("diversified_combinations", [])
    balanced_rows = review_sets.get("balanced_review_set") if isinstance(review_sets.get("balanced_review_set"), list) else []
    if not isinstance(balanced_rows, list):
        balanced_rows = []
    original = _set_metrics(original_rows)
    diversified = _set_metrics(diversified_rows)
    balanced = _set_metrics(balanced_rows)
    records, replay_state = load_replay_records(replay_memory)
    hit_eval = _hit_eval(original, diversified, balanced, records)
    coverage_gain = diversified["unique_numbers_covered"] - original["unique_numbers_covered"]
    score_loss = round(original["average_score_reference"] - diversified["average_score_reference"], 6)
    return {
        "version": VERSION,
        "generated_at": utc_now(),
        "source_files": {"diversity": diversity_path, "decision_slate": slate_path, "replay_memory": replay_memory},
        "replay_input_state": replay_state,
        "original": original | {"combinations": None},
        "diversified": diversified | {"combinations": None},
        "balanced": balanced | {"combinations": None},
        "coverage_gain": coverage_gain,
        "score_loss_from_diversification": score_loss,
        "comparison_notes": [
            "Original comes from decision_slate.review_sets.pure_rank_top when available.",
            "Diversified comes from decision_slate.review_sets.diversified_top or v4_diversity_output.json.",
            "No new combinations are generated and no scores are modified.",
        ],
        **hit_eval,
        "recommendation": "diagnostic_only",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate diversified vs original review sets.")
    parser.add_argument("--output", default="v4_diversified_vs_original_eval.json")
    parser.add_argument("--diversity", default="v4_diversity_output.json")
    parser.add_argument("--slate", default="v4_decision_slate.json")
    parser.add_argument("--replay-memory", default="v4_replay_memory.json")
    args = parser.parse_args()
    report = build_eval(args.diversity, args.slate, args.replay_memory)
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {args.output}; coverage_gain={report['coverage_gain']}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
