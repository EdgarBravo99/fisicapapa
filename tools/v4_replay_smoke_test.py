# -*- coding: utf-8 -*-
"""Smoke tests for the V4.3.2 replay lab safety guarantees."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.v4_historical_replay_lab import (  # noqa: E402
    file_sha256,
    patched_engine,
    replay_environment,
    run_replay_lab,
    select_targets,
    write_truncated_csv,
)
from tools.v4_legacy_snapshot_classifier import classify_snapshot_text  # noqa: E402
from v4_replay_memory import ENABLE_REPLAY_PRIOR, compute_replay_prior, default_replay_memory  # noqa: E402


class DummyEngine:
    def __init__(self) -> None:
        self.choose_mode = lambda: "original"
        self.choose_buffer = lambda: 150
        self.load_draws = lambda path: path


def _csv(path: Path) -> None:
    path.write_text(
        "sorteo,n1,n2,n3,n4,n5,n6,extra\n"
        "100,1,2,3,4,5,6,a\n"
        "101,7,8,9,10,11,12,b\n"
        "102,13,14,15,16,17,18,c\n"
        "103,19,20,21,22,23,24,d\n",
        encoding="utf-8",
    )


def run_smoke() -> dict:
    results: dict[str, object] = {}
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        csv_path = root / "historial.csv"
        _csv(csv_path)
        before = file_sha256(csv_path)
        temp_csv = root / "train.csv"
        info = write_truncated_csv(csv_path, 102, temp_csv)
        after = file_sha256(csv_path)
        train_text = temp_csv.read_text(encoding="utf-8")
        results["target_draw_not_in_train"] = "\n102," not in train_text
        results["future_draw_not_in_train"] = "\n103," not in train_text
        results["columns_preserved"] = train_text.splitlines()[0] == "sorteo,n1,n2,n3,n4,n5,n6,extra"
        results["csv_original_unchanged"] = before == after
        results["leakage_passed"] = bool(info["leakage_passed"])
        results["select_targets_conservative"] = select_targets(csv_path, start_draw=100, end_draw=103, max_targets=2, min_train_rows=2) == [102, 103]

        original_env = {key: os.environ.get(key) for key in ("MELATE_V4_MC_TOTAL", "MELATE_V4_MC_BATCH", "MELATE_V4_OOS_STEPS")}
        with replay_environment("replay_fast"):
            results["env_set_before_engine_load"] = os.environ.get("MELATE_V4_MC_TOTAL") == "100000"
        results["env_restored"] = all(os.environ.get(key) == value for key, value in original_env.items())

        engine = DummyEngine()
        original_choose_mode = engine.choose_mode
        original_cwd = Path.cwd()
        try:
            with patched_engine(engine, "revancha", 200, temp_csv):
                assert engine.choose_mode() == "revancha"
                raise RuntimeError("forced")
        except RuntimeError:
            pass
        results["monkeypatch_restored"] = engine.choose_mode is original_choose_mode
        results["cwd_restored"] = Path.cwd() == original_cwd

        smoke_cwd = Path.cwd()
        try:
            os.chdir(root)
            analysis = run_replay_lab(
                csv_path=csv_path,
                game_mode="revancha",
                start_draw=100,
                end_draw=103,
                max_targets=2,
                intensity="replay_fast",
                output_dir=root / "replay_archive",
                dry_run=True,
                buffer_size=200,
            )
        finally:
            os.chdir(smoke_cwd)
        results["dry_run_no_memory"] = analysis["dry_run"] and not (Path("v4_replay_memory.json").exists())

    hindsight_text = json.dumps({"hindsight_log": "Auditoría inversa del sorteo 4212\nCombinación real: 9 15 22 27 47 49"})
    classified = classify_snapshot_text(hindsight_text, commit_sha="c5d4a18594c4c4b70833f62b70db694964a2aa12")
    results["legacy_hindsight_blocked"] = classified["classification"] == "legacy_hindsight_snapshot" and not classified["eligible_for_prior"]

    def quality_record(index: int) -> dict:
        rows = {}
        for number in range(1, 57):
            appeared = number <= 6
            score = 95 - number if number <= 10 else 40 - (number % 20)
            rows[str(number)] = {"predicted_score": score, "appeared": appeared, "error": score - (100 if appeared else 0)}
        return {"record_type": "historical_replay", "leakage_passed": True, "prediction_draw": str(index), "target_draw": str(index + 1), "number_score_errors": rows}

    memory = default_replay_memory()
    memory["records"] = [quality_record(i) for i in range(30)]
    prior = compute_replay_prior(memory)
    memory_60 = default_replay_memory()
    memory_60["records"] = [quality_record(i) for i in range(60)]
    prior_60 = compute_replay_prior(memory_60)
    results["replay_prior_disabled_by_default"] = ENABLE_REPLAY_PRIOR is False and not prior["applied"]
    results["replay_prior_threshold_30"] = prior["eligible"] and prior["max_number_adjustment"] == 0.02
    results["replay_prior_threshold_60"] = prior_60["eligible"] and prior_60["max_number_adjustment"] == 0.03
    forbidden_calibrator = "feedback_" + "calibrator.py"
    forbidden_runner = "local_cruncher_v4_" + "3.py"
    results["no_second_runner_contract"] = not (ROOT / forbidden_calibrator).exists() and not (ROOT / forbidden_runner).exists()
    return results


if __name__ == "__main__":
    output = run_smoke()
    print(json.dumps(output, indent=2, ensure_ascii=False))
    failed = [key for key, value in output.items() if value is not True]
    if failed:
        raise SystemExit(f"Smoke failed: {failed}")
