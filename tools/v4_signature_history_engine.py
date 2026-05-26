# -*- coding: utf-8 -*-
"""Analyze historical block signature responses for V4.4."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from v4_history_common import MAX_NUMBER, PRODUCTION_STATUS, block_signature, presence_signature, utc_now, write_json


ENGINE_VERSION = "v4.4-signature-history"


def numbers_from_row(row: list[int]) -> list[int]:
    return [index + 1 for index, value in enumerate(row) if int(value) == 1]


def partial_score(left: str, right: str) -> int:
    return sum(1 for a, b in zip(left.split("-"), right.split("-")) if a == b)


def build_signature_history(matrix_path: str) -> dict:
    data = json.loads(Path(matrix_path).read_text(encoding="utf-8"))
    draws = data["draws"]
    matrix = data["matrix"]
    if not draws or not matrix:
        raise SystemExit("History matrix is empty.")
    rows = [numbers_from_row(row) for row in matrix]
    signatures = [block_signature(numbers) for numbers in rows]
    presences = [presence_signature(numbers) for numbers in rows]
    current_signature = signatures[-1]
    current_presence = presences[-1]
    exact: list[dict] = []
    partial: list[dict] = []
    response_signatures: Counter[str] = Counter()
    numbers_after: Counter[int] = Counter()
    for index in range(0, len(rows) - 1):
        response_numbers = rows[index + 1]
        response_sig = signatures[index + 1]
        match = {
            "draw_id": draws[index],
            "signature": signatures[index],
            "presence_signature": presences[index],
            "response_draw": draws[index + 1],
            "response_signature": response_sig,
            "response_presence_signature": presences[index + 1],
        }
        if signatures[index] == current_signature or presences[index] == current_presence:
            exact.append(match)
            response_signatures[response_sig] += 1
            numbers_after.update(response_numbers)
        elif partial_score(presences[index], current_presence) >= 3:
            partial.append(match)
            response_signatures[response_sig] += 1
            numbers_after.update(response_numbers)
    return {
        "generated_at": utc_now(),
        "engine_version": ENGINE_VERSION,
        "production_status": PRODUCTION_STATUS,
        "latest_draw": data["latest_draw"],
        "current_signature": current_signature,
        "current_presence_signature": current_presence,
        "exact_matches": exact[-60:],
        "partial_matches": partial[-120:],
        "response_signatures": dict(response_signatures.most_common()),
        "most_frequent_response": response_signatures.most_common(1)[0][0] if response_signatures else None,
        "numbers_after": {
            str(number): {"count": count, "signature_history_score": round(count / max(sum(numbers_after.values()), 1), 6)}
            for number, count in numbers_after.most_common(MAX_NUMBER)
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build V4.4 signature history signals.")
    parser.add_argument("--matrix", default="v4_history_matrix.json")
    parser.add_argument("--output", default="v4_signature_history.json")
    args = parser.parse_args()
    report = build_signature_history(args.matrix)
    write_json(args.output, report)
    print(f"Wrote {args.output}; current_presence={report['current_presence_signature']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
