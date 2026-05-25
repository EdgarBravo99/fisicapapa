# -*- coding: utf-8 -*-
"""Export visual binary matrices for Revancha harmonic review."""

from __future__ import annotations

import argparse
import csv
import itertools
import json
from collections import Counter
from pathlib import Path
from typing import Any

from v4_winner_composition_audit import MAX_NUMBER, read_revancha_csv, utc_now


ROOT = Path(__file__).resolve().parents[1]
EXPORT_DIR = ROOT / "visual_exports"


def _load_json(path: str | Path) -> dict[str, Any] | None:
    json_path = Path(path)
    if not json_path.exists():
        return None
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _pattern(numbers: list[int]) -> list[int]:
    number_set = set(numbers)
    return [1 if number in number_set else 0 for number in range(1, MAX_NUMBER + 1)]


def _pattern_text(numbers: list[int]) -> str:
    return "-".join(str(value) for value in _pattern(numbers))


def export_visual_matrices(
    csv_path: str | Path = "revancha.csv",
    slate_path: str | Path = "v4_hybrid_composition_slate.json",
    pair_audit_path: str | Path = "v4_pair_companion_audit.json",
    output_dir: str | Path = EXPORT_DIR,
) -> dict[str, Any]:
    draws = read_revancha_csv(csv_path)
    if not draws:
        raise SystemExit(f"No valid Revancha draws found in {csv_path}.")
    export_dir = Path(output_dir)
    export_dir.mkdir(parents=True, exist_ok=True)

    wide_path = export_dir / "revancha_visual_matrix.csv"
    compact_path = export_dir / "revancha_visual_matrix_compact.csv"
    candidate_path = export_dir / "revancha_visual_candidate_overlay.csv"
    pair_path = export_dir / "revancha_visual_pair_overlay.csv"

    number_columns = [f"n{number:02d}" for number in range(1, MAX_NUMBER + 1)]
    with wide_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["draw_id", *number_columns])
        for draw in draws:
            writer.writerow([draw["draw_id"], *_pattern(draw["numbers"])])

    with compact_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["draw_id", "pattern"])
        writer.writeheader()
        for draw in draws:
            writer.writerow({"draw_id": draw["draw_id"], "pattern": _pattern_text(draw["numbers"])})

    slate = _load_json(slate_path)
    ticket_count = 0
    with candidate_path.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = ["row_type", "synthetic", "target_draw", "ticket_id", "ticket_type", "pattern", *number_columns]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        tickets = slate.get("slate", []) if isinstance(slate, dict) and isinstance(slate.get("slate"), list) else []
        target_draw = int(slate.get("latest_draw", 0) or 0) + 1 if isinstance(slate, dict) else ""
        for ticket in tickets:
            numbers = ticket.get("numbers") if isinstance(ticket, dict) else None
            if not isinstance(numbers, list) or len(numbers) != 6:
                continue
            values = _pattern([int(number) for number in numbers])
            row = {
                "row_type": "candidate",
                "synthetic": "true",
                "target_draw": target_draw,
                "ticket_id": ticket.get("ticket_id", ""),
                "ticket_type": ticket.get("ticket_type", ""),
                "pattern": "-".join(str(value) for value in values),
            }
            row.update({column: value for column, value in zip(number_columns, values)})
            writer.writerow(row)
            ticket_count += 1

    pair_audit = _load_json(pair_audit_path)
    pair_rows = []
    if isinstance(pair_audit, dict) and isinstance(pair_audit.get("top_co_travel_pairs"), list):
        pair_rows = pair_audit["top_co_travel_pairs"][:120]
    else:
        counts: Counter[tuple[int, int]] = Counter()
        for draw in draws:
            counts.update(tuple(sorted(pair)) for pair in itertools.combinations(draw["numbers"], 2))
        pair_rows = [
            {"pair": list(pair), "observed_count": count, "lift": "", "confidence": "raw_count"}
            for pair, count in counts.most_common(120)
        ]
    with pair_path.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = ["pair", "a", "b", "observed_count", "lift", "confidence", "blocks", "is_block_bridge"]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in pair_rows:
            pair = row.get("pair") or []
            if len(pair) != 2:
                continue
            writer.writerow(
                {
                    "pair": f"{int(pair[0]):02d}-{int(pair[1]):02d}",
                    "a": int(pair[0]),
                    "b": int(pair[1]),
                    "observed_count": row.get("observed_count", ""),
                    "lift": row.get("lift", ""),
                    "confidence": row.get("confidence", ""),
                    "blocks": "|".join(row.get("blocks", [])) if isinstance(row.get("blocks"), list) else "",
                    "is_block_bridge": row.get("is_block_bridge", False),
                }
            )

    return {
        "generated_at": utc_now(),
        "source": str(csv_path),
        "latest_draw": draws[-1]["draw_id"],
        "draws_exported": len(draws),
        "paths": {
            "wide_matrix": str(wide_path),
            "compact_matrix": str(compact_path),
            "candidate_overlay": str(candidate_path),
            "pair_overlay": str(pair_path),
        },
        "candidate_overlay_rows": ticket_count,
        "warnings": ["visual_exports contains visual-only overlays; do not use as canonical history."],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Export Revancha visual binary matrices under visual_exports/.")
    parser.add_argument("--csv", default="revancha.csv")
    parser.add_argument("--slate", default="v4_hybrid_composition_slate.json")
    parser.add_argument("--pair-audit", default="v4_pair_companion_audit.json")
    parser.add_argument("--output-dir", default=str(EXPORT_DIR))
    parser.add_argument("--report", default="v4_visual_matrix_export_report.json")
    args = parser.parse_args()
    report = export_visual_matrices(args.csv, args.slate, args.pair_audit, args.output_dir)
    Path(args.report).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote visual exports under {args.output_dir}; latest_draw={report['latest_draw']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
