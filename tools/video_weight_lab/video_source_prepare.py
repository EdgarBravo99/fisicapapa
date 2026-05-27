from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

from common import PRODUCTION_STATUS, parse_bool, read_json, video_id_from_url, write_json


def source_from_inputs(source_json: str, manual_url: str | None) -> tuple[str, str, str, str]:
    if manual_url:
        return manual_url, video_id_from_url(manual_url), "manual_url", ""
    source = read_json(source_json, {}) or {}
    video = source.get("source_video") or {}
    url = video.get("url") or ""
    return url, video.get("video_id") or video_id_from_url(url), "youtube_auto", video.get("title") or ""


def download_video(video_url: str, output_path: Path) -> tuple[bool, str]:
    if not shutil.which("yt-dlp"):
        return False, "yt-dlp no disponible. No se descargó el video."
    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "yt-dlp",
        "-f",
        "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/best",
        "--merge-output-format",
        "mp4",
        "-o",
        str(output_path),
        video_url,
    ]
    result = subprocess.run(command, check=False, capture_output=True, text=True, encoding="utf-8")
    if result.returncode != 0:
        return False, result.stderr.strip() or "yt-dlp no pudo descargar el video."
    return output_path.exists(), "Video descargado para revisión visual."


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--draw", type=int, required=True)
    parser.add_argument("--source-json", default="v4_video_weight_source.json")
    parser.add_argument("--video-url")
    parser.add_argument("--download", default="false")
    parser.add_argument("--output-dir", default="data/video_weight_lab/videos")
    args = parser.parse_args()

    video_url, video_id, source_type, title = source_from_inputs(args.source_json, args.video_url)
    output_dir = Path(args.output_dir)
    video_path = output_dir / f"revancha_{args.draw}.mp4"
    downloaded = False
    notes = "Metadata registrada. Descarga no solicitada."
    if parse_bool(args.download) and video_url:
        downloaded, notes = download_video(video_url, video_path)
    elif not video_url:
        notes = "No hay video_url disponible. Requiere revisión manual."

    payload = {
        "production_status": PRODUCTION_STATUS,
        "draw": args.draw,
        "video_url": video_url,
        "video_id": video_id,
        "title": title,
        "downloaded": downloaded,
        "downloaded_video_path": str(video_path) if downloaded else "",
        "source": source_type if video_url else "unavailable",
        "needs_manual_review": not downloaded,
        "notes_es": notes,
    }
    output_path = output_dir / f"revancha_{args.draw}_source.json"
    write_json(output_path, payload)
    print(f"video source prepared {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
