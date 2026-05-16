@echo off
setlocal
cd /d "%~dp0"
title Melate Pro - Local Cruncher V4 Deep Stacking

echo ================================================================
echo   MELATE PRO - LOCAL CRUNCHER V4 DEEP STACKING
echo ================================================================
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
    pause
    exit /b 1
  )
)

if not exist "local_cruncher_v4_deep_stacking.py" (
  echo ERROR: No existe local_cruncher_v4_deep_stacking.py en esta carpeta.
  echo Ejecuta: git pull origin main
  pause
  exit /b 1
)

echo Usando Python:
%PY_CMD% --version
echo.

if exist "preflight_v4_cuda.py" (
  echo [PRE] Revisando CUDA / CuPy / PyTorch / NVRTC...
  %PY_CMD% -X utf8 "preflight_v4_cuda.py"
  if %ERRORLEVEL% NEQ 0 (
    echo ERROR: fallo preflight_v4_cuda.py
    pause
    exit /b 1
  )
)

if exist ".v4_cuda_env.bat" (
  call ".v4_cuda_env.bat"
)

if not exist "fix_v4_deep_stacking_alignment.py" (
  echo ERROR: Falta fix_v4_deep_stacking_alignment.py en esta carpeta.
  echo Ejecuta: git pull origin main
  pause
  exit /b 1
)

echo [PRE] Aplicando alineacion V4...
%PY_CMD% -X utf8 "fix_v4_deep_stacking_alignment.py"
if %ERRORLEVEL% NEQ 0 (
  echo ERROR: No se pudo aplicar fix_v4_deep_stacking_alignment.py
  pause
  exit /b 1
)

if exist "hotfix_v4_mat_index.py" (
  echo [PRE] Validando hotfix de matriz 1..56...
  %PY_CMD% -X utf8 "hotfix_v4_mat_index.py"
  if %ERRORLEVEL% NEQ 0 (
    echo ERROR: No se pudo aplicar hotfix_v4_mat_index.py
    pause
    exit /b 1
  )
)

if exist "patch_v4_exhaustive_search.py" (
  echo [PRE] Activando busqueda exhaustiva deterministica V4...
  %PY_CMD% -X utf8 "patch_v4_exhaustive_search.py"
  if %ERRORLEVEL% NEQ 0 (
    echo ERROR: No se pudo aplicar patch_v4_exhaustive_search.py
    pause
    exit /b 1
  )
)

%PY_CMD% -X utf8 -c "from pathlib import Path; s=Path('local_cruncher_v4_deep_stacking.py').read_text(encoding='utf-8'); ok=('col = n if indexed_with_zero_pad else n - 1' in s and 'def exhaustive_search(' in s and 'ranked = exhaustive_search(score, audit[\"graph\"])' in s); raise SystemExit(0 if ok else 1)"
if %ERRORLEVEL% NEQ 0 (
  echo ERROR: V4 no quedo correctamente parchado. No se ejecutara para evitar errores o Monte Carlo viejo.
  pause
  exit /b 1
)

echo.
echo [OK] Preflight completo. Iniciando V4 Deep Stacking...
echo.
%PY_CMD% -X utf8 "local_cruncher_v4_deep_stacking.py"

echo.
echo ================================================================
echo El programa termino o se detuvo. Si hubo error, copia el texto de arriba.
echo ================================================================
pause
endlocal
