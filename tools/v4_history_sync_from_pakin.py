# -*- coding: utf-8 -*-
"""Sync canonical Melate/Revancha history CSVs from pakinja/pakin."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MAX_NUMBER = 56
SOURCE_REPO = "https://github.com/pakinja/pakin"
RAW_BASE = "https://raw.githubusercontent.com/pakinja/pakin/master"
GAME_SOURCES = {
    "revancha": ("Revancha.csv", "Historico-Revancha.csv"),
    "melate": ("Melate.csv", "Historico-Melate.csv"),
}
CANONICAL_HEADER = ["CONCURSO", "ID", "R1", "R2", "R3", "R4", "R5", "R6", "BOLSA", "FECHA", "PRIMOS", "REPETIDOS", "MEDIA"]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_int(value: Any) -> int | None:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None


def source_urls(game: str) -> list[str]:
    return [f"{RAW_BASE}/{name}" for name in GAME_SOURCES[game]]


def fetch_url(url: str, timeout: int = 20) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "fisicapapa-v43-history-sync"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8-sig", errors="replace")


def number_values(row: dict[str, str]) -> list[Any]:
    preferred = [row.get(f"R{i}") for i in range(1, 7)]
    if any(value not in (None, "") for value in preferred):
        return preferred
    keys = ("N1", "N2", "N3", "N4", "N5", "N6", "B1", "B2", "B3", "B4", "B5", "B6")
    values = [row.get(key) for key in keys if row.get(key) not in (None, "")]
    return values[:6]


def normalize_rows(raw_text: str) -> tuple[list[dict[str, Any]], int]:
    reader = csv.DictReader(raw_text.splitlines())
    rows: dict[int, dict[str, Any]] = {}
    dropped = 0
    for row in reader:
        draw = parse_int(row.get("CONCURSO") or row.get("SORTEO") or row.get("draw") or row.get("draw_id"))
        numbers = [parse_int(value) for value in number_values(row)]
        clean = [number for number in numbers if number is not None]
        if draw is None or len(clean) != 6 or len(set(clean)) != 6 or any(number < 1 or number > MAX_NUMBER for number in clean):
            dropped += 1
            continue
        sorted_numbers = sorted(clean)
        rows[draw] = {
            "CONCURSO": draw,
            "ID": row.get("ID") or row.get("id") or "",
            "R1": sorted_numbers[0],
            "R2": sorted_numbers[1],
            "R3": sorted_numbers[2],
            "R4": sorted_numbers[3],
            "R5": sorted_numbers[4],
            "R6": sorted_numbers[5],
            "BOLSA": row.get("BOLSA") or row.get("bolsa") or "",
            "FECHA": row.get("FECHA") or row.get("fecha") or row.get("Fecha") or "",
            "PRIMOS": row.get("PRIMOS") or "",
            "REPETIDOS": row.get("REPETIDOS") or "",
            "MEDIA": row.get("MEDIA") or round(sum(sorted_numbers) / 6, 1),
        }
    return [rows[key] for key in sorted(rows)], dropped


def serialize_csv(rows: list[dict[str, Any]]) -> str:
    output = [",".join(CANONICAL_HEADER)]
    for row in rows:
        output.append(",".join(str(row.get(key, "")) for key in CANONICAL_HEADER))
    return "\n".join(output) + "\n"


def write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", delete=False, dir=path.parent, suffix=".tmp") as handle:
        handle.write(text)
        temp_path = Path(handle.name)
    temp_path.replace(path)


def write_report(report: dict[str, Any], output: str = "v4_history_sync_report.json") -> None:
    (ROOT / output).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")


def build_report(game: str, attempted: list[str], warnings: list[str]) -> dict[str, Any]:
    return {
        "generated_at": utc_now(),
        "source_repo": SOURCE_REPO,
        "source_urls_attempted": attempted,
        "selected_source": None,
        "game": game,
        "rows_loaded": 0,
        "rows_valid": 0,
        "rows_dropped": 0,
        "latest_draw": None,
        "output_path": None,
        "checksum": None,
        "warnings": warnings,
    }


def sync_history(args: argparse.Namespace) -> dict[str, Any]:
    game = str(args.game).lower()
    attempted = source_urls(game)
    report = build_report(game, attempted, [])

    if args.mock_pakin_failure:
        report["warnings"].append("mock Pakin failure requested; local CSV left untouched.")
        return report

    candidates: list[dict[str, Any]] = []
    for url in attempted:
        try:
            raw = fetch_url(url)
            rows, dropped = normalize_rows(raw)
            candidates.append({"url": url, "raw_rows": max(len(raw.splitlines()) - 1, 0), "rows": rows, "dropped": dropped})
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            report["warnings"].append(f"Could not fetch {url}: {exc}")

    if not candidates:
        report["warnings"].append("No Pakin source could be loaded; local CSV left untouched.")
        return report

    selected = max(candidates, key=lambda item: ((item["rows"][-1]["CONCURSO"] if item["rows"] else -1), len(item["rows"])))
    rows = selected["rows"]
    report.update(
        {
            "selected_source": selected["url"],
            "rows_loaded": selected["raw_rows"],
            "rows_valid": len(rows),
            "rows_dropped": selected["dropped"],
            "latest_draw": rows[-1]["CONCURSO"] if rows else None,
            "output_path": str(Path(args.output) if args.output else ROOT / f"{game}.csv"),
        }
    )
    if not rows:
        report["warnings"].append("Selected Pakin source had no valid rows; local CSV left untouched.")
        return report

    csv_text = serialize_csv(rows)
    report["checksum"] = hashlib.sha256(csv_text.encode("utf-8")).hexdigest()
    output_path = Path(args.output) if args.output else ROOT / f"{game}.csv"
    if args.dry_run:
        report["warnings"].append("dry-run: output was validated but not written.")
        return report

    write_atomic(output_path, csv_text)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync canonical history CSVs from pakinja/pakin.")
    parser.add_argument("--game", choices=sorted(GAME_SOURCES), default="revancha")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output", default=None)
    parser.add_argument("--mock-pakin-failure", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = sync_history(args)
    write_report(report)
    status = "ok" if report.get("rows_valid") else "warning"
    print(f"v4 history sync {status}; game={report['game']} latest_draw={report.get('latest_draw')} output={report.get('output_path')}")
    if report["warnings"]:
        for warning in report["warnings"]:
            print(f"WARNING: {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
