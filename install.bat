@echo off
title VRBOT Agent - Installer
color 0A
echo ================================================
echo   VRBOT Agent v1.0 - Windows Installer
echo   Viking Rise Automation Bot
echo ================================================
echo.

:: Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is NOT installed!
    echo.
    echo Please install Python first:
    echo   1. Go to: https://www.python.org/downloads/
    echo   2. Download Python 3.11+
    echo   3. IMPORTANT: Check "Add Python to PATH" during install
    echo   4. Run this installer again
    echo.
    pause
    exit /b 1
)

echo [OK] Python found:
python --version
echo.

:: Install Python packages
echo [1/4] Installing Python packages...
echo.
pip install opencv-python>=4.8.0 --quiet
pip install pytesseract>=0.3.10 --quiet
pip install numpy>=1.24.0 --quiet
pip install websockets>=12.0 --quiet
pip install Pillow>=10.0.0 --quiet
echo.
echo [OK] Python packages installed!
echo.

:: Check for Tesseract OCR
echo [2/4] Checking Tesseract OCR...
where tesseract >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Tesseract OCR not found. Downloading...
    echo.
    
    :: Download Tesseract installer
    powershell -Command "& {Invoke-WebRequest -Uri 'https://deb.rug.nl/ppa/mirror/github-releases/UB-Mannheim_tesseract-ocr/tesseract-ocr-w64-setup-5.4.0.20240606.exe' -OutFile 'tesseract_installer.exe'}" 2>nul
    
    if exist tesseract_installer.exe (
        echo [INFO] Running Tesseract installer...
        echo        Please follow the installation wizard.
        echo        IMPORTANT: Keep default install path!
        echo.
        start /wait tesseract_installer.exe
        del tesseract_installer.exe 2>nul
    ) else (
        echo [WARNING] Could not auto-download Tesseract.
        echo          Please install manually from:
        echo          https://github.com/UB-Mannheim/tesseract/wiki
        echo          Install to: C:\Program Files\Tesseract-OCR
        echo.
    )
) else (
    echo [OK] Tesseract OCR found!
)
echo.

:: Check LDPlayer ADB
echo [3/4] Checking LDPlayer ADB...
set ADB_FOUND=0

if exist "C:\LDPlayer\LDPlayer9\adb.exe" (
    echo [OK] LDPlayer 9 ADB found: C:\LDPlayer\LDPlayer9\adb.exe
    set ADB_FOUND=1
)
if exist "C:\Program Files\LDPlayer\LDPlayer9\adb.exe" (
    echo [OK] LDPlayer 9 ADB found: C:\Program Files\LDPlayer\LDPlayer9\adb.exe
    set ADB_FOUND=1
)
if exist "C:\LDPlayer\LDPlayer4.0\adb.exe" (
    echo [OK] LDPlayer 4 ADB found: C:\LDPlayer\LDPlayer4.0\adb.exe
    set ADB_FOUND=1
)

if %ADB_FOUND%==0 (
    echo [WARNING] LDPlayer ADB not found in default paths.
    echo          Make sure LDPlayer is installed.
    echo          Default: C:\LDPlayer\LDPlayer9\
)
echo.

:: Create templates folder
echo [4/4] Setting up folders...
if not exist "templates" mkdir templates
if not exist "logs" mkdir logs
if not exist "screenshots" mkdir screenshots
echo [OK] Folders created: templates, logs, screenshots
echo.

:: Verify installation
echo ================================================
echo   Installation Verification
echo ================================================
echo.
python -c "import cv2; print(f'  [OK] OpenCV {cv2.__version__}')" 2>nul || echo   [FAIL] OpenCV
python -c "import numpy; print(f'  [OK] NumPy {numpy.__version__}')" 2>nul || echo   [FAIL] NumPy
python -c "import websockets; print(f'  [OK] websockets {websockets.__version__}')" 2>nul || echo   [FAIL] websockets
python -c "import PIL; print(f'  [OK] Pillow {PIL.__version__}')" 2>nul || echo   [FAIL] Pillow
python -c "import pytesseract; print('  [OK] pytesseract')" 2>nul || echo   [FAIL] pytesseract

echo.
echo ================================================
echo   Installation Complete!
echo ================================================
echo.
echo   Next steps:
echo   1. Open LDPlayer and start Viking Rise
echo   2. Set LDPlayer resolution to 1280x720
echo   3. Take screenshots and add to templates\ folder
echo   4. Run: python main.py
echo.
echo ================================================
pause
