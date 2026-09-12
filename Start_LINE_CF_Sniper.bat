@echo off
title LINE Personal Auto-CF Sniper (PC Desktop)
color 0A
echo ========================================================
echo   LINE Personal Auto-CF Sniper (PC Desktop Edition)
echo ========================================================
echo Starting application...
python app_desktop.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo An error occurred. Press any key to exit.
    pause >nul
)
