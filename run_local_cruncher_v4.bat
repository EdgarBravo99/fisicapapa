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
) else (
  echo ERROR: Falta patch_v4_exhaustive_search.py en esta carpeta.
  echo Ejecuta: git pull origin main
  pause
  exit /b 1
)

findstr /C:"col = n if indexed_with_zero_pad else n - 1" "local_cruncher_v4_deep_stacking.py" >nul
if %ERRORLEVEL% NEQ 0 (
  echo ERROR: V4 no tiene el fix de matriz para el numero 56.
  pause
  exit /b 1
)

findstr /C:"def exhaustive_search(" "local_cruncher_v4_deep_stacking.py" >nul
if %ERRORLEVEL% NEQ 0 (
  echo ERROR: V4 no tiene la funcion exhaustive_search.
  pause
  exit /b 1
)

findstr /C:"ranked = exhaustive_search" "local_cruncher_v4_deep_stacking.py" >nul
if %ERRORLEVEL% NEQ 0 (
  echo ERROR: V4 no esta llamando exhaustive_search en run_pipeline.
  pause
  exit /b 1
)

findstr /C:"ranked = monte_carlo" "local_cruncher_v4_deep_stacking.py" >nul
if %ERRORLEVEL% EQU 0 (
  echo ERROR: V4 aun contiene la llamada vieja ranked = monte_carlo.
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
