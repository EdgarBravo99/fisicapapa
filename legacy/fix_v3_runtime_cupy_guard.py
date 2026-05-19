#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Parchea local_cruncher_v3.py para que:
1) No active CuPy si no encuentra nvrtc64_*.dll en CUDA_PATH/PATH.
2) Si CuPy falla durante Monte Carlo, reintente automáticamente con NumPy CPU.

Uso:
  py -X utf8 .\fix_v3_runtime_cupy_guard.py
  py -X utf8 .\local_cruncher_v3.py
"""
from pathlib import Path

TARGET = Path("local_cruncher_v3.py")
if not TARGET.exists():
    raise SystemExit(f"No existe {TARGET.resolve()}")

text = TARGET.read_text(encoding="utf-8")

old_import = '''    try:
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

new_import = '''    try:
        import glob as _glob
        cuda_bins = []
        cuda_path = os.environ.get("CUDA_PATH") or os.environ.get("CUDA_HOME")
        if cuda_path:
            cuda_bins.append(os.path.join(cuda_path, "bin"))
        cuda_bins.extend([p for p in os.environ.get("PATH", "").split(os.pathsep) if p])
        nvrtc_hits = []
        for folder in cuda_bins:
            nvrtc_hits.extend(_glob.glob(os.path.join(folder, "nvrtc64_*.dll")))
            nvrtc_hits.extend(_glob.glob(os.path.join(folder, "nvrtc*.dll")))
        if not nvrtc_hits:
            raise RuntimeError("No encontré nvrtc64_*.dll en CUDA_PATH/PATH. Se usará NumPy CPU para Monte Carlo.")
        import cupy as _cp
        _ = _cp.cuda.runtime.getDeviceCount()
        # Prueba real de NVRTC: fuerza compilación JIT antes de habilitar GPU_ARRAYS.
        _x = _cp.asarray([1, 2, 3], dtype=_cp.float32)
        _kernel = _cp.ElementwiseKernel("float32 x", "float32 y", "y = x + 1", "nvrtc_probe_kernel")
        _y = _kernel(_x)
        _ = float(_cp.sum(_y).get())
        del _x, _y, _kernel
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

if "nvrtc_probe_kernel" not in text:
    if old_import not in text:
        # También soporta el parche anterior.
        start = text.find("    try:\n        import cupy as _cp\n        _ = _cp.cuda.runtime.getDeviceCount()")
        end = text.find("\n\ndef torch_device():", start)
        if start == -1 or end == -1:
            raise SystemExit("No encontré el bloque import_runtime/CuPy para parchear.")
        text = text[:start] + new_import.rstrip("\n") + text[end:]
    else:
        text = text.replace(old_import, new_import, 1)
    print("Import runtime CuPy/NVRTC parcheado.")
else:
    print("Import runtime CuPy/NVRTC ya estaba parcheado.")

# Parche de seguridad dentro de run_pipeline: si Monte Carlo revienta por CuPy runtime, reintenta CPU.
old_call = '''    ranked, net_cpu = monte_carlo_gpu(final_bundle.experts, weights, total=MC_TOTAL_COMBINATIONS)
'''
new_call = '''    try:
        ranked, net_cpu = monte_carlo_gpu(final_bundle.experts, weights, total=MC_TOTAL_COMBINATIONS)
    except Exception as exc:
        global XP, GPU_ARRAYS, cp
        print(f"Monte Carlo CuPy falló en runtime ({exc}). Reintentando con NumPy CPU sin detener el pipeline...")
        cp = None
        XP = np
        GPU_ARRAYS = False
        cleanup_memory()
        ranked, net_cpu = monte_carlo_gpu(final_bundle.experts, weights, total=MC_TOTAL_COMBINATIONS)
'''

if "Reintentando con NumPy CPU sin detener el pipeline" not in text:
    if old_call not in text:
        raise SystemExit("No encontré la llamada monte_carlo_gpu para parchear.")
    text = text.replace(old_call, new_call, 1)
    print("Fallback runtime Monte Carlo parcheado.")
else:
    print("Fallback runtime Monte Carlo ya estaba parcheado.")

TARGET.write_text(text, encoding="utf-8")
print("Parche completo aplicado a local_cruncher_v3.py")
