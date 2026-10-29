@echo off
title AI Document Understanding Platform - Server Launcher
color 0B
echo ==========================================================
echo   AI Document Understanding Platform - Starting Server
echo ==========================================================
echo.

cd /d "%~dp0\.."

REM Activate virtual environment if present
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
    echo [OK] Virtual environment activated.
)

echo [OK] Launching application on http://127.0.0.1:5000
echo.
python app.py
pause
