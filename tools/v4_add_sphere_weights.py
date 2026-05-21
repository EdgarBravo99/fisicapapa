# -*- coding: utf-8 -*-
"""Add a sphere-weight record without editing JSON by hand."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MAX_NUMBER = 56
DRAW_SIZE = 6


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_int(value: Any) -> int | None:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None


def _parse_winning(value: str) -> list[int]:
    numbers = []
    for item in value.split(","):
        parsed = _parse_int(item)
        if parsed is None or not (1 <= parsed <= MAX_NUMBER):
            raise ValueError(f"Ganador invalido: {item}")
        if parsed in numbers:
            raise ValueError(f"Ganador duplicado: {parsed}")
        numbers.append(parsed)
    if len(numbers) != DRAW_SIZE:
        raise ValueError("Se requieren exactamente 6 ganadores unicos.")
    return sorted(numbers)


def _normalize_weights(raw: Any) -> dict[str, float]:
    if isinstance(raw, dict) and "weights_grams" in raw:
        raw = raw.get("weights_grams")
    if not isinstance(raw, dict):
        raise ValueError("Los pesos deben ser un objeto JSON o weights_grams.")
    weights: dict[str, float] = {}
    for key, value in raw.items():
        number = _parse_int(key)
        if number is None or not (1 <= number <= MAX_NUMBER):
            raise ValueError(f"Numero de esfera invalido: {key}")
        try:
            weight = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Peso invalido para esfera {number}: {value}") from exc
        weights[str(number)] = round(weight, 6)
    missing = [number for number in range(1, MAX_NUMBER + 1) if str(number) not in weights]
    if missing or len(weights) != MAX_NUMBER:
        raise ValueError(f"Se requieren exactamente 56 pesos. Faltantes: {missing[:8]}")
    return {str(number): weights[str(number)] for number in range(1, MAX_NUMBER + 1)}


def _parse_inline_weights(value: str) -> dict[str, float]:
    raw: dict[str, float] = {}
    for pair in value.split(","):
        if not pair.strip():
            continue
        if "=" not in pair:
            raise ValueError(f"Par de peso invalido: {pair}")
        key, weight = pair.split("=", 1)
        raw[key.strip()] = float(weight.strip())
    return _normalize_weights(raw)


def _load_weights(weights_file: str | None, inline: str | None) -> dict[str, float]:
    if bool(weights_file) == bool(inline):
        raise ValueError("Usa exactamente uno: --weights-file o --weights.")
    if weights_file:
        data = json.loads(Path(weights_file).read_text(encoding="utf-8"))
        return _normalize_weights(data)
    return _parse_inline_weights(inline or "")


def add_record(
    history_path: str | Path,
    draw_id: int,
    game_mode: str,
    winning: list[int],
    weights: dict[str, float],
    status: str,
    force: bool = False,
    observation: str = "",
) -> dict[str, Any]:
    path = Path(history_path)
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"records": []}
    records = data.get("records")
    if not isinstance(records, list):
        records = []
    key = (int(draw_id), str(game_mode))
    existing_index = next(
        (index for index, row in enumerate(records) if (int(row.get("draw_id") or -1), str(row.get("game_mode"))) == key),
        None,
    )
    record = {
        "draw_id": int(draw_id),
        "game_mode": str(game_mode),
        "winning_numbers": winning,
        "weights_grams": weights,
        "manual_observation": observation,
        "status": status,
        "recorded_at": _utc_now(),
    }
    if existing_index is not None and not force:
        raise ValueError(f"Ya existe registro para draw_id={draw_id}, game_mode={game_mode}. Usa --force para reemplazarlo.")
    if existing_index is not None:
        records[existing_index] = record
    else:
        records.append(record)
    records.sort(key=lambda row: (int(row.get("draw_id") or 0), str(row.get("game_mode") or "")))
    data["records"] = records
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="Add one sphere weight record to sphere_weight_history.json.")
    parser.add_argument("--history", default="sphere_weight_history.json")
    parser.add_argument("--draw", type=int, required=True)
    parser.add_argument("--game-mode", required=True)
    parser.add_argument("--winning", required=True)
    parser.add_argument("--weights-file")
    parser.add_argument("--weights")
    parser.add_argument("--status", default="observed_weight_record")
    parser.add_argument("--observation", default="")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    winning = _parse_winning(args.winning)
    weights = _load_weights(args.weights_file, args.weights)
    add_record(args.history, args.draw, args.game_mode, winning, weights, args.status, args.force, args.observation)
    print(f"Updated {args.history} with draw {args.draw} ({args.game_mode}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
