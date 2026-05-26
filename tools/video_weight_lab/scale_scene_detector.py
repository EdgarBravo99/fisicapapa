from __future__ import annotations

import argparse
from pathlib import Path

from common import PRODUCTION_STATUS, read_json, write_json


def classify_frame(frame: dict, ordinal: int) -> dict | None:
    # Lightweight first pass: sample regularly and mark candidates for manual review.
    # Real OCR/CV happens later when optional dependencies are available.
    if ordinal % 8 != 0:
        return None
    scene_type = "scale_inset_top_left" if ordinal % 16 == 0 else "unknown"
    confidence = "low"
    reason = (
        "Candidato por muestreo periódico; revisar si el recuadro superior izquierdo contiene pesaje."
        if scene_type == "scale_inset_top_left"
        else "Candidato amplio por muestreo; requiere revisión manual para confirmar báscula."
    )
    return {
        "frame_index": frame.get("frame_index"),
        "timestamp_sec": frame.get("timestamp_sec"),
        "timestamp_text": frame.get("timestamp_text"),
        "frame_path": frame.get("frame_path"),
        "scene_type": scene_type,
        "confidence": confidence,
        "needs_manual_review": True,
        "reason_es": reason,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--draw", type=int, required=True)
    parser.add_argument("--frame-manifest", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    manifest = read_json(args.frame_manifest, {}) or {}
    candidates = []
    for ordinal, frame in enumerate(manifest.get("frames", [])):
        candidate = classify_frame(frame, ordinal)
        if candidate:
            candidates.append(candidate)
        if len(candidates) >= 80:
            break
    payload = {
        "production_status": PRODUCTION_STATUS,
        "draw": args.draw,
        "candidates": candidates,
    }
    write_json(args.output, payload)
    print(f"scale scene candidates: {len(candidates)}")
    return 0 if Path(args.frame_manifest).exists() else 2


if __name__ == "__main__":
    raise SystemExit(main())
