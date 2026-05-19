#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Parchea local_cruncher_v3.py para validar CuPy con una operación real y caer a NumPy si falta nvrtc*.dll."""
from pathlib import Path

TARGET = Path("local_cruncher_v3.py")
OLD = '''    try:
        import cupy as _cp
        _ = _cp.cuda.runtime.getDeviceCount()
        cp = _cp
        XP = _cp
        GPU_ARRAYS = True
        print("CuPy activo: Monte Carlo usará GPU/VRAM.")
    except Exception as exc:
        cp = None
        XP = _np
        GPU_ARRAYS = False
        print(f"CuPy no disponible; Monte Carlo usará NumPy CPU. Detalle: {exc}")
'''
NEW = '''    try:
        import cupy as _cp
        _ = _cp.cuda.runtime.getDeviceCount()
        # Prueba real: en Windows puede importar CuPy, pero fallar después por falta de nvrtc*.dll.
        # Esta operación fuerza compilación/ejecución básica antes de declarar GPU_ARRAYS=True.
        _test = _cp.asarray([1, 2, 3], dtype=_cp.float32)
        _ = float(_cp.sum(_test).get())
        del _test
        cp = _cp
        XP = _cp
        GPU_ARRAYS = True
        print("CuPy activo: Monte Carlo usará GPU/VRAM.")
    except Exception as exc:
        cp = None
        XP = _np
        GPU_ARRAYS = False
        print(f"CuPy no disponible o CUDA/NVRTC incompleto; Monte Carlo usará NumPy CPU. Detalle: {exc}")
'''

if not TARGET.exists():
    raise SystemExit(f"No existe {TARGET.resolve()}")

text = TARGET.read_text(encoding="utf-8")
if "CUDA/NVRTC incompleto" in text:
    print("Fallback NVRTC ya estaba aplicado.")
elif OLD not in text:
    raise SystemExit("No encontré el bloque CuPy original para parchear.")
else:
    text = text.replace(OLD, NEW, 1)
    TARGET.write_text(text, encoding="utf-8")
    print("Fallback NVRTC aplicado correctamente a local_cruncher_v3.py")
