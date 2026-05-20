#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Local git sync helpers for Fisicapapa V4.3.

No tokens or credentials are stored here. Authentication is delegated to the
user's local git setup.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Iterable


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


def git_pull_rebase(remote: str = "origin", branch: str = "main") -> str:
    return _run_git(["pull", "--rebase", remote, branch]).stdout


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
