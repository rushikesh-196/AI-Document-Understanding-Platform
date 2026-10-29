# AI Document Intelligence Platform - Root Launcher
# Delegates to scripts/start_server.ps1 while preserving exact root execution
$scriptPath = Join-Path $PSScriptRoot "scripts\start_server.ps1"
if (Test-Path $scriptPath) {
    & $scriptPath
} else {
    Write-Host "[ERROR] scripts/start_server.ps1 not found." -ForegroundColor Red
}
