# -*- coding: utf-8 -*-
"""Classify old resultados.json snapshots without making them prior-eligible."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
HINDSIGHT_PATTERNS = [
    "hindsight_log",
    "auditoria inversa",
    "combinacion real",
    "resultado=rastreado",
    "resultado=no_rastreado",
    "combinacion ganadora",
    "numeros reales",
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text)
    plain = "".join(char for char in decomposed if unicodedata.category(char) != "Mn")
    return plain.lower()


def _run_git(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=False, encoding="utf-8")


def _parse_json_text(text: str) -> tuple[dict[str, Any] | None, str | None]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        return None, f"json_corrupt: {exc}"
    if not isinstance(data, dict):
        return None, "json_not_object"
    return data, None


def _parse_int(value: Any) -> int | None:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None


def _combo_numbers(combo: Any) -> list[int]:
    raw = combo if isinstance(combo, list) else combo.get("numbers") or combo.get("nums") or combo.get("combo") or []
    numbers = []
    for value in raw:
        parsed = _parse_int(value)
        if parsed is not None and 1 <= parsed <= 56:
            numbers.append(parsed)
    numbers = sorted(set(numbers))
    return numbers if len(numbers) == 6 else []


def _top_combinations(data: dict[str, Any]) -> list[list[int]]:
    source = data.get("top_combinations") or data.get("generator_pool") or []
    if not isinstance(source, list):
        return []
    return [numbers for numbers in (_combo_numbers(combo) for combo in source[:10]) if numbers]


def _infer_draw(data: dict[str, Any], text: str) -> str | None:
    candidates = [
        data.get("prediction_draw"),
        data.get("target_draw"),
        data.get("historical_forgetting", {}).get("buffer_last_draw") if isinstance(data.get("historical_forgetting"), dict) else None,
    ]
    for value in candidates:
        parsed = _parse_int(value)
        if parsed is not None:
            return str(parsed)
    match = re.search(r"sorteo\s+(\d{3,6})", _normalize(text))
    return match.group(1) if match else None


def _actual_numbers(text: str) -> list[int]:
    normalized = _normalize(text)
    match = re.search(r"combinacion real:\s*([0-9,\s]+)", normalized)
    if not match:
        return []
    numbers = [_parse_int(part) for part in re.split(r"[\s,]+", match.group(1).strip())]
    clean = sorted({number for number in numbers if number is not None and 1 <= number <= 56})
    return clean if len(clean) == 6 else []


def classify_snapshot_text(
    text: str,
    *,
    path: str | None = None,
    commit_sha: str | None = None,
) -> dict[str, Any]:
    data, error = _parse_json_text(text)
    if error:
        return {
            "commit_sha": commit_sha,
            "filename": Path(path).name if path else None,
            "path": path,
            "detected_draw": None,
            "classification": "corrupt_snapshot",
            "eligible_for_prior": False,
            "reason": error,
            "extracted_actual_numbers": [],
            "extracted_top_combinations": [],
            "snapshot_source": "unknown",
            "safety_flags": ["corrupt_json"],
        }
    assert data is not None
    normalized = _normalize(text)
    matched = [pattern for pattern in HINDSIGHT_PATTERNS if pattern in normalized]
    meta = data.get("snapshot_metadata") if isinstance(data.get("snapshot_metadata"), dict) else {}
    has_prediction_shape = bool(data.get("top_combinations") or data.get("generator_pool") or data.get("number_scores"))
    if matched:
        classification = "legacy_hindsight_snapshot"
        reason = "contains " + ", ".join(matched[:3])
        flags = ["hindsight_detected", *matched]
    elif has_prediction_shape and data.get("model_version"):
        classification = "clean_prediction_snapshot"
        reason = "prediction-shaped snapshot without hindsight markers"
        flags = []
    else:
        classification = "legacy_unknown_snapshot"
        reason = "missing enough V4 prediction fields; diagnostic only"
        flags = ["unknown_legacy_shape"]
    return {
        "commit_sha": commit_sha or meta.get("commit_sha"),
        "filename": Path(path).name if path else None,
        "path": path,
        "detected_draw": _infer_draw(data, text),
        "classification": classification,
        "eligible_for_prior": classification == "clean_prediction_snapshot",
        "reason": reason,
        "extracted_actual_numbers": _actual_numbers(text),
        "extracted_top_combinations": _top_combinations(data),
        "snapshot_source": meta.get("source") or ("git_history" if commit_sha else "local_archive"),
        "safety_flags": flags,
    }


def _git_commits(limit: int) -> list[str]:
    result = _run_git(["log", "--format=%H", "--", "resultados.json"])
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()][:limit]


def _git_show(commit_sha: str) -> str | None:
    result = _run_git(["show", f"{commit_sha}:resultados.json"])
    if result.returncode != 0:
        return None
    return result.stdout


def classify_snapshots(
    archive_dir: str | Path = "resultados_archive",
    git_limit: int = 100,
    output: str | Path = "v4_legacy_snapshot_report.json",
    commit: str | None = None,
) -> dict[str, Any]:
    archive_path = ROOT / archive_dir
    rows: list[dict[str, Any]] = []
    if archive_path.exists():
        for path in sorted(archive_path.glob("*.json")):
            if path.name == "index.json":
                continue
            rows.append(classify_snapshot_text(path.read_text(encoding="utf-8", errors="replace"), path=str(path.relative_to(ROOT))))
    commits = [commit] if commit else _git_commits(git_limit)
    for commit_sha in commits:
        text = _git_show(commit_sha)
        if text is None:
            rows.append({
                "commit_sha": commit_sha,
                "classification": "corrupt_snapshot",
                "eligible_for_prior": False,
                "reason": "git show failed for resultados.json",
                "safety_flags": ["git_show_failed"],
            })
            continue
        rows.append(classify_snapshot_text(text, commit_sha=commit_sha))
    report = {
        "version": "V4.3.2-legacy-snapshot-classifier",
        "generated_at": _utc_now(),
        "summary": {
            "total": len(rows),
            "legacy_hindsight": len([row for row in rows if row.get("classification") == "legacy_hindsight_snapshot"]),
            "eligible_for_prior": len([row for row in rows if row.get("eligible_for_prior")]),
        },
        "snapshots": rows,
    }
    Path(output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Clasifica snapshots legacy/hindsight de resultados.json.")
    parser.add_argument("--archive-dir", default="resultados_archive")
    parser.add_argument("--git-limit", type=int, default=100)
    parser.add_argument("--commit")
    parser.add_argument("--output", default="v4_legacy_snapshot_report.json")
    args = parser.parse_args()
    report = classify_snapshots(args.archive_dir, args.git_limit, args.output, args.commit)
    print(json.dumps(report.get("summary", {}), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
