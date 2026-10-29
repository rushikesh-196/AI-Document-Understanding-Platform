# ==============================================================================
# AI Document Intelligence Platform - FastAPI + React Launcher (PowerShell)
# ==============================================================================

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Starting FastAPI Headless Backend (Port 8000)          " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $ProjectRoot

# Activate virtual environment if present
if (Test-Path ".\venv\Scripts\Activate.ps1") {
    & ".\venv\Scripts\Activate.ps1"
}

$env:PYTHONPATH = "backend"
Write-Host "[OK] Starting FastAPI backend on http://127.0.0.1:8000" -ForegroundColor Green
Write-Host "  Interactive Swagger API Docs: http://127.0.0.1:8000/api/docs" -ForegroundColor Cyan
Write-Host "  ReDoc API Docs:               http://127.0.0.1:8000/api/redoc" -ForegroundColor Cyan
Write-Host ""

python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
