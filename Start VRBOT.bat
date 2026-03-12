@echo off
cd /d "%~dp0"
title VRBOT Agent v5.3
echo Starting VRBOT Agent...
python vrbot_gui.py
if errorlevel 1 (
    echo Python not found! Please install Python 3.10+ and add to PATH.
    echo Download: https://www.python.org/downloads/
)
pause
