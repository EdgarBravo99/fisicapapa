@echo off
setlocal
cd /d "%~dp0"
title Melate Pro - Local Cruncher V4.2 Feedback

echo ================================================================
echo   MELATE PRO - LOCAL CRUNCHER V4.2 FEEDBACK LOOP
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

if exist "hotfix_v4_cuda_runtime.py" (
  echo [PRE] Aplicando hotfix runtime CUDA dentro del cruncher...
  %PY_CMD% -X utf8 "hotfix_v4_cuda_runtime.py"
  if %ERRORLEVEL% NEQ 0 (
    echo ERROR: No se pudo aplicar hotfix_v4_cuda_runtime.py
    pause
    exit /b 1
  )
) else (
  echo ERROR: Falta hotfix_v4_cuda_runtime.py en esta carpeta.
  echo Ejecuta: git pull origin main
  pause
  exit /b 1
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

if exist "hotfix_v4_graph_dict.py" (
  echo [PRE] Aplicando hotfix de grafo para exhaustive_search...
  %PY_CMD% -X utf8 "hotfix_v4_graph_dict.py"
  if %ERRORLEVEL% NEQ 0 (
    echo ERROR: No se pudo aplicar hotfix_v4_graph_dict.py
    pause
    exit /b 1
  )
) else (
  echo ERROR: Falta hotfix_v4_graph_dict.py en esta carpeta.
  echo Ejecuta: git pull origin main
  pause
  exit /b 1
)

if exist "patch_v4_hit_aware_meta.py" (
  echo [PRE] Aplicando V4.1 hit-aware meta learning...
  %PY_CMD% -X utf8 "patch_v4_hit_aware_meta.py"
  if %ERRORLEVEL% NEQ 0 (
    echo ERROR: No se pudo aplicar patch_v4_hit_aware_meta.py
    pause
    exit /b 1
  )
) else (
  echo ERROR: Falta patch_v4_hit_aware_meta.py en esta carpeta.
  echo Ejecuta: git pull origin main
  pause
  exit /b 1
)

if exist "patch_v4_oos_feedback_loop.py" (
  echo [PRE] Aplicando V4.2 feedback loop OOS fold-a-fold...
  %PY_CMD% -X utf8 "patch_v4_oos_feedback_loop.py"
  if %ERRORLEVEL% NEQ 0 (
    echo ERROR: No se pudo aplicar patch_v4_oos_feedback_loop.py
    pause
    exit /b 1
  )
) else (
  echo ERROR: Falta patch_v4_oos_feedback_loop.py en esta carpeta.
  echo Ejecuta: git pull origin main
  pause
  exit /b 1
)

findstr /C:"normalize_cuda_runtime_paths_v4" "local_cruncher_v4_deep_stacking.py" >nul
if %ERRORLEVEL% NEQ 0 (
  echo ERROR: V4 no tiene el hotfix runtime CUDA.
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

findstr /C:"graph_source = graph" "local_cruncher_v4_deep_stacking.py" >nul
if %ERRORLEVEL% NEQ 0 (
  echo ERROR: V4 no tiene el hotfix para audit[graph] como dict.
  pause
  exit /b 1
)

findstr /C:"def train_meta_model_hitaware_v41" "local_cruncher_v4_deep_stacking.py" >nul
if %ERRORLEVEL% NEQ 0 (
  echo ERROR: V4 no tiene el patch hit-aware V4.1.
  pause
  exit /b 1
)

findstr /C:"def walk_forward_oos_feedback_v42" "local_cruncher_v4_deep_stacking.py" >nul
if %ERRORLEVEL% NEQ 0 (
  echo ERROR: V4 no tiene el feedback loop OOS V4.2.
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
echo [OK] Preflight completo. Iniciando V4.2 Feedback Loop...
echo.
%PY_CMD% -X utf8 "local_cruncher_v4_deep_stacking.py"

echo.
echo ================================================================
echo El programa termino o se detuvo. Si hubo error, copia el texto de arriba.
echo ================================================================
pause
endlocal
