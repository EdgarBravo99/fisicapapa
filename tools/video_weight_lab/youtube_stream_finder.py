from __future__ import annotations

import argparse
import json
import subprocess
import sys
from typing import Any

from common import PRODUCTION_STATUS, normalize_text, now_iso, write_json, yt_dlp_command


ENGINE_VERSION = "v4.4-video-weight-source-finder"


def has_generic_draw_placeholder(normalized: str) -> bool:
    tokens = normalized.split()
    if "xxxx" in tokens:
        return True
    return any(tokens[index] == "no" and index + 1 < len(tokens) and tokens[index + 1] == "xxxx" for index in range(len(tokens)))


def candidate_date_rank(row: dict[str, Any]) -> int:
    value = row.get("timestamp") or row.get("upload_date") or 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def title_match_score(title: str, draw: int) -> tuple[bool, str, bool, bool, bool, str]:
    normalized = normalize_text(title)
    has_draw = str(draw) in normalized.split() or str(draw) in normalized
    has_melate = "melate" in normalized
    has_revancha = "revancha" in normalized
    has_revanchita = "revanchita" in normalized
    has_game_family = has_melate and has_revancha and has_revanchita
    has_generic_no = has_generic_draw_placeholder(normalized)
    if has_draw and has_game_family:
        return True, "high", False, True, False, f"Título contiene Melate, Revancha, Revanchita y el sorteo exacto No.{draw}."
    if has_draw and has_melate and has_revancha:
        return True, "medium", False, True, True, f"Título contiene el sorteo exacto No.{draw} y parte de la familia Melate/Revancha."
    if has_game_family and has_generic_no:
        return True, "medium", True, False, True, "Título genérico con No.xxxx; no confirma el sorteo exacto. Requiere revisión manual."
    if has_draw:
        return True, "low", False, True, True, f"Título contiene el sorteo exacto No.{draw}, pero requiere revisión manual por familia incompleta."
    return False, "low", False, False, True, f"Título no contiene el sorteo solicitado No.{draw}."


def list_channel_candidates(channel_url: str, playlist_end: int) -> list[dict[str, Any]]:
    yt_dlp = yt_dlp_command()
    if yt_dlp is None:
        raise RuntimeError("yt-dlp no disponible. Instala yt-dlp o proporciona --video-url manualmente.")
    command = [
        *yt_dlp,
        "--dump-json",
        "--flat-playlist",
        "--playlist-end",
        str(playlist_end),
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


def build_payload(
    draw: int,
    channel_url: str,
    candidates: list[dict[str, Any]],
    error: str | None = None,
    allow_generic_fallback: bool = False,
) -> dict[str, Any]:
    query_title = f"MELATE REVANCHA Y REVANCHITA No.{draw}"
    normalized_candidates = []
    best: dict[str, Any] | None = None
    best_score = (-1, -1)
    for row in sorted(candidates, key=candidate_date_rank, reverse=True):
        title = row.get("title") or ""
        matched, confidence, generic_title_match, exact_draw_match, needs_review, reason = title_match_score(title, draw)
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
            "generic_title_match": generic_title_match,
            "exact_draw_match": exact_draw_match,
            "needs_manual_review": needs_review,
            "match_reason_es": reason,
        }
        normalized_candidates.append(candidate)
        rank = {"low": 1, "medium": 2, "high": 3}[candidate["match_confidence"]] if matched else 0
        if generic_title_match and not allow_generic_fallback:
            rank = 0
        score = (rank, candidate_date_rank(row))
        if matched and rank > 0 and score > best_score:
            best = candidate
            best_score = score
    matched = best is not None
    needs_manual_review = (not matched) or bool(best and best.get("needs_manual_review"))
    notes = "Video localizado automáticamente. Requiere revisión visual antes de usar observaciones." if matched else "No se encontró video con título compatible. Revisar manualmente el canal."
    if best and best.get("generic_title_match"):
        notes = "Solo se encontró candidato genérico No.xxxx; confirmar manualmente que corresponde al sorteo solicitado."
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
        "needs_manual_review": needs_manual_review,
        "notes_es": notes,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--draw", type=int, required=True)
    parser.add_argument("--channel-url", default="https://www.youtube.com/@LN_electronicos/streams")
    parser.add_argument("--playlist-end", type=int, default=200)
    parser.add_argument("--allow-generic-fallback", choices=["true", "false"], default="false")
    parser.add_argument("--output", default="v4_video_weight_source.json")
    args = parser.parse_args()

    try:
        candidates = list_channel_candidates(args.channel_url, args.playlist_end)
        payload = build_payload(
            args.draw,
            args.channel_url,
            candidates,
            allow_generic_fallback=args.allow_generic_fallback == "true",
        )
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
