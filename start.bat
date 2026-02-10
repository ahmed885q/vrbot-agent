@echo off
title VRBOT Agent v1.0 - Viking Rise Bot
color 0B
echo ================================================
echo   VRBOT Agent v1.0 - Starting...
echo ================================================
echo.

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Run install.bat first!
    pause
    exit /b 1
)

:: Check LDPlayer ADB connection
echo [INFO] Checking LDPlayer ADB connection...
adb connect 127.0.0.1:5555 >nul 2>&1

:: Start the bot
echo [INFO] Starting VRBOT Agent...
echo.
python main.py
echo.
echo [INFO] VRBOT Agent stopped.
pause
