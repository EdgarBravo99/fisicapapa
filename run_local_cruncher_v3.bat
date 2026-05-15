@echo off
setlocal
cd /d "%~dp0"
title Melate Pro - Local Cruncher V3

echo ================================================================
echo   MELATE PRO - LOCAL CRUNCHER V3
echo ================================================================
echo.
echo Carpeta actual:
echo %CD%
echo.

where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  set PY_CMD=py
) else (
  where python >nul 2>nul
  if %ERRORLEVEL% EQU 0 (
    set PY_CMD=python
  ) else (
    echo ERROR: No se encontro Python.
    echo Instala Python o agrega Python al PATH.
    echo.
    pause
    exit /b 1
  )
)

if not exist "local_cruncher_v3.py" (
  echo ERROR: No existe local_cruncher_v3.py en esta carpeta.
  echo Ejecuta git pull origin main o revisa que estes en el repo correcto.
  echo.
  pause
  exit /b 1
)

if not exist "historial.csv" (
  if not exist "historial_melate.csv" (
    if not exist "historial_revancha.csv" (
      if not exist "melate.csv" (
        if not exist "revancha.csv" (
          echo ADVERTENCIA: No encontre historial.csv, historial_melate.csv, historial_revancha.csv, melate.csv ni revancha.csv.
          echo El programa abrira, pero al ejecutar pipeline pedira/esperara un CSV valido.
          echo.
        )
      )
    )
  )
)

echo Usando Python:
%PY_CMD% --version
echo.
echo Aplicando hotfix de arranque V3 si hace falta...
%PY_CMD% -X utf8 -c "from pathlib import Path; p=Path('local_cruncher_v3.py'); s=p.read_text(encoding='utf-8'); marker='class TinyLSTM(nn.Module):'; boot='''\n# Hotfix: PyTorch debe existir antes de definir TinyLSTM.\n# Este bloque evita AttributeError: NoneType has no attribute Module.\nif nn is None or torch is None:\n    try:\n        import torch as _early_torch\n        import torch.nn as _early_nn\n    except Exception:\n        print('Instalando PyTorch antes de definir TinyLSTM, por favor espere...')\n        subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'torch', '--quiet', '--disable-pip-version-check'])\n        import torch as _early_torch\n        import torch.nn as _early_nn\n    torch = _early_torch\n    nn = _early_nn\n\n'''; target=boot+marker; changed=False\nif marker in s and 'Hotfix: PyTorch debe existir antes de definir TinyLSTM' not in s:\n    s=s.replace(marker,target,1); p.write_text(s,encoding='utf-8'); changed=True\nprint('Hotfix aplicado.' if changed else 'Hotfix ya presente o no necesario.')"
if %ERRORLEVEL% NEQ 0 (
  echo ERROR: No se pudo aplicar hotfix de PyTorch.
  pause
  exit /b 1
)

echo.
echo Iniciando local_cruncher_v3.py...
echo La primera ejecucion puede tardar porque instala/valida pandas, numpy, scipy, xgboost, optuna, torch y cupy.
echo.

%PY_CMD% -X utf8 "local_cruncher_v3.py"

echo.
echo ================================================================
echo El programa termino o se detuvo. Si hubo error, copia el texto de arriba.
echo ================================================================
pause
endlocal
