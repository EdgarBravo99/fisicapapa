# -*- coding: utf-8 -*-
"""Smoke tests for V4.3 Hybrid Composition Engine outputs and guardrails."""

from __future__ import annotations

import json
import subprocess
import tempfile
import csv
from argparse import Namespace
from pathlib import Path

from v4_hybrid_composition_engine import build_slate
from v4_history_sync_from_pakin import sync_history
from v4_predraw_snapshot import build_snapshot, write_snapshot
from v4_visual_pattern_features import build_visual_features
from v4_winner_composition_audit import read_revancha_csv


ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_FILES = [
    "local_cruncher_v4_deep_stacking.py",
    "local_cruncher_v4_2_calibrated.py",
    "v4_replay_memory.json",
]
FORBIDDEN_WORDS = [
    "probability",
    "probabilidad",
    "guarantee",
    "garantia",
    "garantía",
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
    assert isinstance(ticket.get("reasons"), dict) and ticket["reasons"], "ticket must include reasons"
    assert isinstance(ticket.get("composition"), dict) and ticket["composition"], "ticket must include composition"
    assert ticket["composition"].get("sum_band"), "ticket must include sum_band"
    harmonic = ticket["composition"].get("harmonic_coherence")
    assert isinstance(harmonic, dict) and harmonic, "ticket must include harmonic_coherence"
    for number in numbers:
        roles = ticket["roles"].get(str(number))
        assert isinstance(roles, list) and roles, f"number {number} missing roles"
        reasons = ticket["reasons"].get(str(number))
        assert isinstance(reasons, list) and reasons, f"number {number} missing reasons"


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
    csv_latest_draw = draws[-1]["draw_id"]

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
    assert visual.get("latest_draw") == csv_latest_draw
    assert visual.get("pair_lag_mode") in {"promoter", "support_only", "disabled_by_validation"}
    zone_activation = visual.get("zone_activation")
    assert isinstance(zone_activation, dict) and zone_activation, "zone activation metrics missing"
    for row in zone_activation.values():
        assert isinstance(row, dict), "zone activation must expose separate metrics"
        assert "unique_activation" in row and "hit_density" in row

    audit = _load("v4_winner_composition_audit.json")
    audit_blocks = set(audit.get("composition_profile", {}).get("activated_blocks", {}).get("active_blocks", []))
    visual_blocks = {
        name
        for name, row in zone_activation.items()
        if float(row.get("unique_activation", 0.0) or 0.0) >= 0.40
    }
    assert audit_blocks == visual_blocks, f"audit/visual active blocks differ: {audit_blocks} vs {visual_blocks}"

    pair_audit_path = ROOT / "v4_pair_companion_audit.json"
    if pair_audit_path.exists():
        pair_audit = _load("v4_pair_companion_audit.json")
        assert isinstance(pair_audit.get("top_co_travel_pairs"), list), "pair audit top pairs missing"
        assert pair_audit.get("latest_draw") == csv_latest_draw

    validation = slate.get("validation_summary", {})
    assert isinstance(validation.get("slate_sum_distribution"), dict), "slate sum distribution missing"
    assert isinstance(validation.get("sum_band_percentiles"), dict), "sum band percentiles missing"

    ticket_types = {ticket.get("ticket_type") for ticket in tickets}
    pair_lag_mode = visual.get("pair_lag_mode")
    if pair_lag_mode == "promoter":
        assert "pair_lag_bridge" in ticket_types
    elif pair_lag_mode == "support_only":
        assert "pair_lag_bridge" not in ticket_types
        assert "pair_lag_support" in ticket_types
    else:
        assert "pair_lag_bridge" not in ticket_types
        assert "visual_support" in ticket_types

    with tempfile.TemporaryDirectory() as tmp:
        invalid = Path(tmp) / "bad_resultados.json"
        invalid.write_text("{\n<<<<<<< bad\n", encoding="utf-8")
        invalid_visual = build_visual_features(ROOT / "revancha.csv", invalid)
        invalid_slate = build_slate(ROOT / "revancha.csv", ROOT / "v4_winner_composition_audit.json", ROOT / "v4_visual_pattern_output.json", invalid)
        assert invalid_visual["mode"] == "csv_visual_composition_only"
        assert invalid_slate["source_policy"]["fallback_mode"] == "csv_visual_composition_only"
        assert 4 <= len(invalid_slate["slate"]) <= 6

    overlay = ROOT / "visual_exports" / "revancha_visual_candidate_overlay.csv"
    if overlay.exists():
        with overlay.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                assert row.get("row_type") == "candidate", "candidate overlay row_type must be candidate"
                assert row.get("synthetic") == "true", "candidate overlay rows must be synthetic"
        assert "visual_exports" not in str(ROOT / "revancha.csv"), "canonical history must not point to visual_exports"

    with tempfile.TemporaryDirectory() as tmp:
        snapshot = build_snapshot(ROOT / "v4_hybrid_composition_slate.json", target_draw=999999)
        first = write_snapshot(snapshot, force=True)
        try:
            write_snapshot(snapshot, force=False)
            raise AssertionError("pre-draw snapshot must not overwrite by default")
        except FileExistsError:
            pass
        first.unlink(missing_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        test_csv = Path(tmp) / "revancha_sync_test.csv"
        test_csv.write_text("CONCURSO,ID,R1,R2,R3,R4,R5,R6\n1,1,1,2,3,4,5,5\n", encoding="utf-8")
        report = sync_history(Namespace(game="revancha", output=str(test_csv), dry_run=False, mock_pakin_failure=True))
        assert report["warnings"], "mock Pakin failure should report warning"
        assert test_csv.read_text(encoding="utf-8").count("5,5") == 1, "mock failure must not overwrite local CSV"

    replay_memory_json = ROOT / "v4_replay_memory.json"
    if replay_memory_json.exists():
        with replay_memory_json.open("r", encoding="utf-8") as handle:
            json.load(handle)
    replay_memory_py = ROOT / "v4_replay_memory.py"
    if replay_memory_py.exists():
        text = replay_memory_py.read_text(encoding="utf-8", errors="replace")
        assert "ENABLE_REPLAY_PRIOR = False" in text
    if (ROOT / "resultados.json").exists():
        text = (ROOT / "resultados.json").read_text(encoding="utf-8", errors="replace")
        assert '"score_kind": "v4_2_deep_stacking_meta_score"' in text

    _assert_no_forbidden_file_diff()
    print("v4 hybrid composition smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
