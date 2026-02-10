@echo off
title VRBOT Agent - Installer
echo.
echo ========================================
echo   VRBOT Agent v2.0 - Installer
echo ========================================
echo.

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found!
    echo Please install Python 3.10+ from https://www.python.org/downloads/
    echo IMPORTANT: Check "Add Python to PATH" during installation!
    pause
    exit /b 1
)
echo [OK] Python found

:: Install requirements
echo [INFO] Installing Python packages...
pip install -r requirements.txt --quiet
if %errorlevel% neq 0 (
    echo [WARN] Some packages may have failed. Trying individually...
    pip install opencv-python --quiet
    pip install numpy --quiet
    pip install pytesseract --quiet
    pip install Pillow --quiet
    pip install websockets --quiet
)
echo [OK] Python packages installed

:: Check ADB
adb version >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARN] ADB not found in PATH.
    echo LDPlayer includes ADB. Make sure LDPlayer is installed.
    echo Default path: C:\LDPlayer\LDPlayer9
) else (
    echo [OK] ADB found
)

:: Check LDPlayer
if exist "C:\LDPlayer\LDPlayer9\ldconsole.exe" (
    echo [OK] LDPlayer 9 found
) else if exist "C:\LDPlayer\LDPlayer4.0\ldconsole.exe" (
    echo [OK] LDPlayer 4 found
) else (
    echo [WARN] LDPlayer not found at default path.
    echo Please update ldplayer_path in config/vrbot_config.json
)

:: Check Tesseract OCR
tesseract --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Installing Tesseract OCR...
    echo Please download from: https://github.com/UB-Mannheim/tesseract/wiki
    echo After install, add to PATH or set path in config.
) else (
    echo [OK] Tesseract OCR found
)

:: Create directories
mkdir config 2>nul
mkdir logs 2>nul
mkdir screenshots 2>nul
mkdir templates 2>nul

echo.
echo ========================================
echo   Installation Complete!
echo ========================================
echo.
echo Next steps:
echo   1. Start LDPlayer and open Viking Rise
echo   2. Run start.bat to start the bot
echo   3. Add template images to /templates folder
echo.
pause

