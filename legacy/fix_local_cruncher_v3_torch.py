#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Parchea local_cruncher_v3.py para importar PyTorch antes de definir TinyLSTM."""
from pathlib import Path

TARGET = Path("local_cruncher_v3.py")
NEEDLE = "class TinyLSTM(nn.Module):"
PATCH = '''# Hotfix: import PyTorch before declaring TinyLSTM.
# Fixes: AttributeError: 'NoneType' object has no attribute 'Module'.
if nn is None or torch is None:
    try:
        import torch as _early_torch
        import torch.nn as _early_nn
    except Exception:
        print("Instalando PyTorch antes de definir TinyLSTM, por favor espere...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "torch", "--quiet", "--disable-pip-version-check"])
        import torch as _early_torch
        import torch.nn as _early_nn
    torch = _early_torch
    nn = _early_nn

class TinyLSTM(nn.Module):'''

if not TARGET.exists():
    raise SystemExit(f"No existe {TARGET.resolve()}")

text = TARGET.read_text(encoding="utf-8")
if "Hotfix: import PyTorch before declaring TinyLSTM" in text:
    print("Hotfix ya estaba aplicado.")
elif NEEDLE not in text:
    raise SystemExit("No encontré la clase TinyLSTM para parchear.")
else:
    text = text.replace(NEEDLE, PATCH, 1)
    TARGET.write_text(text, encoding="utf-8")
    print("Hotfix aplicado correctamente a local_cruncher_v3.py")
