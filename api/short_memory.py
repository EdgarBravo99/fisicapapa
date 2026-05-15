# -*- coding: utf-8 -*-
"""Vercel Python endpoint for short_memory_engine.py."""

from __future__ import annotations

import json
import traceback
from http.server import BaseHTTPRequestHandler

from short_memory_engine import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_CANDIDATE_POOL,
    DEFAULT_MC_ITERATIONS,
    draws_from_csv_text,
    draws_from_rows,
    run_engine,
)


def _json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        _json_response(self, 200, {"ok": True})

    def do_GET(self):
        _json_response(
            self,
            200,
            {
                "ok": True,
                "service": "short_memory_engine",
                "methods": ["POST"],
                "input": {
                    "csv": "CSV text as string",
                    "rows": "Optional array rows like [sorteo, fecha, n1, n2, n3, n4, n5, n6]",
                    "options": {
                        "skip_walk_forward": True,
                        "candidate_pool": DEFAULT_CANDIDATE_POOL,
                        "batch_size": DEFAULT_BATCH_SIZE,
                        "monte_carlo_iterations": DEFAULT_MC_ITERATIONS,
                    },
                },
                "algorithms": ["XGBoost calibrated", "Bayesian sigmoid posterior", "STFT/Fourier", "Weighted Monte Carlo"],
            },
        )

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
            raw = self.rfile.read(length).decode("utf-8") if length else "{}"
            payload = json.loads(raw or "{}")
            options = payload.get("options") or {}

            if payload.get("csv"):
                draws = draws_from_csv_text(
                    payload["csv"],
                    natural_cols=payload.get("natural_cols"),
                    additional_col=payload.get("additional_col"),
                    draw_col=payload.get("draw_col"),
                    date_col=payload.get("date_col"),
                )
            elif payload.get("rows"):
                draws = draws_from_rows(payload["rows"])
            else:
                _json_response(self, 400, {"ok": False, "error": "Envía 'csv' como texto o 'rows' como arreglo."})
                return

            result = run_engine(
                draws,
                skip_walk_forward=bool(options.get("skip_walk_forward", True)),
                candidate_pool=int(options.get("candidate_pool", DEFAULT_CANDIDATE_POOL)),
                batch_size=int(options.get("batch_size", DEFAULT_BATCH_SIZE)),
                mc_iterations=int(options.get("monte_carlo_iterations", DEFAULT_MC_ITERATIONS)),
                retrain_every=int(options.get("retrain_every", 5)),
            )

            _json_response(self, 200, {"ok": True, "result": result})
        except Exception as exc:
            _json_response(
                self,
                500,
                {
                    "ok": False,
                    "error": str(exc),
                    "trace": traceback.format_exc(limit=5),
                },
            )
