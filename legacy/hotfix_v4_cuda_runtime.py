#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from pathlib import Path
import re

p = Path('local_cruncher_v4_deep_stacking.py')
if not p.exists():
    raise SystemExit('local_cruncher_v4_deep_stacking.py not found')

s = p.read_text(encoding='utf-8')
if 'def normalize_cuda_runtime_paths_v4()' in s:
    print('OK: CUDA runtime hotfix already applied')
    raise SystemExit(0)

new_block = '''def normalize_cuda_runtime_paths_v4() -> None:
    import glob
    def norm_bin(value):
        if not value:
            return None
        q = Path(str(value).strip().strip('"'))
        candidates = []
        if q.name.lower() == 'bin':
            candidates.append(q)
            candidates.append(q.parent / 'bin')
        else:
            candidates.append(q / 'bin')
            candidates.append(q)
        for c in candidates:
            try:
                if c.exists() and c.is_dir():
                    if c.name.lower() == 'bin' and c.parent.name.lower() == 'bin':
                        c = c.parent
                    return str(c)
            except Exception:
                pass
        return None

    bins = []
    for key in ('CUDA_PATH', 'CUDA_HOME'):
        b = norm_bin(os.environ.get(key))
        if b:
            bins.append(b)
    root = Path(r'C:\\Program Files\\NVIDIA GPU Computing Toolkit\\CUDA')
    if root.exists():
        for folder in sorted(root.glob('v*'), reverse=True):
            b = norm_bin(str(folder))
            if b:
                bins.append(b)
    for entry in os.environ.get('PATH', '').split(os.pathsep):
        if entry and 'CUDA' in entry.upper():
            b = norm_bin(entry)
            if b:
                bins.append(b)

    clean = []
    seen = set()
    for b in bins:
        k = b.lower()
        if k not in seen:
            seen.add(k)
            clean.append(b)

    chosen = None
    for b in clean:
        hits = glob.glob(str(Path(b) / 'nvrtc64_*.dll')) + glob.glob(str(Path(b) / 'nvrtc*.dll'))
        if hits:
            chosen = b
            break
    if not chosen and clean:
        chosen = clean[0]

    if chosen:
        os.environ['CUDA_PATH'] = str(Path(chosen).parent)
        os.environ['CUDA_HOME'] = str(Path(chosen).parent)
        os.environ['PATH'] = chosen + os.pathsep + os.environ.get('PATH', '')
        try:
            os.add_dll_directory(chosen)
        except Exception:
            pass


def import_runtime() -> None:
    global pd, np, rfft, rfftfreq, XGBClassifier, torch, nn, cp, GPU_ARRAYS
    import pandas as _pd
    import numpy as _np
    from scipy.fft import rfft as _rfft, rfftfreq as _rfftfreq
    from xgboost import XGBClassifier as _XGBClassifier
    import torch as _torch
    import torch.nn as _nn
    pd, np, rfft, rfftfreq, XGBClassifier, torch, nn = _pd, _np, _rfft, _rfftfreq, _XGBClassifier, _torch, _nn
    try:
        normalize_cuda_runtime_paths_v4()
        import cupy as _cp
        _cp.cuda.runtime.getDeviceCount()
        x = _cp.asarray([1, 2, 3], dtype=_cp.float32)
        kernel = _cp.ElementwiseKernel('float32 x', 'float32 y', 'y = x + 1', 'v4_runtime_nvrtc_probe')
        y = kernel(x)
        _ = float(_cp.sum(y).get())
        cp, GPU_ARRAYS = _cp, True
        print('CuPy activo para aceleracion parcial.')
    except Exception as exc:
        cp, GPU_ARRAYS = None, False
        print(f'CuPy no disponible; fallback NumPy CPU. Detalle: {exc}')
'''

pattern = r'def import_runtime\(\) -> None:\n(?:    .*\n)*?        print\(f"CuPy no disponible; fallback NumPy CPU\. Detalle: \{exc\}"\)\n'
ns, count = re.subn(pattern, lambda _m: new_block, s, count=1)
if count != 1:
    raise SystemExit('Could not replace import_runtime()')

p.write_text(ns, encoding='utf-8')
print('OK: CUDA runtime hotfix applied')
