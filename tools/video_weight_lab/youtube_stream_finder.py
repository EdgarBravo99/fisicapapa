from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from typing import Any

from common import PRODUCTION_STATUS, normalize_text, now_iso, write_json


ENGINE_VERSION = "v4.4-video-weight-source-finder"


def title_match_score(title: str, draw: int) -> tuple[bool, str, str]:
    normalized = normalize_text(title)
    has_draw = str(draw) in normalized.split() or str(draw) in normalized
    has_melate = "melate" in normalized
    has_revancha = "revancha" in normalized
    has_revanchita = "revanchita" in normalized
    if has_draw and has_melate and has_revancha and has_revanchita:
        return True, "high", "Título contiene Melate, Revancha, Revanchita y el número de sorteo."
    if has_draw and has_melate and has_revancha:
        return True, "medium", "Título contiene Melate, Revancha y el número de sorteo."
    if has_draw:
        return True, "low", "Título contiene el número de sorteo, pero requiere revisión manual."
    return False, "low", "Título no contiene el sorteo solicitado."


def list_channel_candidates(channel_url: str) -> list[dict[str, Any]]:
    if not shutil.which("yt-dlp"):
        raise RuntimeError("yt-dlp no disponible. Instala yt-dlp o proporciona --video-url manualmente.")
    command = [
        "yt-dlp",
        "--dump-json",
        "--flat-playlist",
        "--playlist-end",
        "80",
        channel_url,
    ]
    result = subprocess.run(command, check=False, capture_output=True, text=True, encoding="utf-8")
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "yt-dlp no pudo listar el canal.")
    rows: list[dict[str, Any]] = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def build_payload(draw: int, channel_url: str, candidates: list[dict[str, Any]], error: str | None = None) -> dict[str, Any]:
    query_title = f"MELATE REVANCHA Y REVANCHITA No.{draw}"
    normalized_candidates = []
    best: dict[str, Any] | None = None
    best_rank = 0
    for row in candidates:
        title = row.get("title") or ""
        matched, confidence, reason = title_match_score(title, draw)
        url = row.get("url") or row.get("webpage_url") or ""
        video_id = row.get("id") or ""
        if url and not url.startswith("http"):
            url = f"https://www.youtube.com/watch?v={url}"
        candidate = {
            "title": title,
            "url": url,
            "video_id": video_id,
            "published_at": row.get("timestamp") or row.get("upload_date") or "",
            "match_confidence": confidence if matched else "low",
            "match_reason_es": reason,
        }
        normalized_candidates.append(candidate)
        rank = {"low": 1, "medium": 2, "high": 3}[candidate["match_confidence"]] if matched else 0
        if matched and rank > best_rank:
            best = candidate
            best_rank = rank
    matched = best is not None
    notes = "Video localizado automáticamente. Requiere revisión visual antes de usar observaciones." if matched else "No se encontró video con título compatible. Revisar manualmente el canal."
    if error:
        notes = error
    return {
        "production_status": PRODUCTION_STATUS,
        "engine_version": ENGINE_VERSION,
        "generated_at": now_iso(),
        "draw": draw,
        "channel_url": channel_url,
        "query_title": query_title,
        "matched": matched,
        "source_video": best,
        "candidates": normalized_candidates,
        "needs_manual_review": not matched,
        "notes_es": notes,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--draw", type=int, required=True)
    parser.add_argument("--channel-url", default="https://www.youtube.com/@LN_electronicos/streams")
    parser.add_argument("--output", default="v4_video_weight_source.json")
    args = parser.parse_args()

    try:
        candidates = list_channel_candidates(args.channel_url)
        payload = build_payload(args.draw, args.channel_url, candidates)
        write_json(args.output, payload)
        print(f"video source finder wrote {args.output}")
        return 0 if payload["matched"] else 2
    except RuntimeError as exc:
        payload = build_payload(args.draw, args.channel_url, [], str(exc))
        write_json(args.output, payload)
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
