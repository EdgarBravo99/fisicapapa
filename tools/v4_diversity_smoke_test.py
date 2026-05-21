# -*- coding: utf-8 -*-
"""Focused smoke tests for the V4.4 diversity selector."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.v4_diversity_selector import build_report  # noqa: E402


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_smoke() -> dict[str, bool]:
    fixture = {
        "score_kind": "v4_2_deep_stacking_meta_score",
        "top_combinations": [
            {"numbers": [1, 2, 3, 4, 5, 6], "score_percent": 99},
            {"numbers": [1, 2, 3, 4, 5, 7], "score_percent": 95},
            {"numbers": [10, 11, 12, 13, 14, 15], "score_percent": 90},
            {"numbers": [10, 11, 12, 13, 14, 16], "score_percent": 88},
        ],
    }
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "resultados.json"
        path.write_text(json.dumps(fixture), encoding="utf-8")
        before = _sha(path)
        report = build_report(path, 4, 0.7)
        after = _sha(path)
    matrix = report["overlap_matrix"]
    scores = [row["original_score"] for row in report["diversified_combinations"]]
    return {
        "input_not_modified": before == after,
        "matrix_symmetric": all(matrix[i][j] == matrix[j][i] for i in range(len(matrix)) for j in range(len(matrix))),
        "jaccard_range": all(0 <= value <= 1 for row in matrix for value in row),
        "scores_preserved": all(score in {99.0, 95.0, 90.0, 88.0} for score in scores),
    }


def main() -> int:
    checks = run_smoke()
    for name, ok in checks.items():
        print(f"{name}: {'OK' if ok else 'FAIL'}")
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
