@echo off
title Roblox Checker
set FOLDER=%~dp0
echo.
echo  === Roblox Code Checker ===
echo.
echo  [1/3] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    winget install -e --id Python.Python.3.11 --silent --accept-package-agreements --accept-source-agreements >nul 2>&1
    if errorlevel 1 (
        powershell -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe' -OutFile '%TEMP%\python_setup.exe'" >nul 2>&1
        "%TEMP%\python_setup.exe" /quiet InstallAllUsers=1 PrependPath=1 Include_test=0
    )
)
echo  Python OK
echo  [2/3] Installing Playwright...
python -m pip install playwright -q >nul 2>&1
echo  Playwright OK
echo  [3/3] Setting up browser...
python -m playwright install chromium >nul 2>&1
echo  Browser OK
echo.
if not exist "%FOLDER%codes.txt" (echo  ERROR: codes.txt not found! & pause & exit)
if not exist "%FOLDER%checker.py" (echo  ERROR: checker.py not found! & pause & exit)
echo  Starting...
echo.
python "%FOLDER%checker.py"
pause
