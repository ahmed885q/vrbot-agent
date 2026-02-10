@echo off
title VRBOT Agent v2.0
echo.

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Run install.bat first!
    pause
    exit /b 1
)

:: Check LDPlayer ADB
echo [INFO] Checking LDPlayer connection...
adb connect 127.0.0.1:5555 >nul 2>&1

:: Start the bot
echo [INFO] Starting VRBOT Agent v2.0...
echo.
python main.py
echo.
echo [INFO] VRBOT Agent stopped.
pause

