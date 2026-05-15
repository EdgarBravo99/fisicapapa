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
