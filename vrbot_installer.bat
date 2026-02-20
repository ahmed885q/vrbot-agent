@echo off
echo ============================================
echo   VRBOT Installer
echo ============================================
pip install PyQt5 requests openai ultralytics --quiet
if not exist "models" mkdir models
if not exist "debug_screenshots" mkdir debug_screenshots
echo.
echo   Done! Run: python vrbot_gui.py
pause
