$ErrorActionPreference = "Stop"

if (!(Test-Path ".venv")) {
  py -m venv .venv
}

. .\.venv\Scripts\Activate.ps1
py -m pip install --upgrade pip
pip install -r requirements-gpu.txt
pip install pyinstaller

pyinstaller --onefile --clean --name MelateCruncher local_cruncher.py

Write-Host ""
Write-Host "Ejecutable creado en: dist\MelateCruncher.exe" -ForegroundColor Green
Write-Host "Copia historial.csv junto a MelateCruncher.exe y ejecuta:" -ForegroundColor Yellow
Write-Host ".\MelateCruncher.exe --csv .\historial.csv" -ForegroundColor Cyan
