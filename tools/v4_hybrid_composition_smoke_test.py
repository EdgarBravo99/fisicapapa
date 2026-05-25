# -*- coding: utf-8 -*-
"""Smoke tests for V4.3 Hybrid Composition Engine outputs and guardrails."""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

from v4_hybrid_composition_engine import build_slate
from v4_visual_pattern_features import build_visual_features
from v4_winner_composition_audit import read_revancha_csv


ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_FILES = [
    "local_cruncher_v4_deep_stacking.py",
    "local_cruncher_v4_2_calibrated.py",
    "v4_replay_memory.json",
]
FORBIDDEN_WORDS = [
    "guaranteed",
    "winning chance",
    "probability_model",
    "winning_model",
]


def _load(path: str) -> dict:
    with (ROOT / path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _assert_ticket(ticket: dict) -> None:
    numbers = ticket.get("numbers")
    assert isinstance(numbers, list), "ticket numbers must be a list"
    assert len(numbers) == 6, f"ticket must have 6 numbers: {numbers}"
    assert len(set(numbers)) == 6, f"ticket numbers must be unique: {numbers}"
    assert all(isinstance(number, int) and 1 <= number <= 56 for number in numbers), numbers
    assert isinstance(ticket.get("roles"), dict) and ticket["roles"], "ticket must include roles"
    assert isinstance(ticket.get("composition"), dict) and ticket["composition"], "ticket must include composition"
    for number in numbers:
        roles = ticket["roles"].get(str(number))
        assert isinstance(roles, list) and roles, f"number {number} missing roles"


def _assert_no_forbidden_language(payload: dict) -> None:
    text = json.dumps(payload, ensure_ascii=False).lower()
    for word in FORBIDDEN_WORDS:
        assert word not in text, f"forbidden language found: {word}"


def _assert_no_forbidden_file_diff() -> None:
    for path in FORBIDDEN_FILES:
        result = subprocess.run(["git", "diff", "--", path], cwd=ROOT, text=True, capture_output=True, check=False)
        assert result.returncode == 0, result.stderr
        assert result.stdout == "", f"forbidden file modified: {path}"


def main() -> int:
    draws = read_revancha_csv(ROOT / "revancha.csv")
    assert draws, "revancha.csv must parse"

    for path in (
        "v4_winner_composition_audit.json",
        "v4_visual_pattern_output.json",
        "v4_hybrid_composition_slate.json",
    ):
        data = _load(path)
        assert isinstance(data, dict), f"{path} must parse as object"
        _assert_no_forbidden_language(data)

    slate = _load("v4_hybrid_composition_slate.json")
    tickets = slate.get("slate")
    assert isinstance(tickets, list), "slate must be a list"
    assert 4 <= len(tickets) <= 6, f"slate must contain 4-6 tickets, got {len(tickets)}"
    assert slate.get("production_status") == "review_default"
    for ticket in tickets:
        _assert_ticket(ticket)

    visual = _load("v4_visual_pattern_output.json")
    assert visual.get("mode") in {"csv_visual_composition_only", "csv_plus_v42_signal"}

    with tempfile.TemporaryDirectory() as tmp:
        invalid = Path(tmp) / "bad_resultados.json"
        invalid.write_text("{\n<<<<<<< bad\n", encoding="utf-8")
        invalid_visual = build_visual_features(ROOT / "revancha.csv", invalid)
        invalid_slate = build_slate(ROOT / "revancha.csv", ROOT / "v4_winner_composition_audit.json", ROOT / "v4_visual_pattern_output.json", invalid)
        assert invalid_visual["mode"] == "csv_visual_composition_only"
        assert invalid_slate["source_policy"]["fallback_mode"] == "csv_visual_composition_only"
        assert 4 <= len(invalid_slate["slate"]) <= 6

    replay_memory = ROOT / "v4_replay_memory.py"
    if replay_memory.exists():
        text = replay_memory.read_text(encoding="utf-8", errors="replace")
        assert "ENABLE_REPLAY_PRIOR = False" in text
    if (ROOT / "resultados.json").exists():
        text = (ROOT / "resultados.json").read_text(encoding="utf-8", errors="replace")
        assert '"score_kind": "v4_2_deep_stacking_meta_score"' in text

    _assert_no_forbidden_file_diff()
    print("v4 hybrid composition smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
