from __future__ import annotations

import argparse
from html import escape
from pathlib import Path

from common import read_json


def img(path: str, label: str) -> str:
    if not path:
        return f"<p>{escape(label)}: no disponible</p>"
    safe_label = escape(label)
    safe_path = escape(Path(path).as_posix(), quote=True)
    return f'<figure><figcaption>{safe_label}</figcaption><img src="{safe_path}" alt="{safe_label}"></figure>'


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--observations", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    data = read_json(args.observations, {}) or {}
    observations = data.get("observations", [])
    cards = []
    for row in observations:
        event_id = escape(str(row.get("event_id") or "observación"))
        timestamp = escape(str(row.get("timestamp_text") or "no disponible"))
        ball = escape(str(row.get("ball") or "revisión manual"))
        weight = escape(str(row.get("weight_g") or "revisión manual"))
        confidence = escape(str(row.get("confidence") or "low"))
        review_status = escape(str(row.get("review_status") or "pending"))
        notes = escape(str(row.get("notes_es") or "Sin notas."))
        cards.append(f"""
        <article>
          <h2>{event_id}</h2>
          <p><b>Timestamp:</b> {timestamp}</p>
          <p><b>Bola propuesta:</b> {ball}</p>
          <p><b>Peso propuesto:</b> {weight}</p>
          <p><b>Confianza:</b> {confidence} · <b>review_status:</b> {review_status}</p>
          <p>{notes}</p>
          {img(row.get('scale_display_crop_path', ''), 'Display de báscula')}
          {img(row.get('ball_crop_path', ''), 'Bola')}
        </article>
        """)
    draw = escape(str(data.get("draw", "N/D")))
    html = f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <title>Video Weight Lab Review</title>
  <style>
    body {{ background:#0d1117; color:#e6edf3; font-family:system-ui,sans-serif; margin:24px; }}
    article {{ border:1px solid #30363d; border-radius:8px; margin:16px 0; padding:16px; }}
    img {{ max-width:100%; border:1px solid #30363d; border-radius:6px; }}
    figcaption {{ color:#7d8590; margin-bottom:6px; }}
  </style>
</head>
<body>
  <h1>Revisión manual de pesaje visual, sorteo {draw}</h1>
  <p>Observaciones review_default. Aceptar, corregir o descartar debe hacerse manualmente fuera de esta primera versión.</p>
  {''.join(cards) if cards else '<p>No hay observaciones para revisar.</p>'}
</body>
</html>
"""
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding="utf-8")
    print(f"manual review page wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
