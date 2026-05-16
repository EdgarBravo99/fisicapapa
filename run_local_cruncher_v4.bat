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
  echo Ejecuta git pull origin codex/v4-deep-stacking o revisa que estes en el repo correcto.
  pause
  exit /b 1
)

echo Usando Python:
%PY_CMD% --version
echo.

if exist "fix_v4_deep_stacking_alignment.py" (
  echo Aplicando alineacion V4 antes de iniciar...
  %PY_CMD% -X utf8 "fix_v4_deep_stacking_alignment.py"
  if %ERRORLEVEL% NEQ 0 (
    echo ERROR: No se pudo aplicar fix_v4_deep_stacking_alignment.py
    pause
    exit /b 1
  )
)

echo.
echo Iniciando local_cruncher_v4_deep_stacking.py...
echo.
%PY_CMD% -X utf8 "local_cruncher_v4_deep_stacking.py"

echo.
echo ================================================================
echo El programa termino o se detuvo. Si hubo error, copia el texto de arriba.
echo ================================================================
pause
endlocal
