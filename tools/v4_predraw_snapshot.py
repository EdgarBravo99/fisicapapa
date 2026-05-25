# -*- coding: utf-8 -*-
"""Freeze a V4.3 slate before the next draw for later post-draw audit."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from v4_winner_composition_audit import utc_now


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_DIR = ROOT / "v4_predraw_slate_snapshots"


def load_json(path: str | Path) -> dict[str, Any]:
    json_path = Path(path)
    with json_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Expected object in {json_path}")
    return data


def slate_hash(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def build_snapshot(
    slate_path: str | Path = "v4_hybrid_composition_slate.json",
    target_draw: int | None = None,
) -> dict[str, Any]:
    slate = load_json(ROOT / slate_path)
    source_latest_draw = slate.get("latest_draw")
    if not isinstance(source_latest_draw, int):
        raise ValueError("v4_hybrid_composition_slate.json does not expose integer latest_draw.")

    inferred = target_draw is None
    final_target_draw = int(target_draw if target_draw is not None else source_latest_draw + 1)

    return {
        "version": "V4.3-predraw-slate-snapshot",
        "snapshot_created_at": utc_now(),
        "source_latest_draw": source_latest_draw,
        "target_draw": final_target_draw,
        "inferred_target_draw": inferred,
        "engine_version": slate.get("engine_version"),
        "production_status": slate.get("production_status", "review_default"),
        "source_policy": slate.get("source_policy", {}),
        "slate": slate.get("slate", []),
        "validation_summary": slate.get("validation_summary", {}),
        "warnings": slate.get("warnings", []),
        "slate_hash": slate_hash(slate),
        "no_outcome_certainty_claims": True,
    }


def write_snapshot(snapshot: dict[str, Any], force: bool = False) -> Path:
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    target_draw = snapshot["target_draw"]
    output_path = SNAPSHOT_DIR / f"v4_predraw_slate_target_{target_draw}.json"
    if output_path.exists() and not force:
        raise FileExistsError(f"Snapshot already exists: {output_path}. Use --force to overwrite explicitly.")
    output_path.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8")
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Freeze the current V4.3 slate before the next draw.")
    parser.add_argument("--slate", default="v4_hybrid_composition_slate.json")
    parser.add_argument("--target-draw", type=int, default=None)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    try:
        snapshot = build_snapshot(args.slate, args.target_draw)
        output_path = write_snapshot(snapshot, force=args.force)
    except (FileNotFoundError, ValueError, FileExistsError, json.JSONDecodeError) as exc:
        print(f"[v4-predraw-snapshot] ERROR: {exc}")
        return 1

    print(f"[v4-predraw-snapshot] wrote {output_path}")
    print(f"[v4-predraw-snapshot] target_draw={snapshot['target_draw']} source_latest_draw={snapshot['source_latest_draw']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
