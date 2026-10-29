# ==============================================================================
# AI Document Intelligence Platform - One-Click Environment Setup Script
# ==============================================================================

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  AI Document Intelligence Platform - Environment Setup   " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ""

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $ProjectRoot

# 1. Check or Create Virtual Environment
if (-Not (Test-Path ".\venv")) {
    Write-Host "[INFO] Creating Python virtual environment (venv)..." -ForegroundColor Yellow
    python -m venv venv
    Write-Host "[OK] Virtual environment created." -ForegroundColor Green
} else {
    Write-Host "[OK] Virtual environment found." -ForegroundColor Green
}

# 2. Activate Virtual Environment
& ".\venv\Scripts\Activate.ps1"

# 3. Upgrade pip and install requirements
Write-Host "[INFO] Installing Python dependencies from requirements.txt..." -ForegroundColor Yellow
pip install --upgrade pip
pip install -r requirements.txt

# 4. Download spaCy Language Model if missing
Write-Host "[INFO] Checking spaCy language model (en_core_web_sm)..." -ForegroundColor Yellow
python -c "import spacy; spacy.load('en_core_web_sm')" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[INFO] Downloading en_core_web_sm model..." -ForegroundColor Yellow
    python -m spacy download en_core_web_sm
}
Write-Host "[OK] spaCy model ready." -ForegroundColor Green

# 5. Create .env if not exists
if (-Not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "[OK] Created '.env' from '.env.example'. Please customize credentials if desired." -ForegroundColor Green
}

# 6. Initialize Database Schema
Write-Host "[INFO] Initializing application database schema..." -ForegroundColor Yellow
python -c "from services.database import init_auth_db, get_active_db; init_auth_db(); engine, _ = get_active_db(); print(f'[OK] Database initialized successfully with engine: {engine}')"

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Setup Completed Successfully!                           " -ForegroundColor Green
Write-Host "  To start the server, run: .\scripts\start_server.ps1    " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
