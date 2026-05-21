# -*- coding: utf-8 -*-
"""Local read-only audit state for Fisicapapa outputs and repo hygiene."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VERSION = "V4.4-local-audit-state"
ROOT = Path(__file__).resolve().parents[1]

CRITICAL_FILES = (
    "AGENTS.md",
    "README.md",
    "index.html",
    "local_cruncher_v4_2_calibrated.py",
    "local_cruncher_v4_deep_stacking.py",
    "resultados.json",
    "v4_replay_memory.py",
    "v4-decision-audit-panel.js",
)

GENERATED_OUTPUTS = (
    "v4_diversity_output.json",
    "v4_candidate_pool_audit.json",
    "v4_baseline_benchmark.json",
    "v4_physics_regime_analysis.json",
    "v4_physics_regime_timeline.json",
    "v4_replay_qualification.json",
    "v4_decision_slate.json",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _git(args: list[str]) -> tuple[int, str]:
    result = subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True, check=False)
    return result.returncode, result.stdout.strip() or result.stderr.strip()


def _load_json(path: str) -> dict[str, Any] | None:
    file_path = ROOT / path
    if not file_path.exists():
        return None
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _git_state() -> dict[str, Any]:
    _, branch = _git(["branch", "--show-current"])
    _, status = _git(["status", "--porcelain"])
    lines = [line for line in status.splitlines() if line.strip()]
    conflict_prefixes = {"UU", "AA", "DD", "AU", "UA", "DU", "UD"}
    conflicts = [line for line in lines if line[:2] in conflict_prefixes]
    return {
        "branch": branch or "unknown",
        "has_uncommitted_changes": bool(lines),
        "conflict_detected": bool(conflicts),
        "status_entries": lines,
        "conflicts": conflicts,
    }


def _file_map(paths: tuple[str, ...]) -> dict[str, dict[str, Any]]:
    output = {}
    for path in paths:
        file_path = ROOT / path
        output[path] = {"exists": file_path.exists(), "size_bytes": file_path.stat().st_size if file_path.exists() else 0}
    return output


def _weight_records_count() -> int:
    data = _load_json("sphere_weight_history.json")
    records = data.get("records") if data else []
    return len(records) if isinstance(records, list) else 0


def _physics_state() -> dict[str, Any]:
    timeline = _load_json("v4_physics_regime_timeline.json") or {}
    summary = timeline.get("event_summary") or {}
    return {
        "weight_records_count": _weight_records_count(),
        "timeline_records_count": timeline.get("records_count") or 0,
        "can_estimate_periodicity": bool(summary.get("can_estimate_periodicity")),
        "reason": summary.get("reason") or "timeline missing or not generated",
    }


def _replay_state() -> dict[str, Any]:
    gate = _load_json("v4_replay_qualification.json") or {}
    return {
        "can_influence_future_prior": bool(gate.get("can_influence_future_prior")),
        "eligible_for_future_experiment": bool(gate.get("eligible_for_future_experiment")),
        "recommendation": gate.get("recommendation") or "diagnostic_only",
        "reason": gate.get("reason") or "qualification missing or not generated",
    }


def _sensitive_scan() -> dict[str, Any]:
    sensitive = [
        ROOT / "v4_replay_memory.py",
        ROOT / "local_cruncher_v4_2_calibrated.py",
        ROOT / "local_cruncher_v4_deep_stacking.py",
    ]
    enabled_true = []
    for path in sensitive:
        if path.exists() and "ENABLE_REPLAY_PRIOR = True" in path.read_text(encoding="utf-8", errors="ignore"):
            enabled_true.append(str(path.relative_to(ROOT)))
    second_runners = [str(path.name) for path in ROOT.glob("local_cruncher_v4_3*.py")]
    return {
        "enable_replay_prior_true_hits": enabled_true,
        "feedback_calibrator_exists": (ROOT / "feedback_calibrator.py").exists(),
        "suspicious_second_runners": second_runners,
    }


def build_audit() -> dict[str, Any]:
    git = _git_state()
    critical = _file_map(CRITICAL_FILES)
    outputs = _file_map(GENERATED_OUTPUTS)
    replay = _replay_state()
    physics = _physics_state()
    sensitive = _sensitive_scan()
    warnings = []
    if git["has_uncommitted_changes"]:
        warnings.append("Hay cambios locales sin commit.")
    if git["conflict_detected"]:
        warnings.append("Hay conflictos Git activos.")
    missing_critical = [path for path, row in critical.items() if not row["exists"]]
    if missing_critical:
        warnings.append(f"Faltan archivos criticos: {', '.join(missing_critical)}")
    missing_outputs = [path for path, row in outputs.items() if not row["exists"]]
    if missing_outputs:
        warnings.append(f"Faltan outputs generados: {', '.join(missing_outputs)}")
    if sensitive["enable_replay_prior_true_hits"]:
        warnings.append("ENABLE_REPLAY_PRIOR aparece como True en archivo sensible.")
    if sensitive["feedback_calibrator_exists"]:
        warnings.append("Existe feedback_calibrator.py, archivo prohibido.")
    if sensitive["suspicious_second_runners"]:
        warnings.append("Existe runner secundario sospechoso.")
    return {
        "version": VERSION,
        "generated_at": _utc_now(),
        "git": git,
        "critical_files": critical,
        "generated_outputs": outputs,
        "replay": replay,
        "physics": physics,
        "sensitive_scan": sensitive,
        "warnings": warnings,
        "recommendation": "review_warnings" if warnings else "ok",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Write local Fisicapapa audit state.")
    parser.add_argument("--output", default="v4_audit_state.json")
    args = parser.parse_args()
    report = build_audit()
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Branch: {report['git']['branch']}")
    print(f"Uncommitted changes: {report['git']['has_uncommitted_changes']}")
    print(f"Conflicts: {report['git']['conflict_detected']}")
    print(f"Replay can influence: {report['replay']['can_influence_future_prior']}")
    print(f"Physics records: {report['physics']['weight_records_count']}")
    print(f"Recommendation: {report['recommendation']}")
    if report["warnings"]:
        print("Warnings:")
        for warning in report["warnings"]:
            print(f"- {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
