from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from common import PRODUCTION_STATUS, read_json, write_json


def crop_with_cv2(candidate: dict, output_dir: Path) -> dict:
    import cv2  # type: ignore

    frame_path = Path(candidate.get("frame_path") or "")
    frame = cv2.imread(str(frame_path))
    if frame is None:
        raise ValueError(f"No se pudo leer frame {frame_path}")
    height, width = frame.shape[:2]
    frame_index = int(candidate.get("frame_index") or 0)
    base = output_dir / f"frame_{frame_index:06d}"
    base.mkdir(parents=True, exist_ok=True)
    full_path = base / "full_frame_reference.jpg"
    shutil.copyfile(frame_path, full_path)

    if candidate.get("scene_type") == "scale_inset_top_left":
        inset = frame[0:int(height * 0.45), 0:int(width * 0.45)]
        inset = cv2.resize(inset, None, fx=2.5, fy=2.5, interpolation=cv2.INTER_CUBIC)
        inset_path = base / "inset_crop.jpg"
        cv2.imwrite(str(inset_path), inset)
        crop_source = inset
    else:
        inset_path = ""
        crop_source = frame

    ch, cw = crop_source.shape[:2]
    display = crop_source[int(ch * 0.55):int(ch * 0.85), int(cw * 0.25):int(cw * 0.85)]
    ball = crop_source[int(ch * 0.15):int(ch * 0.65), int(cw * 0.25):int(cw * 0.75)]
    display_path = base / "scale_display_crop.jpg"
    ball_path = base / "ball_crop.jpg"
    cv2.imwrite(str(display_path), display)
    cv2.imwrite(str(ball_path), ball)
    return {
        "frame_index": frame_index,
        "timestamp_text": candidate.get("timestamp_text"),
        "scene_type": candidate.get("scene_type"),
        "frame_path": str(full_path),
        "inset_crop_path": str(inset_path),
        "scale_display_crop_path": str(display_path),
        "ball_crop_path": str(ball_path),
        "confidence": candidate.get("confidence", "low"),
        "needs_manual_review": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--draw", type=int, required=True)
    parser.add_argument("--candidates", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    try:
        import cv2  # noqa: F401  # type: ignore
    except ImportError:
        print("opencv-python no disponible. Instala opencv-python para crear crops.", file=sys.stderr)
        return 2

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    source = read_json(args.candidates, {}) or {}
    crops = []
    for candidate in source.get("candidates", [])[:80]:
        try:
            crops.append(crop_with_cv2(candidate, output_dir))
        except Exception as exc:  # pragma: no cover - diagnostic path.
            crops.append({
                "frame_index": candidate.get("frame_index"),
                "timestamp_text": candidate.get("timestamp_text"),
                "scene_type": candidate.get("scene_type", "unknown"),
                "frame_path": candidate.get("frame_path", ""),
                "inset_crop_path": "",
                "scale_display_crop_path": "",
                "ball_crop_path": "",
                "confidence": "low",
                "needs_manual_review": True,
                "notes_es": str(exc),
            })
    payload = {"production_status": PRODUCTION_STATUS, "draw": args.draw, "crops": crops}
    write_json(output_dir / "crop_manifest.json", payload)
    print(f"crops generated: {len(crops)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
