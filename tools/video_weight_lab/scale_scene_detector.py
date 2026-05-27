from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from common import PRODUCTION_STATUS, read_json, write_json


def temporal_fallback(frame: dict[str, Any], ordinal: int, reason_prefix: str) -> dict[str, Any] | None:
    if ordinal % 8 != 0:
        return None
    scene_type = "scale_inset_top_left" if ordinal % 16 == 0 else "unknown"
    return {
        "frame_index": frame.get("frame_index"),
        "timestamp_sec": frame.get("timestamp_sec"),
        "timestamp_text": frame.get("timestamp_text"),
        "frame_path": frame.get("frame_path"),
        "scene_type": scene_type,
        "confidence": "low",
        "needs_manual_review": True,
        "reason_es": f"{reason_prefix} Candidato por muestreo temporal; requiere revisión manual.",
    }


def region_features(image: Any) -> dict[str, float | bool]:
    import cv2  # type: ignore
    import numpy as np  # type: ignore

    if image is None or image.size == 0:
        return {"white_ratio": 0.0, "red_ratio": 0.0, "circle_count": 0, "display_like": False}
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    white_mask = cv2.inRange(hsv, (0, 0, 175), (180, 70, 255))
    red_mask_a = cv2.inRange(hsv, (0, 70, 70), (12, 255, 255))
    red_mask_b = cv2.inRange(hsv, (168, 70, 70), (180, 255, 255))
    red_mask = cv2.bitwise_or(red_mask_a, red_mask_b)
    white_ratio = float(np.count_nonzero(white_mask)) / float(white_mask.size)
    red_ratio = float(np.count_nonzero(red_mask)) / float(red_mask.size)
    circles = cv2.HoughCircles(
        cv2.medianBlur(gray, 5),
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=max(18, min(image.shape[:2]) // 8),
        param1=80,
        param2=18,
        minRadius=8,
        maxRadius=max(12, min(image.shape[:2]) // 4),
    )
    edges = cv2.Canny(gray, 50, 150)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    display_like = False
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        if w > image.shape[1] * 0.18 and h > image.shape[0] * 0.04 and 2.2 <= (w / max(h, 1)) <= 8.0:
            roi = gray[y:y + h, x:x + w]
            if roi.size and float((roi < 80).sum()) / float(roi.size) > 0.18:
                display_like = True
                break
    return {
        "white_ratio": white_ratio,
        "red_ratio": red_ratio,
        "circle_count": 0 if circles is None else int(circles.shape[1]),
        "display_like": display_like,
    }


def visual_candidate(frame: dict[str, Any], ordinal: int) -> dict[str, Any] | None:
    import cv2  # type: ignore

    frame_path = frame.get("frame_path") or ""
    image = cv2.imread(frame_path)
    if image is None:
        return temporal_fallback(frame, ordinal, "Frame no legible por OpenCV.")
    height, width = image.shape[:2]
    inset = image[0:int(height * 0.42), 0:int(width * 0.42)]
    center = image[int(height * 0.12):int(height * 0.88), int(width * 0.12):int(width * 0.88)]
    inset_features = region_features(inset)
    center_features = region_features(center)
    reasons = []
    score_inset = 0
    score_full = 0

    if inset_features["display_like"]:
        score_inset += 2
        reasons.append("display rectangular posible en recuadro superior izquierdo")
    if inset_features["circle_count"] or inset_features["white_ratio"] > 0.05:
        score_inset += 1
        reasons.append("zona blanca/circular compatible con bola en recuadro")
    if inset_features["red_ratio"] > 0.004:
        score_inset += 1
        reasons.append("pixeles rojos compatibles con número de bola en recuadro")
    if center_features["display_like"]:
        score_full += 2
        reasons.append("display rectangular posible en zona principal")
    if center_features["circle_count"] or center_features["white_ratio"] > 0.04:
        score_full += 1
        reasons.append("zona blanca/circular compatible con bola en zona principal")
    if center_features["red_ratio"] > 0.003:
        score_full += 1
        reasons.append("pixeles rojos compatibles con número de bola en zona principal")

    best_score = max(score_inset, score_full)
    if best_score <= 0:
        return temporal_fallback(frame, ordinal, "Sin indicios visuales fuertes.")
    scene_type = "scale_inset_top_left" if score_inset >= score_full else "scale_fullscreen"
    confidence = "high" if best_score >= 4 else "medium" if best_score >= 2 else "low"
    return {
        "frame_index": frame.get("frame_index"),
        "timestamp_sec": frame.get("timestamp_sec"),
        "timestamp_text": frame.get("timestamp_text"),
        "frame_path": frame_path,
        "scene_type": scene_type,
        "confidence": confidence,
        "needs_manual_review": confidence != "high",
        "reason_es": "Indicios visuales: " + "; ".join(reasons[:5]) + ".",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--draw", type=int, required=True)
    parser.add_argument("--frame-manifest", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    manifest = read_json(args.frame_manifest, {}) or {}
    try:
        import cv2  # noqa: F401  # type: ignore
        cv2_available = True
    except ImportError:
        cv2_available = False
    candidates = []
    for ordinal, frame in enumerate(manifest.get("frames", [])):
        if cv2_available:
            candidate = visual_candidate(frame, ordinal)
        else:
            candidate = temporal_fallback(frame, ordinal, "Fallback por muestreo temporal; OpenCV no disponible.")
        if candidate:
            candidates.append(candidate)
        if len(candidates) >= 120:
            break
    payload = {
        "production_status": PRODUCTION_STATUS,
        "draw": args.draw,
        "opencv_available": cv2_available,
        "candidates": candidates,
    }
    write_json(args.output, payload)
    print(f"scale scene candidates: {len(candidates)}")
    return 0 if Path(args.frame_manifest).exists() else 2


if __name__ == "__main__":
    raise SystemExit(main())
