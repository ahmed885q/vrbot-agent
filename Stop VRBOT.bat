@echo off
taskkill /f /im python.exe /fi "WINDOWTITLE eq VRBOT*" 2>nul
echo VRBOT Agent stopped.
pause
