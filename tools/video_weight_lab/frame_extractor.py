from __future__ import annotations

import argparse
import sys
from pathlib import Path

from common import PRODUCTION_STATUS, timestamp_text, write_json


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--draw", type=int, required=True)
    parser.add_argument("--video", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--fps-sample", type=float, default=1.0)
    args = parser.parse_args()

    try:
        import cv2  # type: ignore
    except ImportError:
        print("opencv-python no disponible. Instala opencv-python para extraer frames.", file=sys.stderr)
        return 2

    video_path = Path(args.video)
    if not video_path.exists():
        print(f"video no encontrado: {video_path}", file=sys.stderr)
        return 2

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    capture = cv2.VideoCapture(str(video_path))
    fps = capture.get(cv2.CAP_PROP_FPS) or 30.0
    step = max(1, int(round(fps / max(args.fps_sample, 0.01))))
    frames = []
    frame_index = 0
    saved_index = 0
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        if frame_index % step == 0:
            timestamp_sec = frame_index / fps
            frame_path = output_dir / f"frame_{saved_index:06d}.jpg"
            cv2.imwrite(str(frame_path), frame)
            frames.append({
                "frame_index": frame_index,
                "timestamp_sec": round(timestamp_sec, 3),
                "timestamp_text": timestamp_text(timestamp_sec),
                "frame_path": str(frame_path),
            })
            saved_index += 1
        frame_index += 1
    capture.release()

    payload = {
        "production_status": PRODUCTION_STATUS,
        "draw": args.draw,
        "video_path": str(video_path),
        "fps_sample": args.fps_sample,
        "frames": frames,
    }
    write_json(output_dir / "frame_manifest.json", payload)
    print(f"extracted {len(frames)} frames")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
