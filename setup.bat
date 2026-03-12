@echo off
title VRBOT Agent - Setup
color 0A
echo.
echo  ======================================
echo    VRBOT Agent - One-Click Setup
echo    Viking Rise Automation
echo  ======================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [!] Python not found!
    echo [!] Please install Python 3.10+ from python.org
    echo [!] Make sure to check "Add Python to PATH"
    pause
    start https://www.python.org/downloads/
    exit /b 1
)
echo [OK] Python found

:: Check pip
pip --version >nul 2>&1
if errorlevel 1 (
    echo [!] pip not found. Installing...
    python -m ensurepip
)
echo [OK] pip found

:: Install dependencies
echo.
echo [*] Installing dependencies...
pip install websockets Pillow numpy opencv-python-headless onnxruntime openai anthropic requests >nul 2>&1
echo [OK] Dependencies installed

:: Check LDPlayer
if exist "C:\LDPlayer\LDPlayer9\ldconsole.exe" (
    echo [OK] LDPlayer 9 found
) else (
    echo [!] LDPlayer 9 not found at C:\LDPlayer\LDPlayer9
    echo [!] Download from: https://www.ldplayer.net/
    echo [!] You can continue but LDPlayer is required to run the bot
)

:: Check ADB
adb version >nul 2>&1
if errorlevel 1 (
    echo [!] ADB not in PATH, will use LDPlayer's ADB
) else (
    echo [OK] ADB found
)

:: Create directories
if not exist "logs" mkdir logs
if not exist "screenshots" mkdir screenshots
if not exist "templates" mkdir templates
if not exist "config" mkdir config

echo.
echo  ======================================
echo    Setup Complete!
echo  ======================================
echo.
echo  Next steps:
echo  1. Open LDPlayer and start Viking Rise
echo  2. Run start.bat to launch VRBOT Agent
echo.
pause
