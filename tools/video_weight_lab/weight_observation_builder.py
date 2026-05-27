from __future__ import annotations

import argparse
from typing import Any

from common import PRODUCTION_STATUS, merge_confidence, read_json, write_json


ENGINE_VERSION = "v4.4-video-weight-observation-lab"


def by_frame(rows: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    output = {}
    for row in rows:
        try:
            output[int(row.get("frame_index"))] = row
        except (TypeError, ValueError):
            continue
    return output


def build_observations(draw: int, scenes: dict, ocr: dict, balls: dict) -> list[dict[str, Any]]:
    scene_rows = by_frame(scenes.get("candidates", []))
    ocr_rows = by_frame(ocr.get("ocr_results", []))
    ball_rows = by_frame(balls.get("ball_results", []))
    observations = []
    for order, frame_index in enumerate(sorted(set(scene_rows) | set(ocr_rows) | set(ball_rows)), start=1):
        scene = scene_rows.get(frame_index, {})
        weight = ocr_rows.get(frame_index, {})
        ball = ball_rows.get(frame_index, {})
        confidence = merge_confidence(scene.get("confidence"), weight.get("confidence"), ball.get("confidence"))
        needs_review = bool(scene.get("needs_manual_review", True) or weight.get("needs_manual_review", True) or ball.get("needs_manual_review", True))
        if weight.get("weight_g") is None or ball.get("selected_ball") is None:
            needs_review = True
        observations.append({
            "event_id": f"{draw}_weight_{order:03d}",
            "ball": ball.get("selected_ball"),
            "weight_g": weight.get("weight_g"),
            "timestamp_text": scene.get("timestamp_text") or weight.get("timestamp_text") or ball.get("timestamp_text"),
            "frame_index": frame_index,
            "scene_type": scene.get("scene_type", "unknown"),
            "scale_display_crop_path": weight.get("scale_display_crop_path", ""),
            "ball_crop_path": ball.get("ball_crop_path", ""),
            "confidence": confidence,
            "needs_manual_review": needs_review,
            "review_status": "pending",
            "notes_es": "Peso observado desde video. Requiere revisión manual antes de usarse como evidencia.",
        })
    return observations


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--draw", type=int, required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--scene-candidates", required=True)
    parser.add_argument("--ocr", required=True)
    parser.add_argument("--balls", required=True)
    parser.add_argument("--output", default="v4_ball_weight_observations.json")
    args = parser.parse_args()

    source = read_json(args.source, {}) or {}
    scenes = read_json(args.scene_candidates, {}) or {}
    ocr = read_json(args.ocr, {}) or {}
    balls = read_json(args.balls, {}) or {}
    observations = build_observations(args.draw, scenes, ocr, balls)
    payload = {
        "production_status": PRODUCTION_STATUS,
        "engine_version": ENGINE_VERSION,
        "draw": args.draw,
        "source_type": "video_observation",
        "source_video": {
            "url": source.get("video_url", ""),
            "video_id": source.get("video_id", ""),
            "title": source.get("title", ""),
        },
        "observations": observations,
    }
    write_json(args.output, payload)
    print(f"weight observations: {len(observations)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
