#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Preflight CUDA/CuPy/PyTorch para V4.

No entrena ni modifica resultados. Revisa dependencias y corrige lo que puede:
- Instala cupy-cuda12x si falta CuPy.
- Detecta CUDA Toolkit y NVRTC.
- Genera .v4_cuda_env.bat para que run_local_cruncher_v4.bat agregue CUDA\bin al PATH.
- Prueba torch.cuda y cupy.ElementwiseKernel.
"""
from __future__ import annotations

import glob
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENV_BAT = ROOT / ".v4_cuda_env.bat"


def exists(mod: str) -> bool:
    return importlib.util.find_spec(mod) is not None


def pip_install(pkg: str) -> bool:
    try:
        print(f"Instalando {pkg}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg, "--quiet", "--disable-pip-version-check"])
        return True
    except Exception as exc:
        print(f"ADVERTENCIA: no pude instalar {pkg}: {exc}")
        return False


def find_cuda_bins() -> list[str]:
    bins: list[str] = []
    for key in ("CUDA_PATH", "CUDA_HOME"):
        base = os.environ.get(key)
        if base:
            b = Path(base) / "bin"
            if b.exists():
                bins.append(str(b))
    root = Path(r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA")
    if root.exists():
        for folder in sorted(root.glob("v*"), reverse=True):
            b = folder / "bin"
            if b.exists():
                bins.append(str(b))
    for entry in os.environ.get("PATH", "").split(os.pathsep):
        if entry and Path(entry).exists() and "CUDA" in entry.upper():
            bins.append(entry)
    out = []
    seen = set()
    for b in bins:
        key = b.lower()
        if key not in seen:
            seen.add(key)
            out.append(b)
    return out


def find_nvrtc(cuda_bins: list[str]) -> str | None:
    for b in cuda_bins:
        hits = glob.glob(str(Path(b) / "nvrtc64_*.dll")) + glob.glob(str(Path(b) / "nvrtc*.dll"))
        if hits:
            return hits[0]
    return None


def write_env(cuda_bin: str | None) -> None:
    if cuda_bin:
        cuda_path = str(Path(cuda_bin).parent)
        ENV_BAT.write_text(
            f"@echo off\r\nset \"CUDA_PATH={cuda_path}\"\r\nset \"CUDA_HOME={cuda_path}\"\r\nset \"PATH={cuda_bin};%PATH%\"\r\n",
            encoding="utf-8",
        )
        print(f"OK: entorno CUDA escrito en {ENV_BAT.name}: {cuda_bin}")
    else:
        ENV_BAT.write_text("@echo off\r\n", encoding="utf-8")
        print("ADVERTENCIA: no encontré CUDA\\bin con nvrtc*.dll. Se dejará fallback CPU/CuPy inactivo.")


def main() -> int:
    required = [("numpy", "numpy"), ("pandas", "pandas"), ("scipy", "scipy"), ("sklearn", "scikit-learn"), ("xgboost", "xgboost"), ("torch", "torch")]
    missing = [pkg for mod, pkg in required if not exists(mod)]
    for pkg in missing:
        pip_install(pkg)

    if not exists("cupy"):
        pip_install("cupy-cuda12x")

    cuda_bins = find_cuda_bins()
    nvrtc = find_nvrtc(cuda_bins)
    write_env(str(Path(nvrtc).parent) if nvrtc else (cuda_bins[0] if cuda_bins else None))

    # Actualizar PATH del proceso actual para las pruebas de import.
    if nvrtc:
        cuda_bin = str(Path(nvrtc).parent)
        os.environ["PATH"] = cuda_bin + os.pathsep + os.environ.get("PATH", "")
        os.environ.setdefault("CUDA_PATH", str(Path(cuda_bin).parent))
        try:
            os.add_dll_directory(cuda_bin)
        except Exception:
            pass

    try:
        import torch
        print(f"Torch: {torch.__version__} | CUDA disponible: {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            print(f"GPU Torch: {torch.cuda.get_device_name(0)}")
    except Exception as exc:
        print(f"ADVERTENCIA: torch no pudo validar CUDA: {exc}")

    try:
        import cupy as cp
        count = cp.cuda.runtime.getDeviceCount()
        x = cp.asarray([1, 2, 3], dtype=cp.float32)
        kernel = cp.ElementwiseKernel("float32 x", "float32 y", "y = x + 1", "v4_nvrtc_probe_kernel")
        y = kernel(x)
        print(f"CuPy OK: GPUs={count}, probe={float(cp.sum(y).get()):.1f}")
    except Exception as exc:
        print(f"ADVERTENCIA: CuPy/NVRTC no disponible; V4 usará CPU en búsqueda exhaustiva si hace falta. Detalle: {exc}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
