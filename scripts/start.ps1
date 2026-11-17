# Run from any folder: right-click -> Run, or:
# powershell -ExecutionPolicy Bypass -File "C:\Users\user\Desktop\Проект фулстек\keitaro-wrapper\scripts\start.ps1"

$ProjectRoot = Split-Path $PSScriptRoot -Parent
Set-Location $ProjectRoot
Write-Host "Project: $ProjectRoot"

$Py = Get-Command py -ErrorAction SilentlyContinue
if ($Py) { $Python = "py", "-3" } else { $Python = @("python") }

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    Write-Host "Creating venv..."
    & @Python -m venv .venv
}

$VenvPy = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
& $VenvPy -m pip install -q -r requirements.txt
& $VenvPy scripts\init_db.py

Write-Host "Starting http://127.0.0.1:8000"
& $VenvPy -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000