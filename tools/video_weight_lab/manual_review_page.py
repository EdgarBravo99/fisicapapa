from __future__ import annotations

import argparse
from pathlib import Path

from common import read_json


def img(path: str, label: str) -> str:
    if not path:
        return f"<p>{label}: no disponible</p>"
    return f'<figure><figcaption>{label}</figcaption><img src="{Path(path).as_posix()}" alt="{label}"></figure>'


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--observations", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    data = read_json(args.observations, {}) or {}
    observations = data.get("observations", [])
    cards = []
    for row in observations:
        cards.append(f"""
        <article>
          <h2>{row.get('event_id')}</h2>
          <p><b>Timestamp:</b> {row.get('timestamp_text')}</p>
          <p><b>Bola propuesta:</b> {row.get('ball')}</p>
          <p><b>Peso propuesto:</b> {row.get('weight_g')}</p>
          <p><b>Confianza:</b> {row.get('confidence')} · <b>review_status:</b> {row.get('review_status')}</p>
          <p>{row.get('notes_es')}</p>
          {img(row.get('scale_display_crop_path', ''), 'Display de báscula')}
          {img(row.get('ball_crop_path', ''), 'Bola')}
        </article>
        """)
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
  <h1>Revisión manual de pesaje visual, sorteo {data.get('draw', 'N/D')}</h1>
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
