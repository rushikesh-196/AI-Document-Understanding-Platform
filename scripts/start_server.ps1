# ==============================================================================
# AI Document Intelligence Platform - Production Server Launcher (PowerShell)
# ==============================================================================

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  AI Document Intelligence Platform - Starting Server     " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ""

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $ProjectRoot

# Stop any stale server still holding port 5000
Write-Host "[INFO] Checking for old server on port 5000..." -ForegroundColor Yellow
$existing = Get-NetTCPConnection -LocalPort 5000 -ErrorAction SilentlyContinue |
    Where-Object { $_.State -eq 'Listen' } |
    Select-Object -ExpandProperty OwningProcess -Unique

foreach ($procId in $existing) {
    if ($procId) {
        Write-Host "[INFO] Stopping previous server process (PID $procId)..." -ForegroundColor Yellow
        Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
    }
}

if ($existing) {
    Start-Sleep -Seconds 1
    Write-Host "[OK] Port 5000 cleared" -ForegroundColor Green
}

# Activate virtual environment if present
if (Test-Path ".\venv\Scripts\Activate.ps1") {
    & ".\venv\Scripts\Activate.ps1"
    Write-Host "[OK] Virtual environment activated" -ForegroundColor Green
}

Write-Host "[OK] Launching AI Document Intelligence Platform..." -ForegroundColor Green
Write-Host ""
Write-Host "  Home & Uploads: http://127.0.0.1:5000" -ForegroundColor Cyan
Write-Host "  User Dashboard: http://127.0.0.1:5000/dashboard" -ForegroundColor Cyan
Write-Host "  Admin Portal:   http://127.0.0.1:5000/auth?portal=admin" -ForegroundColor Cyan
Write-Host ""
Write-Host "Press CTRL+C to stop the server." -ForegroundColor Yellow
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ""

python app.py
