from __future__ import annotations

import argparse
import re

from common import PRODUCTION_STATUS, read_json, write_json


def read_ball_text(path: str) -> str | None:
    try:
        import pytesseract  # type: ignore
        from PIL import Image  # type: ignore
    except ImportError:
        return None
    if not path:
        return None
    try:
        return pytesseract.image_to_string(Image.open(path), config="--psm 8 -c tessedit_char_whitelist=0123456789")
    except Exception:
        return None


def candidates_from_text(raw: str | None) -> list[dict]:
    if not raw:
        return []
    values = []
    for token in re.findall(r"\d{1,2}", raw):
        number = int(token)
        if 1 <= number <= 56 and number not in values:
            values.append(number)
    candidates = [{"ball": value, "confidence": 0.62 if index == 0 else 0.31} for index, value in enumerate(values[:3])]
    if 6 in values and 16 not in values:
        candidates.append({"ball": 16, "confidence": 0.24})
    if 16 in values and 6 not in values:
        candidates.append({"ball": 6, "confidence": 0.24})
    return candidates


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--draw", type=int, required=True)
    parser.add_argument("--crops", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    manifest = read_json(args.crops, {}) or {}
    results = []
    for crop in manifest.get("crops", []):
        raw = read_ball_text(crop.get("ball_crop_path", ""))
        candidates = candidates_from_text(raw)
        selected = candidates[0]["ball"] if candidates and candidates[0]["confidence"] >= 0.6 else None
        confidence = "medium" if selected else "low"
        results.append({
            "frame_index": crop.get("frame_index"),
            "timestamp_text": crop.get("timestamp_text"),
            "selected_ball": selected,
            "ball_candidates": candidates,
            "confidence": confidence,
            "needs_manual_review": True,
            "ball_crop_path": crop.get("ball_crop_path", ""),
        })
    payload = {"production_status": PRODUCTION_STATUS, "draw": args.draw, "ball_results": results}
    write_json(args.output, payload)
    print(f"ball number results: {len(results)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
