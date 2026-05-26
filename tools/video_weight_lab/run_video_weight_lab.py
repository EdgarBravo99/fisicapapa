from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from common import parse_bool, read_json


HERE = Path(__file__).resolve().parent


def run_step(args: list[str], allow_failure: bool = False) -> int:
    command = [sys.executable, *args]
    print("+", " ".join(command))
    result = subprocess.run(command, check=False)
    if result.returncode != 0 and not allow_failure:
        raise SystemExit(result.returncode)
    return result.returncode


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--draw", type=int, required=True)
    parser.add_argument("--channel-url", default="https://www.youtube.com/@LN_electronicos/streams")
    parser.add_argument("--video-url")
    parser.add_argument("--download", default="false")
    parser.add_argument("--fps-sample", default="1")
    args = parser.parse_args()

    draw = str(args.draw)
    source_json = "v4_video_weight_source.json"
    video_dir = Path("data/video_weight_lab/videos")
    source_prepared = video_dir / f"revancha_{draw}_source.json"
    frames_dir = Path("data/video_weight_lab/frames") / draw
    review_dir = Path("data/video_weight_lab/review") / draw
    crops_dir = Path("data/video_weight_lab/crops") / draw
    review_dir.mkdir(parents=True, exist_ok=True)

    run_step([str(HERE / "youtube_stream_finder.py"), "--draw", draw, "--channel-url", args.channel_url, "--output", source_json], allow_failure=True)
    prepare_args = [str(HERE / "video_source_prepare.py"), "--draw", draw, "--source-json", source_json, "--download", args.download, "--output-dir", str(video_dir)]
    if args.video_url:
        prepare_args.extend(["--video-url", args.video_url])
    run_step(prepare_args, allow_failure=True)

    source = read_json(source_prepared, {}) or {}
    video_path = source.get("downloaded_video_path", "")
    if not parse_bool(args.download) or not video_path:
        print("No hay video descargado; laboratorio queda en metadata/revisión manual.")
        return 0

    frame_manifest = frames_dir / "frame_manifest.json"
    scene_candidates = review_dir / "scale_scene_candidates.json"
    crop_manifest = crops_dir / "crop_manifest.json"
    ocr_results = review_dir / "scale_ocr_results.json"
    ball_results = review_dir / "ball_number_results.json"
    observations = "v4_ball_weight_observations.json"
    manual_html = review_dir / "manual_review.html"

    run_step([str(HERE / "frame_extractor.py"), "--draw", draw, "--video", video_path, "--output-dir", str(frames_dir), "--fps-sample", args.fps_sample])
    run_step([str(HERE / "scale_scene_detector.py"), "--draw", draw, "--frame-manifest", str(frame_manifest), "--output", str(scene_candidates)])
    run_step([str(HERE / "crop_extractor.py"), "--draw", draw, "--candidates", str(scene_candidates), "--output-dir", str(crops_dir)], allow_failure=True)
    run_step([str(HERE / "scale_display_ocr.py"), "--draw", draw, "--crops", str(crop_manifest), "--output", str(ocr_results)], allow_failure=True)
    run_step([str(HERE / "ball_number_reader.py"), "--draw", draw, "--crops", str(crop_manifest), "--output", str(ball_results)], allow_failure=True)
    run_step([str(HERE / "weight_observation_builder.py"), "--draw", draw, "--source", str(source_prepared), "--scene-candidates", str(scene_candidates), "--ocr", str(ocr_results), "--balls", str(ball_results), "--output", observations])
    run_step([str(HERE / "manual_review_page.py"), "--observations", observations, "--output", str(manual_html)])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
