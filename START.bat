@echo off
title Roblox Checker
set FOLDER=%~dp0

echo.
echo  === Roblox Code Checker ===
echo.

:: Check Python
echo  [1/3] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo  Python not found. Installing...
    winget install -e --id Python.Python.3.11 --silent --accept-package-agreements --accept-source-agreements >nul 2>&1
    if errorlevel 1 (
        echo  Downloading Python installer...
        powershell -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe' -OutFile '%TEMP%\python_setup.exe'" >nul 2>&1
        "%TEMP%\python_setup.exe" /quiet InstallAllUsers=1 PrependPath=1 Include_test=0
        set "PATH=%PATH%;%LOCALAPPDATA%\Programs\Python\Python311;%LOCALAPPDATA%\Programs\Python\Python311\Scripts"
    )
    echo  Python installed!
) else (
    echo  Python OK
)

:: Install Playwright
echo  [2/3] Installing Playwright...
pip install playwright >nul 2>&1
echo  Playwright OK

:: Install browser
echo  [3/3] Setting up browser (first time takes 1-2 min)...
playwright install chromium >nul 2>&1
echo  Browser OK

echo.

:: Check codes.txt
if not exist "%FOLDER%codes.txt" (
    echo  ERROR: codes.txt not found!
    echo  Create codes.txt in this folder with one code per line.
    echo.
    explorer "%FOLDER%"
    pause
    exit
)

:: Check checker.py
if not exist "%FOLDER%checker.py" (
    echo  ERROR: checker.py not found!
    echo  Put checker.py in the same folder as START.bat
    pause
    exit
)

echo  Starting checker...
echo.
python "%FOLDER%checker.py"
pause
