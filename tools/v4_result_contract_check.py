#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Lightweight V4 result contract checker."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

FORBIDDEN_FIELDS = {"_".join(("operational", "confidence"))}


def check_contract(path: str | Path = "resultados.json") -> dict[str, Any]:
    result_path = Path(path)
    errors: list[str] = []
    warnings: list[str] = []
    if not result_path.exists():
        return {"ok": False, "errors": [f"No existe {result_path}"], "warnings": []}
    try:
        data = json.loads(result_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"ok": False, "errors": [f"JSON invalido: {exc}"], "warnings": []}
    if not isinstance(data, dict):
        return {"ok": False, "errors": ["Se esperaba objeto JSON"], "warnings": []}
    for field in ("score_kind", "game_mode", "number_scores", "manual_suggestion_seed", "generator_pool", "top_combinations", "walk_forward", "physics_summary"):
        if field not in data:
            warnings.append(f"Falta campo esperado: {field}")
    for forbidden in FORBIDDEN_FIELDS:
        if forbidden in json.dumps(data):
            errors.append(f"Campo prohibido presente: {forbidden}")
    feedback = data.get("feedback_memory")
    if feedback and feedback.get("memory_prior_applied") and feedback.get("adjustment_mode") != "pre_monte_carlo_memory_prior":
        errors.append("memory_prior_applied=true requiere adjustment_mode pre_monte_carlo_memory_prior")
    return {"ok": not errors, "errors": errors, "warnings": warnings}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", default="resultados.json")
    args = parser.parse_args()
    result = check_contract(args.path)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
