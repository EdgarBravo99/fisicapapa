# -*- coding: utf-8 -*-
"""Shared V4.4 history helpers for Revancha composition tooling."""

from __future__ import annotations

import csv
import hashlib
import json
import statistics
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MAX_NUMBER = 56
DRAW_SIZE = 6
PRODUCTION_STATUS = "review_default"
BLOCK_ORDER = ["1_10", "11_20", "21_30", "31_40", "41_56"]
BLOCK_RANGES = {
    "1_10": range(1, 11),
    "11_20": range(11, 21),
    "21_30": range(21, 31),
    "31_40": range(31, 41),
    "41_56": range(41, 57),
}
SUM_BAND_ES = {
    "low_tail": "cola baja",
    "historical_core": "núcleo histórico",
    "upper_core": "núcleo alto",
    "high_tail": "cola alta",
    "extreme_high": "extremo alto",
}
VISUAL_LABELS_ES = {
    "0-0-1-0-1": "Activación media-alta: presencia en 21_30 y 41_56",
    "0-1-1-0-1": "Puente 11_20 + 21_30 + 41_56",
    "0-1-0-0-1": "Puente bajo-medio con bloque alto",
    "1-0-1-0-1": "Triángulo 1_10 + 21_30 + 41_56",
    "1-1-1-0-0": "Escalera baja-media hasta 21_30",
    "0-1-1-1-0": "Centro extendido 11_20 + 21_30 + 31_40",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def file_sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def parse_int(value: Any) -> int | None:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None


def normalize_key(key: str | None) -> str:
    return str(key or "").strip().lower().replace(" ", "_")


def canonical_row_values(row: dict[str, Any]) -> tuple[int | None, list[int]]:
    lowered = {normalize_key(key): value for key, value in row.items()}
    draw = parse_int(
        lowered.get("sorteo")
        or lowered.get("concurso")
        or lowered.get("draw")
        or lowered.get("draw_id")
        or lowered.get("id_sorteo")
    )
    values: list[Any] = []
    for prefix in ("n", "r", "b"):
        values = [lowered.get(f"{prefix}{index}") for index in range(1, 7)]
        if any(value not in (None, "") for value in values):
            break
    numbers = [number for number in (parse_int(value) for value in values) if number is not None]
    if len(numbers) != DRAW_SIZE:
        return draw, []
    return draw, sorted(numbers)


def validate_draw(draw: int | None, numbers: list[int]) -> str | None:
    if draw is None:
        return "missing_draw_id"
    if len(numbers) != DRAW_SIZE:
        return "expected_6_numbers"
    if len(set(numbers)) != DRAW_SIZE:
        return "duplicated_number_in_draw"
    if any(number < 1 or number > MAX_NUMBER for number in numbers):
        return "number_out_of_range"
    return None


def read_history_csv(path: str | Path = "revancha.csv") -> list[dict[str, Any]]:
    csv_path = Path(path)
    rows: dict[int, dict[str, Any]] = {}
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for raw in reader:
            draw, numbers = canonical_row_values(raw)
            if validate_draw(draw, numbers) is not None:
                continue
            rows[int(draw)] = {"draw_id": int(draw), "numbers": numbers, "raw": raw}
    return [rows[key] for key in sorted(rows)]


def write_canonical_csv(path: str | Path, draws: list[dict[str, Any]]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["sorteo", "n1", "n2", "n3", "n4", "n5", "n6"])
        for draw in sorted(draws, key=lambda item: item["draw_id"]):
            writer.writerow([draw["draw_id"], *sorted(draw["numbers"])])


def write_json(path: str | Path, data: dict[str, Any]) -> None:
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def block_name(number: int) -> str:
    for name, values in BLOCK_RANGES.items():
        if number in values:
            return name
    return "unknown"


def block_counts(numbers: list[int]) -> dict[str, int]:
    number_set = set(numbers)
    return {name: sum(1 for number in values if number in number_set) for name, values in BLOCK_RANGES.items()}


def block_vector(numbers: list[int]) -> list[int]:
    counts = block_counts(numbers)
    return [counts[name] for name in BLOCK_ORDER]


def signature(values: list[int]) -> str:
    return "-".join(str(int(value)) for value in values)


def block_signature(numbers: list[int]) -> str:
    return signature(block_vector(numbers))


def presence_vector(numbers: list[int]) -> list[int]:
    return [1 if value > 0 else 0 for value in block_vector(numbers)]


def presence_signature(numbers: list[int]) -> str:
    return signature(presence_vector(numbers))


def visual_structure_label_es(presence: str) -> str:
    return VISUAL_LABELS_ES.get(presence, f"Presencia visual {presence}")


def sum_band(total: int) -> str:
    if total < 100:
        return "low_tail"
    if total <= 140:
        return "historical_core"
    if total <= 170:
        return "upper_core"
    if total <= 200:
        return "high_tail"
    return "extreme_high"


def parity_label(numbers: list[int]) -> str:
    even = sum(1 for number in numbers if number % 2 == 0)
    odd = len(numbers) - even
    return f"{even}_even_{odd}_odd"


def safe_avg(values: list[float]) -> float:
    return round(sum(values) / len(values), 6) if values else 0.0


def safe_median(values: list[float]) -> float:
    return round(float(statistics.median(values)), 6) if values else 0.0


def distribution(values: list[Any]) -> dict[str, int]:
    return dict(Counter(str(value) for value in values).most_common())


def top_counter_rows(counter: Counter[Any], limit: int = 20) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key, count in counter.most_common(limit):
        if isinstance(key, tuple):
            rows.append({"pair": list(key), "count": count})
        else:
            rows.append({"value": key, "count": count})
    return rows


def sequence_gaps(draw_ids: list[int]) -> list[dict[str, int]]:
    gaps: list[dict[str, int]] = []
    for previous, current in zip(draw_ids, draw_ids[1:]):
        if current != previous + 1:
            gaps.append({"after": previous, "before": current, "missing_count": current - previous - 1})
    return gaps
