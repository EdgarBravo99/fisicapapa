from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path
from typing import Any

from common import PRODUCTION_STATUS, read_json, write_json


def save_crop(cv2: Any, image: Any, path: Path) -> str:
    if image is None or image.size == 0:
        return ""
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), image)
    return str(path)


def crop_region(image: Any, left: float, top: float, right: float, bottom: float) -> Any:
    height, width = image.shape[:2]
    x1 = max(0, min(width - 1, int(width * left)))
    y1 = max(0, min(height - 1, int(height * top)))
    x2 = max(x1 + 1, min(width, int(width * right)))
    y2 = max(y1 + 1, min(height, int(height * bottom)))
    return image[y1:y2, x1:x2]


def crop_with_cv2(candidate: dict[str, Any], output_dir: Path) -> dict[str, Any]:
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

    inset_path = ""
    if candidate.get("scene_type") == "scale_inset_top_left":
        inset = frame[0:int(height * 0.45), 0:int(width * 0.45)]
        crop_source = cv2.resize(inset, None, fx=2.8, fy=2.8, interpolation=cv2.INTER_CUBIC)
        inset_path = save_crop(cv2, crop_source, base / "inset_crop.jpg")
        display_regions = [(0.48, 0.08, 0.98, 0.34), (0.38, 0.28, 0.98, 0.55), (0.18, 0.55, 0.96, 0.86)]
        ball_regions = [(0.12, 0.12, 0.68, 0.58), (0.18, 0.28, 0.82, 0.76)]
    else:
        crop_source = frame
        display_regions = [(0.20, 0.48, 0.86, 0.82), (0.05, 0.38, 0.95, 0.92), (0.34, 0.58, 0.96, 0.90)]
        ball_regions = [(0.18, 0.10, 0.82, 0.62), (0.05, 0.05, 0.95, 0.72)]

    display_paths = []
    for index, region in enumerate(display_regions):
        name = "scale_display_crop_primary.jpg" if index == 0 else f"scale_display_crop_alt_{index}.jpg"
        display_paths.append(save_crop(cv2, crop_region(crop_source, *region), base / name))
    ball_paths = []
    for index, region in enumerate(ball_regions):
        name = "ball_crop_primary.jpg" if index == 0 else f"ball_crop_alt_{index}.jpg"
        ball_paths.append(save_crop(cv2, crop_region(crop_source, *region), base / name))

    display_paths = [path for path in display_paths if path]
    ball_paths = [path for path in ball_paths if path]
    return {
        "frame_index": frame_index,
        "timestamp_text": candidate.get("timestamp_text"),
        "scene_type": candidate.get("scene_type"),
        "frame_path": str(full_path),
        "full_frame_reference_path": str(full_path),
        "inset_crop_path": inset_path,
        "scale_display_crop_path": display_paths[0] if display_paths else "",
        "ball_crop_path": ball_paths[0] if ball_paths else "",
        "scale_display_crop_candidates": display_paths,
        "ball_crop_candidates": ball_paths,
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
    for candidate in source.get("candidates", [])[:120]:
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
                "scale_display_crop_candidates": [],
                "ball_crop_candidates": [],
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
