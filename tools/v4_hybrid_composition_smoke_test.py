# -*- coding: utf-8 -*-
"""Smoke tests for V4.3 Hybrid Composition Engine outputs and guardrails."""

from __future__ import annotations

import hashlib
import itertools
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
FORBIDDEN_SPANISH_USER_FIELDS = [
    "probabilidad garantizada",
    "garantia de ganar",
    "garantía de ganar",
    "chance de ganar",
    "seguro",
    "certeza de resultado",
]
FORBIDDEN_ENGLISH_BOILERPLATE = [
    "Review-default composition slate",
    "Outcome-neutral review layer",
    "Composed by V4.3 harmonic roles",
    "Fallback V4.3 harmonic composition",
    "Sum band guardrail",
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
    assert ticket["composition"].get("sum_band_es"), "ticket must include sum_band_es"
    assert ticket["composition"].get("block_signature"), "ticket must include block_signature"
    assert ticket["composition"].get("block_presence_signature"), "ticket must include block_presence_signature"
    assert ticket["composition"].get("visual_structure_label_es"), "ticket must include visual_structure_label_es"
    harmonic = ticket["composition"].get("harmonic_coherence")
    assert isinstance(harmonic, dict) and harmonic, "ticket must include harmonic_coherence"
    assert isinstance(harmonic.get("notes_es"), list), "ticket harmonic notes_es missing"
    explanation_es = ticket.get("explanation_es")
    assert isinstance(explanation_es, dict) and explanation_es, "ticket must include explanation_es"
    assert isinstance(explanation_es.get("why_this_ticket"), list) and explanation_es["why_this_ticket"], "explanation_es why missing"
    assert ticket.get("reason_es"), "ticket must include reason_es"
    assert isinstance(ticket.get("risk_notes_es"), list) and ticket["risk_notes_es"], "ticket must include risk_notes_es"
    assert ticket.get("thesis_es"), "ticket must include thesis_es"
    assert ticket.get("decision_summary_es"), "ticket must include decision_summary_es"
    assert ticket.get("structure_summary_es"), "ticket must include structure_summary_es"
    assert isinstance(ticket.get("reasons_es"), dict) and ticket["reasons_es"], "ticket must include reasons_es"
    for number in numbers:
        roles = ticket["roles"].get(str(number))
        assert isinstance(roles, list) and roles, f"number {number} missing roles"
        reasons = ticket["reasons"].get(str(number))
        assert isinstance(reasons, list) and reasons, f"number {number} missing reasons"
        reasons_es = ticket["reasons_es"].get(str(number))
        assert isinstance(reasons_es, list) and reasons_es, f"number {number} missing Spanish reasons"


def _spanish_field_text(payload: dict) -> str:
    chunks: list[str] = []

    def visit(value, key: str = "") -> None:
        if isinstance(value, dict):
            for child_key, child_value in value.items():
                visit(child_value, str(child_key))
        elif isinstance(value, list):
            for item in value:
                visit(item, key)
        elif key.endswith("_es") or key == "explanation_es":
            chunks.append(str(value))

    visit(payload)
    return "\n".join(chunks)


def _assert_spanish_contract_language(payload: dict) -> None:
    text = _spanish_field_text(payload)
    lower = text.lower()
    for phrase in FORBIDDEN_SPANISH_USER_FIELDS:
        assert phrase not in lower, f"forbidden Spanish user-facing language found: {phrase}"
    for phrase in FORBIDDEN_ENGLISH_BOILERPLATE:
        assert phrase not in text, f"English boilerplate leaked into Spanish contract: {phrase}"


def _assert_no_forbidden_language(payload: dict) -> None:
    text = json.dumps(payload, ensure_ascii=False).lower()
    for word in FORBIDDEN_WORDS:
        assert word not in text, f"forbidden language found: {word}"


def _assert_no_forbidden_file_diff() -> None:
    for path in FORBIDDEN_FILES:
        result = subprocess.run(["git", "diff", "--", path], cwd=ROOT, text=True, capture_output=True, check=False)
        assert result.returncode == 0, result.stderr
        assert result.stdout == "", f"forbidden file modified: {path}"


def _assert_v44_ticket(ticket: dict) -> None:
    assert ticket.get("production_status") == "review_default", "V4.4 ticket production_status must be review_default"
    numbers = ticket.get("numbers")
    assert isinstance(numbers, list) and len(numbers) == 6, f"V4.4 ticket must have 6 numbers: {numbers}"
    assert len(set(numbers)) == 6, f"V4.4 ticket has duplicates: {numbers}"
    assert all(isinstance(number, int) and 1 <= number <= 56 for number in numbers), numbers
    signals = ticket.get("signals")
    assert isinstance(signals, dict) and signals, "V4.4 ticket signals missing"
    for number in numbers:
        active = signals.get(str(number))
        assert isinstance(active, list) and active, f"number {number} lacks active signals"
    composition = ticket.get("composition")
    assert isinstance(composition, dict), "V4.4 ticket composition missing"
    for field in (
        "parity",
        "sum",
        "sum_band",
        "sum_band_es",
        "block_signature",
        "block_presence_signature",
        "visual_structure_label_es",
        "immediate_overlap_previous_draw",
        "immediate_overlap_label_es",
        "immediate_overlap_reason_es",
        "pair_companion_count",
        "pair_lag_relation_count",
        "matches_winner_profile",
        "matches_recent_profile",
    ):
        assert field in composition, f"V4.4 composition missing {field}"
    assert isinstance(ticket.get("construction_trace_es"), list) and ticket["construction_trace_es"], "construction_trace_es missing"
    assert ticket.get("reason_es"), "reason_es missing"
    assert ticket.get("thesis_es"), "thesis_es missing"
    assert isinstance(ticket.get("risk_notes_es"), list) and ticket["risk_notes_es"], "risk_notes_es missing"


def _assert_v44_outputs() -> None:
    required = [
        "v4_history_matrix.json",
        "v4_gap_echo_output.json",
        "v4_signature_history.json",
        "v4_pair_lag_signals.json",
        "v4_block_completion_signals.json",
        "v4_winner_profile.json",
        "v4_recent_composition_profile.json",
        "v4_combination_slate.json",
    ]
    if not (ROOT / "v4_combination_slate.json").exists():
        return
    for path in required:
        assert (ROOT / path).exists(), f"missing V4.4 output: {path}"
        data = _load(path)
        assert data.get("production_status") == "review_default", f"{path} production_status must be review_default"
        _assert_no_forbidden_language(data)

    recent = _load("v4_recent_composition_profile.json")
    winner = _load("v4_winner_profile.json")
    slate = _load("v4_combination_slate.json")
    assert recent.get("window") == 30, "recent composition window must be 30"
    assert recent.get("latest_draw") == slate.get("latest_draw"), "latest_draw mismatch between recent profile and slate"
    assert recent.get("source_sha256") == winner.get("source_sha256"), "source sha mismatch"
    assert recent.get("source_sha256") == hashlib.sha256((ROOT / "revancha.csv").read_bytes()).hexdigest()
    assert recent.get("sum_profile", {}).get("sum_band_distribution"), "recent sum distribution missing"
    assert recent.get("parity_profile", {}).get("parity_distribution"), "recent parity distribution missing"
    assert recent.get("presence_signature_profile", {}).get("dominant_presence_signature"), "recent dominant presence missing"
    assert isinstance(recent.get("pair_companion_profile", {}).get("top_pair_companions"), list), "top_pair_companions missing"
    assert isinstance(recent.get("number_frequency_recent_30"), dict), "number_frequency_recent_30 missing"
    assert isinstance(slate.get("recent_composition_profile_used"), dict), "recent_composition_profile_used missing"
    assert isinstance(slate.get("slate_structure_summary"), dict), "slate_structure_summary missing"
    tickets = slate.get("tickets")
    assert isinstance(tickets, list) and tickets, "V4.4 tickets missing"
    assert len(tickets) == 5, f"V4.4 constructor should produce exactly 5 tickets, got {len(tickets)}"
    for ticket in tickets:
        _assert_v44_ticket(ticket)
    for left, right in itertools.combinations(tickets, 2):
        overlap = len(set(left["numbers"]) & set(right["numbers"]))
        if overlap > 3:
            trace = " ".join(left.get("construction_trace_es", []) + right.get("construction_trace_es", [])).lower()
            assert "relaj" in trace or "compartidos" in trace, f"ticket overlap {overlap} lacks justification"
    _assert_spanish_contract_language(slate)


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
    assert tickets, "slate must not be empty"
    assert 4 <= len(tickets) <= 6, f"slate must contain 4-6 tickets, got {len(tickets)}"
    assert slate.get("production_status") == "review_default"
    assert slate.get("visual_structure_contract_version"), "visual structure contract missing"
    assert isinstance(slate.get("slate_structure_summary"), dict), "slate structure summary missing"
    assert slate["slate_structure_summary"].get("dominant_presence_signature"), "dominant presence signature missing"
    assert slate["slate_structure_summary"].get("summary_es"), "slate summary_es missing"
    _assert_spanish_contract_language(slate)
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
    assert validation.get("visual_structure_contract_version"), "validation structure contract missing"

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
    _assert_v44_outputs()
    print("v4 hybrid composition smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
