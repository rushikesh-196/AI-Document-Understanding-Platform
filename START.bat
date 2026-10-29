@echo off
REM AI Document Intelligence Platform - Root Launcher
REM Delegates to scripts\start.bat while preserving root execution
if exist "%~dp0scripts\start.bat" (
    call "%~dp0scripts\start.bat"
) else (
    echo [ERROR] scripts\start.bat not found.
    pause
)
