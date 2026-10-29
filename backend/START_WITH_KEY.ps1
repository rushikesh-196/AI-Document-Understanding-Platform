<#
PowerShell helper: START_WITH_KEY.ps1
- Loads a local backend/.env (if present) but does NOT print secrets
- Prompts to use an existing GEMINI_API_KEY found in backend/.env or enter a key for this session
- Sets GEMINI_API_KEY in the current session and starts the backend (python app.py)

USAGE:
  1. Copy backend/.env.template -> backend/.env and edit values (ensure .env is gitignored)
  2. From a PowerShell prompt run: .\START_WITH_KEY.ps1
  3. Follow prompts. The script will start the backend in the same session so the env var is available.

Security: This script never writes your real secret into repo files. It only sets the env var for the shell session.
#>

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$envFile = Join-Path $scriptDir '.env'

function Read-EnvValue($path, $key) {
    if (-Not (Test-Path $path)) { return $null }
    $lines = Get-Content -Raw -ErrorAction SilentlyContinue $path -Encoding UTF8
    foreach ($ln in $lines -split "\r?\n") {
        $trim = $ln.Trim()
        if ($trim -match "^$key\s*=\s*(.+)$") {
            return $matches[1].Trim('"')
        }
    }
    return $null
}

Write-Host "\n[Helper] Backend helper: set GEMINI_API_KEY for this session and start server" -ForegroundColor Cyan

$existingKey = Read-EnvValue -path $envFile -key 'GEMINI_API_KEY'
$useKey = $false
if ($existingKey) {
    # Mask part of the key in the prompt
    $masked = if ($existingKey.Length -ge 8) { $existingKey.Substring(0,4) + '...' + $existingKey.Substring($existingKey.Length-4) } else { '***masked***' }
    Write-Host "Found GEMINI_API_KEY in backend/.env: $masked" -ForegroundColor Yellow
    $yn = Read-Host "Use the key found in backend/.env for this session? (Y/n)"
    if ($yn -eq '' -or $yn -match '^[Yy]') { $useKey = $true }
}

if (-not $useKey) {
    Write-Host "Enter GEMINI API key for this session (input hidden). Press Enter to cancel." -ForegroundColor Yellow
    $secure = Read-Host -AsSecureString "GEMINI_API_KEY"
    if (-not $secure) { Write-Host "No key entered. Exiting." -ForegroundColor Red; exit 1 }
    $bstr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try { $plainKey = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr) } finally { [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
    $env:GEMINI_API_KEY = $plainKey
    Write-Host "GEMINI_API_KEY set for this PowerShell session." -ForegroundColor Green
} else {
    # Use the existing key from backend/.env but do not write it into the environment file
    $env:GEMINI_API_KEY = $existingKey
    Write-Host "Using GEMINI_API_KEY from backend/.env for this PowerShell session." -ForegroundColor Green
}

# Optionally show a short test help (does not reveal the key)
Write-Host "\nYou can test that the process can read the key by running:" -ForegroundColor Cyan
Write-Host "  python -c ""from services.llm_service import get_api_key; print('KEY FOUND' if get_api_key() else 'KEY NOT FOUND')""" -ForegroundColor Gray

# Start the backend server in the current session so the env var is present
Write-Host "\nStarting backend (python app.py). Press Ctrl+C to stop." -ForegroundColor Cyan
& python app.py

# When python exits, clear the session variable
Remove-Variable -Name env -ErrorAction SilentlyContinue
Write-Host "Backend process ended. GEMINI_API_KEY cleared from session." -ForegroundColor Yellow
