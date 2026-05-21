# -*- coding: utf-8 -*-
"""Audit available combination pools inside resultados.json.

The script does not generate combinations. It only validates pools that already
exist in resultados.json and reports whether existing data can support better
diversity than top_combinations alone.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.v4_diversity_selector import (  # noqa: E402
    POOL_NAMES,
    _avg_pairwise_jaccard,
    _combo_numbers,
    _valid_pool_rows,
)

VERSION = "V4.4-candidate-pool-audit"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _pool_status(valid_count: int, unique_numbers: int, avg_jaccard: float) -> str:
    if valid_count <= 0:
        return "missing"
    if valid_count < 10:
        return "too_small"
    if avg_jaccard >= 0.45 or unique_numbers < 18:
        return "too_narrow"
    if valid_count >= 25 and unique_numbers >= 24 and avg_jaccard < 0.35:
        return "broad_enough"
    return "limited"


def _pool_report(data: dict[str, Any], pool_name: str) -> dict[str, Any]:
    exists = pool_name in data and data.get(pool_name) is not None
    rows = _valid_pool_rows(data, pool_name)
    combos = [_combo_numbers(row) for row in rows]
    unique_numbers = len(set(number for combo in combos for number in combo))
    avg_jaccard = _avg_pairwise_jaccard(combos)
    status = _pool_status(len(rows), unique_numbers, avg_jaccard)
    if exists and not rows:
        status = "no_valid_combinations"
    if not exists:
        status = "missing"
    return {
        "exists": bool(exists),
        "valid_combinations": len(rows),
        "unique_numbers": unique_numbers,
        "average_pairwise_jaccard": avg_jaccard,
        "status": status,
    }


def _best_pool(pools: dict[str, dict[str, Any]]) -> tuple[str, dict[str, Any]]:
    valid = [
        (name, row)
        for name, row in pools.items()
        if int(row.get("valid_combinations") or 0) > 0
    ]
    if not valid:
        return "none", {"valid_combinations": 0, "status": "missing"}
    return max(valid, key=lambda item: (int(item[1]["valid_combinations"]), int(item[1]["unique_numbers"])))


def build_audit(input_path: str | Path) -> dict[str, Any]:
    source = Path(input_path)
    data = json.loads(source.read_text(encoding="utf-8"))
    pools = {name: _pool_report(data, name) for name in POOL_NAMES}
    best_name, best = _best_pool(pools)
    top = pools.get("top_combinations", {})
    best_size = int(best.get("valid_combinations") or 0)
    top_size = int(top.get("valid_combinations") or 0)
    can_improve = best_name != "none" and best_name != "top_combinations" and best_size > top_size and best.get("status") in {"broad_enough", "limited"}
    if can_improve:
        reason = f"{best_name} contains {best_size} valid combinations, broader than top_combinations."
    elif best_name == "none":
        reason = "No valid 6-number combination pool was found in resultados.json."
    elif best_name == "top_combinations":
        reason = "Only top_combinations contains valid combinations and it is already highly cloned."
    else:
        reason = f"{best_name} is wider but still not broad enough for confident diversity."
    return {
        "version": VERSION,
        "generated_at": _utc_now(),
        "source_file": str(source),
        "pools_detected": pools,
        "best_available_pool": best_name,
        "best_available_pool_size": best_size,
        "can_improve_diversity_with_existing_data": bool(can_improve),
        "reason": reason,
        "recommendation": "diagnostic_only",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit candidate pools in resultados.json.")
    parser.add_argument("--input", default="resultados.json")
    parser.add_argument("--output", default="v4_candidate_pool_audit.json")
    args = parser.parse_args()
    report = build_audit(args.input)
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {args.output}; best pool: {report['best_available_pool']} ({report['best_available_pool_size']}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
