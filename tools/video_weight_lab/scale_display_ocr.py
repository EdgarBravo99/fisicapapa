from __future__ import annotations

import argparse
import re

from common import PRODUCTION_STATUS, confidence_rank, read_json, write_json


WEIGHT_PATTERN = re.compile(r"(?P<value>[2-8][\.,]\d{1,3})\s*(?P<unit>g)?", re.IGNORECASE)


def parse_weight(raw_text: str) -> tuple[float | None, str, bool]:
    match = WEIGHT_PATTERN.search(raw_text or "")
    if not match:
        return None, "low", True
    value_text = match.group("value").replace(",", ".")
    try:
        value = float(value_text)
    except ValueError:
        return None, "low", True
    has_two_decimals = bool(re.search(r"[\.,]\d{2}\b", match.group("value")))
    has_unit = bool(match.group("unit"))
    if not 2.0 <= value <= 8.0:
        return value, "low", True
    if has_two_decimals and has_unit:
        return value, "high", False
    return value, "medium", True


def ocr_image(path: str) -> str | None:
    try:
        import pytesseract  # type: ignore
        from PIL import Image  # type: ignore
    except ImportError:
        return None
    if not path:
        return None
    try:
        return pytesseract.image_to_string(Image.open(path), config="--psm 7")
    except Exception:
        return None


def crop_paths(crop: dict) -> list[str]:
    paths = [path for path in crop.get("scale_display_crop_candidates", []) if path]
    fallback = crop.get("scale_display_crop_path", "")
    if fallback and fallback not in paths:
        paths.append(fallback)
    return paths


def best_ocr_result(paths: list[str]) -> tuple[str | None, float | None, str, bool, str]:
    best = (None, None, "low", True, "")
    for path in paths:
        raw = ocr_image(path)
        weight, confidence, review = parse_weight(raw or "")
        if confidence_rank(confidence) > confidence_rank(best[2]):
            best = (raw, weight, confidence, review or raw is None, path)
    return best


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--draw", type=int, required=True)
    parser.add_argument("--crops", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    manifest = read_json(args.crops, {}) or {}
    results = []
    for crop in manifest.get("crops", []):
        attempted = crop_paths(crop)
        raw, weight, confidence, review, selected_path = best_ocr_result(attempted)
        results.append({
            "frame_index": crop.get("frame_index"),
            "timestamp_text": crop.get("timestamp_text"),
            "raw_ocr": raw,
            "weight_g": weight,
            "confidence": confidence,
            "needs_manual_review": review or raw is None,
            "scale_display_crop_path": selected_path or crop.get("scale_display_crop_path", ""),
            "selected_crop_path": selected_path,
            "attempted_crop_paths": attempted,
        })
    payload = {"production_status": PRODUCTION_STATUS, "draw": args.draw, "ocr_results": results}
    write_json(args.output, payload)
    print(f"scale OCR results: {len(results)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
