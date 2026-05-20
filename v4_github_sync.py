#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Local git sync helpers for Fisicapapa V4.3.

No tokens or credentials are stored here. Authentication is delegated to the
user's local git setup.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


class GitSyncError(RuntimeError):
    """Raised when a local git operation cannot be completed."""


def _run_git(args: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    ensure_git_available()
    completed = subprocess.run(
        ["git", *args],
        check=False,
        capture_output=True,
        encoding="utf-8",
    )
    if check and completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise GitSyncError(f"git {' '.join(args)} fallo: {detail}")
    return completed


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_int(value: Any) -> int | None:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def _infer_prediction_draw(results_json: dict[str, Any]) -> str | None:
    candidates = [
        results_json.get("prediction_draw"),
        results_json.get("target_prediction_draw"),
        results_json.get("historical_forgetting", {}).get("buffer_last_draw"),
    ]
    rows = results_json.get("walk_forward", {}).get("rows")
    if isinstance(rows, list) and rows:
        candidates.append(rows[-1].get("draw_id"))
    for value in candidates:
        parsed = _parse_int(value)
        if parsed is not None:
            return str(parsed)
    return None


def _read_archive_index(archive_dir: str | Path = "resultados_archive") -> dict[str, Any]:
    index_path = Path(archive_dir) / "index.json"
    if not index_path.exists():
        return {"version": "V4.3.1-archive-index", "entries": []}
    try:
        data = json.loads(index_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"version": "V4.3.1-archive-index", "entries": []}
    if not isinstance(data, dict):
        return {"version": "V4.3.1-archive-index", "entries": []}
    data.setdefault("version", "V4.3.1-archive-index")
    data.setdefault("entries", [])
    return data


def write_archive_index(index: dict[str, Any], archive_dir: str | Path = "resultados_archive") -> None:
    entries = index.get("entries")
    if not isinstance(entries, list) or not entries:
        return
    archive_path = Path(archive_dir)
    archive_path.mkdir(exist_ok=True)
    index["version"] = "V4.3.1-archive-index"
    index["last_updated"] = _utc_now()
    (archive_path / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")


def register_archive_snapshot(
    snapshot_path: str | Path,
    metadata: dict[str, Any],
    archive_dir: str | Path = "resultados_archive",
    status: str = "available",
    warnings: list[str] | None = None,
) -> None:
    path = Path(snapshot_path)
    index = _read_archive_index(archive_dir)
    entries = index.setdefault("entries", [])
    commit_sha = metadata.get("commit_sha")
    content_sha256 = metadata.get("content_sha256")
    existing = None
    for entry in entries:
        if commit_sha and entry.get("commit_sha") == commit_sha:
            existing = entry
            break
        if content_sha256 and entry.get("content_sha256") == content_sha256:
            existing = entry
            break
        if entry.get("path") == str(path):
            existing = entry
            break
    payload = {
        "path": str(path),
        "filename": path.name,
        "source": metadata.get("source"),
        "commit_sha": commit_sha,
        "short_sha": metadata.get("short_sha"),
        "content_sha256": content_sha256,
        "prediction_draw": metadata.get("prediction_draw"),
        "game_mode": metadata.get("game_mode"),
        "model_version": metadata.get("model_version"),
        "score_kind": metadata.get("score_kind"),
        "status": status,
        "warnings": warnings or [],
        "indexed_at": _utc_now(),
    }
    if existing:
        existing.update(payload)
    else:
        entries.append(payload)
    write_archive_index(index, archive_dir)


def ensure_git_available() -> None:
    if shutil.which("git") is None:
        raise GitSyncError("git CLI no esta instalado o no esta en PATH.")


def is_git_repo() -> bool:
    result = _run_git(["rev-parse", "--is-inside-work-tree"], check=False)
    return result.returncode == 0 and result.stdout.strip() == "true"


def git_current_branch() -> str:
    return _run_git(["branch", "--show-current"]).stdout.strip()


def git_status_porcelain() -> str:
    return _run_git(["status", "--porcelain"]).stdout


def is_working_tree_clean() -> bool:
    return not git_status_porcelain().strip()


def git_remote_url(remote: str = "origin") -> str | None:
    result = _run_git(["remote", "get-url", remote], check=False)
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def git_pull_rebase(remote: str = "origin", branch: str = "main") -> str:
    return _run_git(["pull", "--rebase", remote, branch]).stdout


def safe_git_pull_rebase_main() -> dict[str, Any]:
    """Pull main only when it is safe; otherwise return a recoverable warning."""
    try:
        ensure_git_available()
        if not is_git_repo():
            return {"attempted": False, "ok": False, "warnings": ["Este directorio no es un repo git."]}
        current = git_current_branch()
        if current != "main":
            return {
                "attempted": False,
                "ok": False,
                "branch": current,
                "warnings": [f"Rama actual '{current}' no es main; se usa historial local sin pull."],
            }
        if not is_working_tree_clean():
            return {
                "attempted": False,
                "ok": False,
                "branch": current,
                "warnings": ["Working tree con cambios locales; se omite pull --rebase para no pisar trabajo."],
            }
        output = git_pull_rebase("origin", "main")
        return {"attempted": True, "ok": True, "branch": current, "output": output, "warnings": []}
    except GitSyncError as exc:
        return {"attempted": True, "ok": False, "warnings": [f"git pull no completado: {exc}"]}


def list_resultados_json_commits(limit: int = 50) -> list[str]:
    raw = _run_git(["log", f"--format=%H", "--", "resultados.json"], check=False)
    if raw.returncode != 0:
        detail = (raw.stderr or raw.stdout or "").strip()
        raise GitSyncError(f"No pude listar commits de resultados.json: {detail}")
    commits = [line.strip() for line in raw.stdout.splitlines() if line.strip()]
    return commits[: max(0, limit)]


def show_resultados_json_at_commit(commit_sha: str) -> str:
    result = _run_git(["show", f"{commit_sha}:resultados.json"], check=False)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise GitSyncError(f"No pude leer resultados.json en {commit_sha[:12]}: {detail}")
    return result.stdout


def extract_resultados_snapshot_from_commit(commit_sha: str) -> dict[str, Any]:
    text = show_resultados_json_at_commit(commit_sha)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise GitSyncError(f"resultados.json invalido en {commit_sha[:12]}: {exc}") from exc
    if not isinstance(data, dict):
        raise GitSyncError(f"resultados.json en {commit_sha[:12]} no es objeto JSON.")
    short_sha = commit_sha[:12]
    metadata = {
        "source": "git_history",
        "commit_sha": commit_sha,
        "short_sha": short_sha,
        "imported_at": _utc_now(),
        "original_path": "resultados.json",
        "content_sha256": _content_hash(text),
        "prediction_draw": _infer_prediction_draw(data),
        "game_mode": data.get("game_mode"),
        "model_version": data.get("model_version"),
        "score_kind": data.get("score_kind"),
    }
    data["snapshot_metadata"] = metadata
    return data


def build_snapshot_filename(results_json: dict[str, Any], commit_sha: str) -> str:
    draw_id = _infer_prediction_draw(results_json) or "unknown"
    short_sha = commit_sha[:12]
    safe_draw = "".join(ch for ch in str(draw_id) if ch.isalnum() or ch in {"-", "_"}) or "unknown"
    return f"resultados_git_{safe_draw}_{short_sha}.json"


def snapshot_already_imported(commit_sha: str, archive_dir: str | Path = "resultados_archive") -> bool:
    archive_path = Path(archive_dir)
    short_sha = commit_sha[:12]
    index = _read_archive_index(archive_path)
    for entry in index.get("entries", []):
        if entry.get("commit_sha") == commit_sha or entry.get("short_sha") == short_sha:
            return True
    for path in archive_path.glob("resultados_git_*.json"):
        if short_sha in path.name:
            return True
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        meta = data.get("snapshot_metadata") if isinstance(data, dict) else {}
        if meta.get("commit_sha") == commit_sha or meta.get("short_sha") == short_sha:
            return True
    return False


def import_resultados_history_from_git(
    archive_dir: str | Path = "resultados_archive",
    limit: int = 50,
    dry_run: bool = False,
) -> dict[str, Any]:
    archive_path = Path(archive_dir)
    summary: dict[str, Any] = {
        "attempted": True,
        "snapshots_imported": 0,
        "snapshots_existing": 0,
        "snapshots_omitted": 0,
        "imported_paths": [],
        "warnings": [],
    }
    try:
        ensure_git_available()
        if not is_git_repo():
            summary["warnings"].append("Este directorio no es un repo git; no se importa historial.")
            return summary
        commits = list_resultados_json_commits(limit)
    except GitSyncError as exc:
        summary["warnings"].append(str(exc))
        return summary
    if not commits:
        summary["warnings"].append("resultados.json no tiene historial git local.")
        return summary
    archive_path.mkdir(exist_ok=True)
    for commit_sha in commits:
        if snapshot_already_imported(commit_sha, archive_path):
            summary["snapshots_existing"] += 1
            continue
        try:
            snapshot = extract_resultados_snapshot_from_commit(commit_sha)
        except GitSyncError as exc:
            summary["snapshots_omitted"] += 1
            summary["warnings"].append(str(exc))
            continue
        filename = build_snapshot_filename(snapshot, commit_sha)
        target = archive_path / filename
        if target.exists():
            summary["snapshots_existing"] += 1
            continue
        if not dry_run:
            target.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
            register_archive_snapshot(target, snapshot.get("snapshot_metadata", {}), archive_path)
        summary["snapshots_imported"] += 1
        summary["imported_paths"].append(str(target))
    return summary


def git_add(paths: Iterable[str | Path]) -> None:
    existing = [str(path) for path in paths if Path(path).exists()]
    if existing:
        _run_git(["add", *existing])


def git_commit(message: str) -> bool:
    if not git_status_porcelain().strip():
        return False
    result = _run_git(["commit", "-m", message], check=False)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        if "nothing to commit" in detail.lower():
            return False
        raise GitSyncError(f"git commit fallo: {detail}")
    return True


def git_push(remote: str = "origin", branch: str | None = None) -> str:
    target_branch = branch or git_current_branch()
    if not target_branch:
        raise GitSyncError("No pude detectar la rama actual para push.")
    return _run_git(["push", remote, target_branch]).stdout


def sync_outputs_to_github(paths: Iterable[str | Path], message: str) -> dict[str, object]:
    ensure_git_available()
    if not is_git_repo():
        raise GitSyncError("Este directorio no es un repo git.")
    current = git_current_branch()
    warnings: list[str] = []
    if current != "main":
        warnings.append(
            f"La rama actual es '{current}', no 'main'. Se hara pull --rebase origin main "
            f"y push a origin {current}; Vercel/main no vera estos cambios hasta mergear esa rama."
        )
    git_pull_rebase("origin", "main")
    git_add(paths)
    status_after_add = git_status_porcelain()
    if not status_after_add.strip():
        return {
            "synced": False,
            "branch": current,
            "warnings": warnings,
            "committed": False,
            "pushed": False,
            "reason": "Sin cambios para commitear.",
        }
    committed = git_commit(message)
    if not committed:
        return {
            "synced": False,
            "branch": current,
            "warnings": warnings,
            "committed": False,
            "pushed": False,
            "reason": "Commit vacio evitado.",
        }
    git_push("origin", current)
    reason = f"Cambios subidos con git CLI local a origin/{current}."
    if current != "main":
        reason += " Main/Vercel los vera despues del merge."
    return {
        "synced": True,
        "branch": current,
        "warnings": warnings,
        "committed": True,
        "pushed": True,
        "reason": reason,
    }


def sync_outputs_to_github_or_desktop(paths: Iterable[str | Path], message: str) -> dict[str, object]:
    """Try Git CLI sync; on auth/push issues leave changes ready for GitHub Desktop."""
    try:
        return sync_outputs_to_github(paths, message)
    except GitSyncError as exc:
        return {
            "synced": False,
            "committed": False,
            "pushed": False,
            "desktop_fallback": True,
            "warnings": [str(exc)],
            "reason": (
                "Git CLI no pudo completar sync. Los archivos quedan locales para revisar, "
                "commitear y pushear con GitHub Desktop."
            ),
        }
